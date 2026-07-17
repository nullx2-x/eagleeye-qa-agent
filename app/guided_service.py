from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
import uuid
from typing import Any

from .guided_models import (
    GuidedControlRequest,
    GuidedManualVerdict,
    GuidedObservation,
    GuidedObservationBatch,
    GuidedObservationReceipt,
    GuidedScenarioDefinition,
    GuidedScenarioStep,
    GuidedSession,
    GuidedSessionReceipt,
    GuidedSessionStart,
    GuidedStepResult,
    GuidedTelemetryOracle,
    GuidedTelemetryPredicate,
)
from .guided_storage import (
    RevisionConflict,
    append_audit,
    append_observation,
    audits_for_session,
    create_session,
    delete_attestation_digest,
    list_scenarios,
    list_sessions,
    load_attestation_digest,
    load_scenario,
    load_session,
    observations_for_session,
    save_attestation_digest,
    save_scenario,
    save_session,
    write_report,
    write_session_evidence,
    write_step_evidence,
)
from .quality import evaluate_quality_gate
from .strategy_models import QualityGateRequest, QualityGateResponse


class InvalidTransition(RuntimeError):
    pass


class HumanAttestationRequired(PermissionError):
    pass


def now_ms() -> int:
    return time.time_ns() // 1_000_000


_SUGGESTIONS = {
    "NO_TELEMETRY": (
        "テレメトリアダプターの接続先・イベント名・送信間隔を確認してから、このstepだけ再実施してください。"
    ),
    "ORACLE_NOT_SATISFIED": (
        "期待値を表すpredicateと実測valuesを比較し、仕様・アダプター・対象機能のどこに"
        "差があるか切り分けてください。"
    ),
    "PREDICATE_MISMATCH": (
        "失敗観測のvalues/payloadを確認し、境界条件を再現する回帰テストを追加してください。"
    ),
    "REQUIRED_EVENT_MISSING": (
        "必要イベントの発火条件、イベント名、debounce、テレメトリ配送を確認してください。"
    ),
    "EXACT_EVENT_COUNT_MISMATCH": (
        "イベントの重複発火・欠落・debounceを確認し、期待回数と一致する証跡で再実施してください。"
    ),
    "MAX_EVENT_COUNT_EXCEEDED": (
        "イベントの多重発火または意図しない再入を確認し、上限を超えない回帰テストを追加してください。"
    ),
    "SETTLE_WINDOW_INCOMPLETE": (
        "期待状態の成立後も指定された静穏期間を観測できるよう、試験時間と送信間隔を見直してください。"
    ),
    "FORBIDDEN_EVENT": "禁止イベント直前の操作と状態遷移を確認し、ガード条件を追加してください。",
    "LATENCY_EXCEEDED": "処理区間を分離計測し、ボトルネックと予算超過の発生条件を特定してください。",
    "EVIDENCE_DROPPED": "テレメトリキューのdropを解消し、欠落のない証跡で再実施してください。",
    "TIME_LIMIT_EXCEEDED": "制限時間と実測ログを比較し、対象処理またはシナリオ前提を見直してください。",
    "USER_FAILED": (
        "ユーザーの記述と操作手順を照合し、再現条件を最小化して修正後に同じstepだけ再実施してください。"
    ),
    "OBSERVER_FAILED": "観察者の指摘を再現手順へ反映し、期待表示・操作結果との差分を修正してください。",
    "USER_BLOCKED": "実施できなかった環境条件を解消し、同じstepだけ再実施してください。",
    "MANUAL_VERDICT_MISSING": (
        "ユーザーまたは指定観察者に結果を入力してもらい、自己申告証拠として記録してください。"
    ),
}


class GuidedService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Session-bound bearer values live only in the API process. They are deliberately
        # absent from GuidedSession, SQLite, audit records, reports, and JSON APIs.
        self._human_attestations: dict[str, str] = {}

    def register_scenario(self, scenario: GuidedScenarioDefinition) -> GuidedScenarioDefinition:
        return save_scenario(scenario, now_ms())

    # Kept as a small compatibility alias for early callers of the prototype.
    register = register_scenario

    def scenario(self, scenario_id: str) -> GuidedScenarioDefinition:
        return load_scenario(scenario_id)

    def scenarios(self) -> list[GuidedScenarioDefinition]:
        return list_scenarios()

    def sessions(self, scenario_id: str | None = None) -> list[GuidedSession]:
        with self._lock:
            return [self._refresh(item) for item in list_sessions(scenario_id)]

    def start(self, request: GuidedSessionStart) -> GuidedSessionReceipt:
        with self._lock:
            scenario = load_scenario(request.scenarioId)
            ids = request.selectedStepIds or [step.id for step in scenario.steps]
            by_id = {step.id: step for step in scenario.steps}
            if any(step_id not in by_id for step_id in ids):
                raise ValueError("selectedStepIds contains an unknown scenario step")
            if len(ids) != len(set(ids)):
                raise ValueError("selectedStepIds must be unique")
            if not ids:
                raise ValueError("At least one guided step is required")
            if any(by_id[step_id].verdictAuthority == "observer" for step_id in ids) and not (
                request.observerAlias
            ):
                raise ValueError("observerAlias is required by one or more selected steps")
            attempt = 1
            if request.parentSessionId:
                parent = load_session(request.parentSessionId)
                if parent.scenarioId != scenario.id:
                    raise ValueError("Parent session belongs to another scenario")
                allowed = {
                    result.stepId for result in parent.results if result.status in {"FAILED", "BLOCKED"}
                }
                if not set(ids).issubset(allowed):
                    raise ValueError("A retest may contain failed or blocked parent steps only")
                attempt = parent.attempt + 1
            session = self._new_session(
                scenario,
                ids,
                request.operatorAlias,
                request.observerAlias,
                request.parentSessionId,
                attempt,
            )
            create_session(session)
            self._persist_human_attestation(session.id)
            append_audit(
                session.id,
                session.createdAtMs,
                "session_created",
                {"scenarioId": scenario.id, "selectedStepIds": ids},
            )
            return self._receipt(session)

    def get(self, session_id: str) -> GuidedSession:
        with self._lock:
            return self._refresh(load_session(session_id))

    def control(
        self,
        session_id: str,
        request: GuidedControlRequest,
        human_attestation_token: str | None = None,
    ) -> GuidedSession:
        with self._lock:
            session = self._refresh(load_session(session_id))
            if request.action in {"approve", "activate", "resume", "block", "abort"}:
                self._require_human_attestation(session.id, human_attestation_token)
            scenario = load_scenario(session.scenarioId)
            self._check_revision(session, request.expectedRevision)
            if request.action == "approve":
                self._approve(session)
            elif request.action == "activate":
                self._activate(session, request)
            elif request.action == "next":
                self._next(session, scenario)
            elif request.action == "retry":
                self._retry(session, scenario)
            elif request.action == "pause":
                self._pause(session)
            elif request.action == "resume":
                self._resume(session)
            elif request.action == "block":
                self._block(session, scenario, request.reason or "ユーザーが実施不能と判断しました。")
            elif request.action == "abort":
                self._abort(
                    session,
                    scenario,
                    request.reason or "ユーザーがセッションを中断しました。",
                )
            return self._persist(session, scenario)

    def feedback(
        self,
        session_id: str,
        verdict: GuidedManualVerdict,
        human_attestation_token: str | None = None,
    ) -> GuidedSession:
        with self._lock:
            session = self._refresh(load_session(session_id))
            self._require_human_attestation(session.id, human_attestation_token)
            scenario, step, result = self._current(session)
            if result.status not in {"ACTIVE", "AWAITING_FEEDBACK"}:
                raise InvalidTransition(
                    "A manual verdict is accepted only while the step awaits a human result"
                )
            if step.kind == "telemetry" and not step.feedbackRequired:
                raise InvalidTransition("This telemetry-only step does not accept a manual verdict")
            if result.manualVerdict is not None:
                raise InvalidTransition("A recorded human verdict is immutable; retry the step instead")
            self._validate_reporter(session, step, verdict)
            result.manualVerdict = verdict
            result.evidenceClass = (
                "OBSERVER_REPORTED" if verdict.reporterRole == "observer" else "SELF_REPORTED"
            )
            append_audit(
                session.id,
                now_ms(),
                "manual_verdict_submitted",
                {
                    "stepId": step.id,
                    "outcome": verdict.outcome,
                    "reporterRole": verdict.reporterRole,
                    "evidenceClass": result.evidenceClass,
                },
            )
            if verdict.outcome == "blocked":
                self._finish(
                    session,
                    scenario,
                    step,
                    result,
                    "BLOCKED",
                    ["USER_BLOCKED"],
                    [verdict.notes or "ユーザーまたは観察者が実施不能と報告しました。"],
                )
            elif verdict.outcome == "failed":
                code = "OBSERVER_FAILED" if verdict.reporterRole == "observer" else "USER_FAILED"
                self._finish(
                    session,
                    scenario,
                    step,
                    result,
                    "FAILED",
                    [code],
                    [verdict.notes or "人による確認で期待結果を満たさないと報告されました。"],
                )
            elif step.kind == "manual":
                self._finish(
                    session,
                    scenario,
                    step,
                    result,
                    "PASSED",
                    [],
                    [self._manual_pass_reason(verdict)],
                )
            elif result.telemetrySatisfied:
                result.evidenceClass = "HYBRID"
                self._finish(
                    session,
                    scenario,
                    step,
                    result,
                    "PASSED",
                    [],
                    ["テレメトリ条件と人による確認の両方を満たしました。"],
                )
            else:
                result.status = "ACTIVE"
                session.status = "RUNNING"
            return self._persist(session, scenario)

    def observe(self, session_id: str, observation: GuidedObservation) -> GuidedSession:
        with self._lock:
            session = self._refresh(load_session(session_id))
            if self._is_terminal(session):
                return session
            if session.status in {"PREPARED", "READY"}:
                # Pre-approval/pre-activation input is untrusted setup noise. Do not persist it,
                # count it, or update connection freshness.
                return session
            scenario = load_scenario(session.scenarioId)
            accepted = append_observation(session.id, observation)
            if not accepted:
                return session
            self._accept_observation(session, scenario, observation)
            append_audit(
                session.id,
                now_ms(),
                "observation_ingested",
                {"observationId": observation.id, "sequence": observation.sequence},
            )
            return self._persist(session, scenario)

    def observe_batch(self, session_id: str, batch: GuidedObservationBatch) -> GuidedObservationReceipt:
        with self._lock:
            session = self._refresh(load_session(session_id))
            if self._is_terminal(session):
                return GuidedObservationReceipt(
                    sessionId=session.id,
                    accepted=0,
                    duplicates=len(batch.observations),
                    revision=session.revision,
                    status=session.status,
                )
            if session.status in {"PREPARED", "READY"}:
                return GuidedObservationReceipt(
                    sessionId=session.id,
                    accepted=0,
                    duplicates=0,
                    revision=session.revision,
                    status=session.status,
                )
            scenario = load_scenario(session.scenarioId)
            accepted = 0
            duplicates = 0
            for observation in batch.observations:
                if self._is_terminal(session):
                    break
                if append_observation(session.id, observation):
                    accepted += 1
                    self._accept_observation(session, scenario, observation, defer_completion=True)
                else:
                    duplicates += 1
            if accepted and not self._is_terminal(session):
                _scenario, step, result = self._current(session)
                if result.status == "ACTIVE" and step.telemetryOracle is not None:
                    self._advance_settle_window(session, scenario, step, result)
            if accepted:
                append_audit(
                    session.id,
                    now_ms(),
                    "observation_batch_ingested",
                    {"accepted": accepted, "duplicates": duplicates},
                )
                session = self._persist(session, scenario)
            return GuidedObservationReceipt(
                sessionId=session.id,
                accepted=accepted,
                duplicates=duplicates,
                revision=session.revision,
                status=session.status,
            )

    def report(self, session_id: str) -> str:
        session = self.get(session_id)
        return self._render_report(session, load_scenario(session.scenarioId))

    def observations(self, session_id: str) -> list[GuidedObservation]:
        load_session(session_id)
        return observations_for_session(session_id)

    def next_instruction(self, session_id: str) -> dict[str, Any]:
        """Read-only payload intended for an AI guide or accessibility client."""
        session = self.get(session_id)
        scenario, step, result = self._current(session)
        return {
            "sessionId": session.id,
            "scenarioId": scenario.id,
            "sessionStatus": session.status,
            "revision": session.revision,
            "stepNumber": session.currentStepIndex + 1,
            "stepCount": len(session.results),
            "step": step.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
            "allowedActions": self._allowed_actions(session, result),
            "approvalRequired": session.status == "PREPARED",
            "humanVerdictCannotBeOverriddenByAi": True,
        }

    def runner_attestation_token(self, session_id: str) -> str:
        """Return the UI-only session token; never include it in structured API output."""
        with self._lock:
            session = load_session(session_id)
            if self._is_terminal(session):
                return ""
            token = self._human_attestations.get(session_id)
            stored_digest = load_attestation_digest(session_id)
            if token is not None and stored_digest is not None:
                token_digest = hashlib.sha256(token.encode()).hexdigest()
                if secrets.compare_digest(stored_digest, token_digest):
                    return token
            token = secrets.token_urlsafe(32)
            self._human_attestations[session_id] = token
            save_attestation_digest(session_id, hashlib.sha256(token.encode()).hexdigest(), now_ms())
            return token

    def _persist_human_attestation(self, session_id: str) -> None:
        token = self._human_attestations.get(session_id)
        if token is None:
            token = secrets.token_urlsafe(32)
            self._human_attestations[session_id] = token
        save_attestation_digest(session_id, hashlib.sha256(token.encode()).hexdigest(), now_ms())

    def _require_human_attestation(self, session_id: str, supplied: str | None) -> None:
        expected_digest = load_attestation_digest(session_id)
        supplied_digest = hashlib.sha256((supplied or "").encode()).hexdigest()
        if expected_digest is None or not secrets.compare_digest(expected_digest, supplied_digest):
            raise HumanAttestationRequired(
                "This action requires a valid attestation from the guided runner UI"
            )

    def _new_session(
        self,
        scenario: GuidedScenarioDefinition,
        step_ids: list[str],
        operator_alias: str,
        observer_alias: str | None,
        parent_session_id: str | None,
        attempt: int,
    ) -> GuidedSession:
        by_id = {step.id: step for step in scenario.steps}
        timestamp = now_ms()
        session = GuidedSession(
            id=f"guided-{uuid.uuid4().hex}",
            scenarioId=scenario.id,
            projectId=scenario.projectId,
            operatorAlias=operator_alias,
            observerAlias=observer_alias,
            selectedStepIds=step_ids,
            parentSessionId=parent_session_id,
            attempt=attempt,
            scenarioSha256=self._scenario_sha(scenario),
            createdAtMs=timestamp,
            updatedAtMs=timestamp,
            results=[GuidedStepResult(stepId=step_id, kind=by_id[step_id].kind) for step_id in step_ids],
        )
        self._human_attestations[session.id] = secrets.token_urlsafe(32)
        return self._with_gate(session, scenario)

    @staticmethod
    def _scenario_sha(scenario: GuidedScenarioDefinition) -> str:
        body = json.dumps(
            scenario.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(body).hexdigest()

    @staticmethod
    def _receipt(session: GuidedSession) -> GuidedSessionReceipt:
        return GuidedSessionReceipt(
            session=session,
            runnerUrl=f"/guided/{session.id}",
            telemetryEndpoint=f"/api/v1/guided/sessions/{session.id}/observations:batch",
        )

    def _refresh(self, session: GuidedSession) -> GuidedSession:
        scenario = load_scenario(session.scenarioId)
        if session.status in {"RUNNING", "AWAITING_FEEDBACK"}:
            _scenario, step, result = self._current(session)
            if (
                session.status == "RUNNING"
                and result.status == "ACTIVE"
                and step.telemetryOracle is not None
                and self._advance_settle_window(session, scenario, step, result)
            ):
                return self._persist(session, scenario)
            if (
                session.status == "RUNNING"
                and result.status == "ACTIVE"
                and step.kind != "manual"
                and self._elapsed_ms(result) >= step.timeoutMs
            ):
                self._timeout(session, scenario, step, result)
                return self._persist(session, scenario)
        return self._with_gate(session, scenario)

    @staticmethod
    def _check_revision(session: GuidedSession, expected: int | None) -> None:
        if expected is not None and expected != session.revision:
            raise RevisionConflict(f"Expected revision {expected}, current revision is {session.revision}")

    @staticmethod
    def _approve(session: GuidedSession) -> None:
        if session.status != "PREPARED":
            raise InvalidTransition("Only a PREPARED session can be approved")
        session.approvedAtMs = now_ms()
        session.status = "READY"
        append_audit(session.id, session.approvedAtMs, "session_approved", {})

    def _activate(self, session: GuidedSession, request: GuidedControlRequest) -> None:
        if session.status != "READY":
            raise InvalidTransition("The session is not READY for activation")
        _scenario, step, result = self._current(session)
        if result.status != "PENDING":
            raise InvalidTransition("The current step is already consumed")
        missing = sorted(set(step.requiredConditions) - set(request.confirmedConditions))
        if missing:
            raise ValueError(f"Required conditions not confirmed: {', '.join(missing)}")
        result.status = "ACTIVE"
        result.startedAtMs = now_ms()
        result.confirmedConditions = sorted(set(request.confirmedConditions))
        session.status = "RUNNING"
        append_audit(session.id, result.startedAtMs, "step_activated", {"stepId": step.id})

    def _next(self, session: GuidedSession, scenario: GuidedScenarioDefinition) -> None:
        _scenario, _step, result = self._current(session)
        if result.status not in {"PASSED", "FAILED", "BLOCKED"}:
            raise InvalidTransition("Complete or block the current step before continuing")
        if session.currentStepIndex + 1 >= len(session.results):
            self._finalize(session, scenario)
            return
        session.currentStepIndex += 1
        session.status = "READY"
        append_audit(
            session.id,
            now_ms(),
            "next_step_ready",
            {"stepId": session.results[session.currentStepIndex].stepId},
        )

    def _retry(self, session: GuidedSession, scenario: GuidedScenarioDefinition) -> None:
        _scenario, step, result = self._current(session)
        if result.status not in {"FAILED", "BLOCKED"}:
            raise InvalidTransition("Only failed or blocked steps can be retried")
        write_step_evidence(
            session.id,
            step.id,
            result.attempt,
            {"step": step.model_dump(mode="json"), "retrySource": result.model_dump(mode="json")},
        )
        session.results[session.currentStepIndex] = GuidedStepResult(
            stepId=step.id, kind=step.kind, attempt=result.attempt + 1
        )
        session.status = "READY"
        append_audit(
            session.id,
            now_ms(),
            "step_retry_ready",
            {"stepId": step.id, "attempt": result.attempt + 1},
        )

    def _pause(self, session: GuidedSession) -> None:
        if session.status != "RUNNING":
            raise InvalidTransition("Only a RUNNING session can be paused")
        _scenario, step, result = self._current(session)
        if result.status != "ACTIVE":
            raise InvalidTransition("The current step cannot be paused")
        result.status = "PAUSED"
        result.pausedAtMs = now_ms()
        session.status = "PAUSED"
        append_audit(session.id, result.pausedAtMs, "step_paused", {"stepId": step.id})

    def _resume(self, session: GuidedSession) -> None:
        if session.status != "PAUSED":
            raise InvalidTransition("Only a PAUSED session can be resumed")
        _scenario, step, result = self._current(session)
        if result.status != "PAUSED" or result.pausedAtMs is None:
            raise InvalidTransition("The current step is not paused")
        timestamp = now_ms()
        paused_duration = timestamp - result.pausedAtMs
        result.accumulatedPauseMs += paused_duration
        if result.settleStartedAtMs is not None:
            result.settleStartedAtMs += paused_duration
        if result.settleDeadlineMs is not None:
            result.settleDeadlineMs += paused_duration
        result.pausedAtMs = None
        result.status = "ACTIVE"
        session.status = "RUNNING"
        append_audit(session.id, timestamp, "step_resumed", {"stepId": step.id})

    def _block(
        self,
        session: GuidedSession,
        scenario: GuidedScenarioDefinition,
        reason: str,
    ) -> None:
        _scenario, step, result = self._current(session)
        if result.status not in {"PENDING", "ACTIVE", "PAUSED", "AWAITING_FEEDBACK"}:
            raise InvalidTransition("The current step is already terminal")
        if result.evidenceClass == "UNKNOWN":
            result.evidenceClass = "SELF_REPORTED"
        self._finish(session, scenario, step, result, "BLOCKED", ["USER_BLOCKED"], [reason])

    def _abort(self, session: GuidedSession, scenario: GuidedScenarioDefinition, reason: str) -> None:
        if session.status in {"COMPLETED", "FAILED", "BLOCKED", "ABORTED"}:
            raise InvalidTransition("The session is already terminal")
        for result in session.results:
            if result.status in {"PENDING", "ACTIVE", "PAUSED", "AWAITING_FEEDBACK"}:
                result.status = "BLOCKED"
                result.failureCodes = ["USER_BLOCKED"]
                result.verdictReasons = [reason]
                result.correctionSuggestions = [_SUGGESTIONS["USER_BLOCKED"]]
                if result.evidenceClass == "UNKNOWN":
                    result.evidenceClass = "SELF_REPORTED"
        session.status = "ABORTED"
        append_audit(session.id, now_ms(), "session_aborted", {"reason": reason})
        self._ensure_retest(session, scenario)

    def _accept_observation(
        self,
        session: GuidedSession,
        scenario: GuidedScenarioDefinition,
        observation: GuidedObservation,
        *,
        defer_completion: bool = False,
    ) -> None:
        # Connection freshness is a server-side ingestion timestamp. The adapter timestamp
        # remains unchanged inside the observation evidence and may use another clock domain.
        session.lastObservationAtMs = now_ms()
        if session.status not in {"RUNNING", "AWAITING_FEEDBACK"}:
            return
        _scenario, step, result = self._current(session)
        if result.status not in {"ACTIVE", "AWAITING_FEEDBACK"} or step.telemetryOracle is None:
            return
        result.observationIds.append(observation.id)
        self._consume_telemetry(
            session,
            scenario,
            step,
            result,
            observation,
            defer_completion=defer_completion,
        )

    def _consume_telemetry(
        self,
        session: GuidedSession,
        scenario: GuidedScenarioDefinition,
        step: GuidedScenarioStep,
        result: GuidedStepResult,
        observation: GuidedObservation,
        *,
        defer_completion: bool = False,
    ) -> None:
        oracle = step.telemetryOracle
        if oracle is None:
            return
        settle_was_active = result.settleStartedAtMs is not None and not result.telemetrySatisfied
        result.observationCount += 1
        if result.initialDrops is None:
            result.initialDrops = observation.drops
        result.dropDelta = max(result.dropDelta, observation.drops - result.initialDrops)
        if observation.event:
            result.eventCounts[observation.event] = result.eventCounts.get(observation.event, 0) + 1
        if observation.latencyMs is not None:
            result.latencySamplesMs.append(observation.latencyMs)
            result.latencySamplesMs = result.latencySamplesMs[-20_000:]
            result.p95LatencyMs = _percentile(result.latencySamplesMs, 95)

        if observation.event in oracle.forbiddenEvents:
            self._finish(
                session,
                scenario,
                step,
                result,
                "FAILED",
                ["FORBIDDEN_EVENT"],
                [f"禁止イベント {observation.event} を観測しました。"],
            )
            return
        limit_codes, limit_reasons = self._event_limit_failures(result, oracle)
        if limit_codes:
            self._finish(session, scenario, step, result, "FAILED", limit_codes, limit_reasons)
            return
        if result.dropDelta > oracle.maxDropDelta:
            self._finish(session, scenario, step, result, "FAILED", ["EVIDENCE_DROPPED"], [])
            return
        if (
            oracle.maxP95LatencyMs is not None
            and result.observationCount >= oracle.minObservations
            and result.p95LatencyMs is not None
            and result.p95LatencyMs > oracle.maxP95LatencyMs
        ):
            self._finish(session, scenario, step, result, "FAILED", ["LATENCY_EXCEEDED"], [])
            return
        if result.status == "AWAITING_FEEDBACK":
            # Once the stability window is complete, the user may move away to answer.
            # Continue only invariant/event/evidence monitoring; do not mutate predicate,
            # consecutive-match, or settle state based on that expected movement.
            return
        matched = all(self._predicate_matches(observation, predicate) for predicate in oracle.predicates)
        if matched:
            result.matchingObservations += 1
            result.consecutiveMatches += 1
            result.peakConsecutiveMatches = max(result.peakConsecutiveMatches, result.consecutiveMatches)
        else:
            result.mismatches += 1
            result.consecutiveMatches = 0
        constrained_events = {
            *oracle.requiredEvents,
            *oracle.exactEventCounts,
            *oracle.maxEventCounts,
        }
        if settle_was_active and (
            not matched or (observation.event is not None and observation.event in constrained_events)
        ):
            result.settleStartedAtMs = None
            result.settleDeadlineMs = None
        if result.mismatches > oracle.maxMismatches:
            self._finish(session, scenario, step, result, "FAILED", ["PREDICATE_MISMATCH"], [])
            return
        if not defer_completion:
            self._advance_settle_window(session, scenario, step, result)

    def _advance_settle_window(
        self,
        session: GuidedSession,
        scenario: GuidedScenarioDefinition,
        step: GuidedScenarioStep,
        result: GuidedStepResult,
    ) -> bool:
        oracle = step.telemetryOracle
        if oracle is None or result.telemetrySatisfied:
            return False
        timestamp = now_ms()
        if not self._oracle_satisfied(result, oracle, self._elapsed_ms(result, timestamp)):
            changed = result.settleStartedAtMs is not None or result.settleDeadlineMs is not None
            result.settleStartedAtMs = None
            result.settleDeadlineMs = None
            return changed
        changed = False
        if result.settleStartedAtMs is None:
            result.settleStartedAtMs = timestamp
            result.settleDeadlineMs = timestamp + oracle.settleWindowMs
            changed = True
        if result.settleDeadlineMs is not None and timestamp < result.settleDeadlineMs:
            return changed
        result.telemetrySatisfied = True
        self._complete_telemetry_phase(session, scenario, step, result, oracle)
        return True

    def _complete_telemetry_phase(
        self,
        session: GuidedSession,
        scenario: GuidedScenarioDefinition,
        step: GuidedScenarioStep,
        result: GuidedStepResult,
        oracle: GuidedTelemetryOracle,
    ) -> None:
        if step.kind == "telemetry" and not step.feedbackRequired:
            result.evidenceClass = "TELEMETRY"
            self._finish(
                session,
                scenario,
                step,
                result,
                "PASSED",
                [],
                [f"テレメトリオラクル {oracle.name} の条件を満たしました。"],
            )
        elif result.manualVerdict and result.manualVerdict.outcome == "passed":
            result.evidenceClass = "HYBRID"
            self._finish(
                session,
                scenario,
                step,
                result,
                "PASSED",
                [],
                ["テレメトリ条件と人による確認の両方を満たしました。"],
            )
        else:
            result.status = "AWAITING_FEEDBACK"
            session.status = "AWAITING_FEEDBACK"

    @staticmethod
    def _event_limit_failures(
        result: GuidedStepResult, oracle: GuidedTelemetryOracle
    ) -> tuple[list[str], list[str]]:
        codes: list[str] = []
        reasons: list[str] = []
        exact_excess = [
            (name, result.eventCounts.get(name, 0), expected)
            for name, expected in oracle.exactEventCounts.items()
            if result.eventCounts.get(name, 0) > expected
        ]
        if exact_excess:
            codes.append("EXACT_EVENT_COUNT_MISMATCH")
            reasons.extend(
                f"イベント {name} は exact={expected} に対して {actual} 回観測されました。"
                for name, actual, expected in exact_excess
            )
        maximum_excess = [
            (name, result.eventCounts.get(name, 0), maximum)
            for name, maximum in oracle.maxEventCounts.items()
            if result.eventCounts.get(name, 0) > maximum
        ]
        if maximum_excess:
            codes.append("MAX_EVENT_COUNT_EXCEEDED")
            reasons.extend(
                f"イベント {name} は max={maximum} を超えて {actual} 回観測されました。"
                for name, actual, maximum in maximum_excess
            )
        return codes, reasons

    @staticmethod
    def _oracle_satisfied(result: GuidedStepResult, oracle: GuidedTelemetryOracle, elapsed_ms: int) -> bool:
        if result.observationCount < oracle.minObservations:
            return False
        if elapsed_ms < oracle.minObservationMs:
            return False
        if result.matchingObservations < oracle.minMatchingObservations:
            return False
        if oracle.minConsecutiveMatches and result.consecutiveMatches < oracle.minConsecutiveMatches:
            return False
        if any(result.eventCounts.get(name, 0) < count for name, count in oracle.requiredEvents.items()):
            return False
        if any(result.eventCounts.get(name, 0) != count for name, count in oracle.exactEventCounts.items()):
            return False
        if any(result.eventCounts.get(name, 0) > count for name, count in oracle.maxEventCounts.items()):
            return False
        if result.dropDelta > oracle.maxDropDelta:
            return False
        if oracle.maxP95LatencyMs is not None and (
            result.p95LatencyMs is None or result.p95LatencyMs > oracle.maxP95LatencyMs
        ):
            return False
        return True

    @staticmethod
    def _predicate_matches(observation: GuidedObservation, predicate: GuidedTelemetryPredicate) -> bool:
        document = observation.model_dump(mode="python")
        missing = object()
        current: Any = document
        for part in predicate.path.split("."):
            if not isinstance(current, dict) or part not in current:
                current = missing
                break
            current = current[part]
        operator = predicate.operator
        expected = predicate.value
        if operator == "exists":
            return (current is not missing) is bool(expected if expected is not None else True)
        if current is missing:
            return False
        try:
            if operator == "eq":
                return current == expected
            if operator == "ne":
                return current != expected
            if operator == "in":
                return current in expected
            if operator == "not_in":
                return current not in expected
            if operator == "gte":
                return current >= expected
            if operator == "lte":
                return current <= expected
            if operator == "contains":
                return expected in current
        except (TypeError, ValueError):
            return False
        return False

    def _timeout(
        self,
        session: GuidedSession,
        scenario: GuidedScenarioDefinition,
        step: GuidedScenarioStep,
        result: GuidedStepResult,
    ) -> None:
        if result.observationCount == 0:
            self._finish(session, scenario, step, result, "BLOCKED", ["NO_TELEMETRY"], [])
            return
        oracle = step.telemetryOracle
        codes: list[str] = ["TIME_LIMIT_EXCEEDED"]
        if oracle:
            if result.matchingObservations < oracle.minMatchingObservations:
                codes.append("ORACLE_NOT_SATISFIED")
            if any(result.eventCounts.get(name, 0) < count for name, count in oracle.requiredEvents.items()):
                codes.append("REQUIRED_EVENT_MISSING")
            if any(
                result.eventCounts.get(name, 0) != count for name, count in oracle.exactEventCounts.items()
            ):
                codes.append("EXACT_EVENT_COUNT_MISMATCH")
            if any(result.eventCounts.get(name, 0) > count for name, count in oracle.maxEventCounts.items()):
                codes.append("MAX_EVENT_COUNT_EXCEEDED")
            if result.settleStartedAtMs is not None and not result.telemetrySatisfied:
                codes.append("SETTLE_WINDOW_INCOMPLETE")
            if oracle.maxP95LatencyMs is not None and (
                result.p95LatencyMs is None or result.p95LatencyMs > oracle.maxP95LatencyMs
            ):
                codes.append("LATENCY_EXCEEDED")
        self._finish(
            session,
            scenario,
            step,
            result,
            "FAILED",
            codes,
            [f"{result.observationCount}件を観測しましたが、制限時間内に要件を満たしませんでした。"],
        )

    def _finish(
        self,
        session: GuidedSession,
        scenario: GuidedScenarioDefinition,
        step: GuidedScenarioStep,
        result: GuidedStepResult,
        status: str,
        codes: list[str],
        reasons: list[str],
    ) -> None:
        timestamp = now_ms()
        if result.pausedAtMs is not None:
            result.accumulatedPauseMs += timestamp - result.pausedAtMs
            result.pausedAtMs = None
        result.status = status  # type: ignore[assignment]
        result.endedAtMs = timestamp
        result.durationMs = self._elapsed_ms(result, timestamp)
        result.failureCodes = list(dict.fromkeys(codes))
        result.verdictReasons = reasons or (
            ["失敗要因を証跡から確認してください。"] if status != "PASSED" else []
        )
        result.correctionSuggestions = list(
            dict.fromkeys(_SUGGESTIONS[code] for code in result.failureCodes if code in _SUGGESTIONS)
        )
        if step.telemetryOracle is not None and result.observationCount > 0:
            if result.manualVerdict is not None:
                result.evidenceClass = "HYBRID"
            elif result.evidenceClass == "UNKNOWN":
                result.evidenceClass = "TELEMETRY"
        observation_ids = set(result.observationIds)
        evidence_observations = [
            item.model_dump(mode="json")
            for item in observations_for_session(session.id)
            if item.id in observation_ids
        ]
        path, digest = write_step_evidence(
            session.id,
            step.id,
            result.attempt,
            {
                "sessionId": session.id,
                "scenarioId": scenario.id,
                "scenarioSha256": session.scenarioSha256,
                "step": step.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
                "observations": evidence_observations,
            },
        )
        result.evidencePath = path
        result.evidenceSha256 = digest
        session.status = "STEP_COMPLETE"
        append_audit(
            session.id,
            timestamp,
            "step_finished",
            {
                "stepId": step.id,
                "status": status,
                "evidenceClass": result.evidenceClass,
                "failureCodes": result.failureCodes,
                "evidenceSha256": digest,
            },
        )
        if session.currentStepIndex + 1 >= len(session.results):
            self._finalize(session, scenario)

    def _finalize(self, session: GuidedSession, scenario: GuidedScenarioDefinition) -> None:
        statuses = [result.status for result in session.results]
        if any(status == "FAILED" for status in statuses):
            session.status = "FAILED"
        elif any(status == "BLOCKED" for status in statuses):
            session.status = "BLOCKED"
        elif all(status == "PASSED" for status in statuses):
            session.status = "COMPLETED"
        else:
            session.status = "BLOCKED"
        self._ensure_retest(session, scenario)
        append_audit(session.id, now_ms(), "session_finalized", {"status": session.status})

    def _ensure_retest(self, session: GuidedSession, scenario: GuidedScenarioDefinition) -> None:
        retry_ids = [result.stepId for result in session.results if result.status in {"FAILED", "BLOCKED"}]
        if retry_ids and not session.retestSessionId:
            retest = self._new_session(
                scenario,
                retry_ids,
                session.operatorAlias,
                session.observerAlias,
                session.id,
                session.attempt + 1,
            )
            create_session(retest)
            self._persist_human_attestation(retest.id)
            append_audit(
                retest.id,
                retest.createdAtMs,
                "retest_prepared",
                {"parentSessionId": session.id, "stepIds": retry_ids},
            )
            session.retestSessionId = retest.id

    def _persist(self, session: GuidedSession, scenario: GuidedScenarioDefinition) -> GuidedSession:
        session.updatedAtMs = now_ms()
        session = self._with_gate(session, scenario)
        session = save_session(session)
        report_path, report_digest = write_report(session.id, self._render_report(session, scenario))
        evidence_path, evidence_digest = write_session_evidence(
            session.id,
            {
                "session": session.model_dump(mode="json"),
                "scenarioSha256": session.scenarioSha256,
                "observations": [
                    item.model_dump(mode="json") for item in observations_for_session(session.id)
                ],
                "audit": audits_for_session(session.id),
            },
        )
        session.reportPath = report_path
        session.reportSha256 = report_digest
        session.sessionEvidencePath = evidence_path
        session.sessionEvidenceSha256 = evidence_digest
        session.updatedAtMs = now_ms()
        session = save_session(session)
        if self._is_terminal(session):
            delete_attestation_digest(session.id)
            self._human_attestations.pop(session.id, None)
        return session

    def _with_gate(self, session: GuidedSession, scenario: GuidedScenarioDefinition) -> GuidedSession:
        by_id = {step.id: step for step in scenario.steps}
        normalized = []
        for result in session.results:
            step = by_id[result.stepId]
            terminal_status = result.status if result.status in {"PASSED", "FAILED", "BLOCKED"} else "BLOCKED"
            test_type = step.testType
            if test_type == "guided-user":
                test_type = f"guided-user-{step.kind}"
            if result.evidenceClass == "SELF_REPORTED":
                oracle = "self-report:user"
            elif result.evidenceClass == "OBSERVER_REPORTED":
                oracle = "observer-report:human"
            elif result.evidenceClass == "HYBRID":
                oracle = f"hybrid:human+{step.telemetryOracle.name if step.telemetryOracle else 'telemetry'}"
            elif step.telemetryOracle:
                oracle = f"telemetry:{step.telemetryOracle.name}"
            else:
                oracle = "human-verdict-pending"
            normalized.append(
                {
                    "testId": result.stepId,
                    "testType": test_type,
                    "status": terminal_status,
                    "severity": step.severity,
                    "criticalFlow": step.criticalFlow,
                    "durationMs": result.durationMs,
                    "retryCount": max(0, result.attempt - 1),
                    "errorMessage": "; ".join(result.verdictReasons)
                    if terminal_status in {"FAILED", "BLOCKED"}
                    else None,
                    "sampleCount": result.observationCount or None,
                    "evidencePath": result.evidencePath,
                    "evidenceSha256": result.evidenceSha256,
                    "oracle": oracle,
                    "deterministic": result.evidenceClass == "TELEMETRY",
                }
            )
        gate = evaluate_quality_gate(
            QualityGateRequest(
                profileId=f"guided-{scenario.projectId}",
                mode=scenario.gateMode,
                results=normalized,
                requiredTestTypes=sorted({item["testType"] for item in normalized}),
            )
        )
        human_evidence = any(
            result.evidenceClass in {"SELF_REPORTED", "OBSERVER_REPORTED", "HYBRID"}
            and result.status == "PASSED"
            for result in session.results
        )
        warnings = list(gate.warnings)
        boundary_warning = (
            "Guided QAはユーザーテスト用の補助証拠であり、自動テストまたはリリースゲートの代替ではない"
        )
        if boundary_warning not in warnings:
            warnings.append(boundary_warning)
        decision = gate.decision
        if human_evidence and gate.decision in {"PASS", "PASS_WITH_WARNING"}:
            decision = "MANUAL_REVIEW"
            human_warning = "ユーザーテストの合格は人による証拠を含むため自動リリース不可"
            if human_warning not in warnings:
                warnings.append(human_warning)
        gate = QualityGateResponse(
            profileId=gate.profileId,
            decision=decision,
            passRatePercent=gate.passRatePercent,
            counts=gate.counts,
            blockers=gate.blockers,
            warnings=warnings,
            releaseRecommended=False,
            humanApprovalRequired=True,
        )
        session.gate = gate
        return session

    def _current(
        self, session: GuidedSession
    ) -> tuple[GuidedScenarioDefinition, GuidedScenarioStep, GuidedStepResult]:
        scenario = load_scenario(session.scenarioId)
        result = session.results[session.currentStepIndex]
        step = next(step for step in scenario.steps if step.id == result.stepId)
        return scenario, step, result

    @staticmethod
    def _validate_reporter(
        session: GuidedSession,
        step: GuidedScenarioStep,
        verdict: GuidedManualVerdict,
    ) -> None:
        if step.verdictAuthority != "either" and verdict.reporterRole != step.verdictAuthority:
            raise InvalidTransition(f"This step requires a {step.verdictAuthority} verdict")
        if verdict.reporterRole == "observer" and not session.observerAlias:
            raise InvalidTransition("An observerAlias is required for observer verdicts")

    @staticmethod
    def _manual_pass_reason(verdict: GuidedManualVerdict) -> str:
        label = "観察者報告" if verdict.reporterRole == "observer" else "ユーザー自己申告"
        return f"{label}で期待結果を満たしたと記録しました。自動テスト合格とは区別されます。"

    @staticmethod
    def _allowed_actions(session: GuidedSession, result: GuidedStepResult) -> list[str]:
        if session.status == "PREPARED":
            return ["approve", "abort"]
        if session.status == "READY":
            return ["activate", "block", "abort"]
        if session.status == "RUNNING":
            return ["pause", "block", "abort", "submit_manual_verdict"]
        if session.status == "PAUSED":
            return ["resume", "block", "abort"]
        if session.status == "AWAITING_FEEDBACK":
            return ["submit_manual_verdict", "block", "abort"]
        if result.status in {"PASSED", "FAILED", "BLOCKED"} and session.status == "STEP_COMPLETE":
            return ["next", "retry"] if result.status in {"FAILED", "BLOCKED"} else ["next"]
        return []

    @staticmethod
    def _is_terminal(session: GuidedSession) -> bool:
        return session.status in {"COMPLETED", "FAILED", "BLOCKED", "ABORTED"}

    @staticmethod
    def _elapsed_ms(result: GuidedStepResult, timestamp: int | None = None) -> int:
        if result.startedAtMs is None:
            return 0
        end = timestamp or now_ms()
        current_pause = end - result.pausedAtMs if result.pausedAtMs is not None else 0
        return max(0, end - result.startedAtMs - result.accumulatedPauseMs - current_pause)

    @staticmethod
    def _render_report(session: GuidedSession, scenario: GuidedScenarioDefinition) -> str:
        lines = [
            f"# Guided user QA report: {scenario.title}",
            "",
            "> This report is a human-guided user-test record. It is separate from automated tests.",
            "> SELF_REPORTED / OBSERVER_REPORTED / HYBRID passes require manual review "
            "and never auto-release.",
            "> TELEMETRY inside a guided session is supporting evidence only and also never "
            "authorizes release.",
            "",
            f"- Session: `{session.id}`",
            f"- Scenario SHA-256: `{session.scenarioSha256}`",
            f"- Attempt: `{session.attempt}`",
            f"- Operator: `{session.operatorAlias}`",
            f"- Observer: `{session.observerAlias or 'none'}`",
            f"- Status: **{session.status}**",
            f"- Gate: **{session.gate.decision if session.gate else 'BLOCKED'}**",
            f"- Auto release: **{'YES' if session.gate and session.gate.releaseRecommended else 'NO'}**",
            "",
            "## Step results",
            "",
        ]
        for result in session.results:
            lines.extend(
                [
                    f"### `{result.stepId}` — {result.status}",
                    f"- kind: `{result.kind}`, evidence class: `{result.evidenceClass}`",
                    f"- observations: {result.observationCount}, "
                    f"matches: {result.matchingObservations}, mismatches: {result.mismatches}",
                    f"- events: `{result.eventCounts}`",
                    f"- p95 latency: `{result.p95LatencyMs}` ms, drop delta: `{result.dropDelta}`",
                    "- manual verdict: `"
                    f"{result.manualVerdict.model_dump(mode='json') if result.manualVerdict else 'none'}`",
                    f"- failure codes: `{', '.join(result.failureCodes) or 'none'}`",
                    f"- evidence: `{result.evidencePath or 'not yet written'}` "
                    f"sha256=`{result.evidenceSha256 or 'n/a'}`",
                    "",
                ]
            )
            lines.extend(f"- 修正案: {suggestion}" for suggestion in result.correctionSuggestions)
        if session.retestSessionId:
            lines.extend(
                [
                    "",
                    "## Retest prepared",
                    "",
                    f"`{session.retestSessionId}` — failed/blocked steps only; status PREPARED.",
                ]
            )
        return "\n".join(lines) + "\n"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((percentile / 100) * (len(ordered) - 1))))
    return round(float(ordered[index]), 3)


service = GuidedService()
guided_service = service
