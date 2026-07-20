from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import guided_api, guided_storage, mcp_server
from app.guided_models import GuidedMedia, GuidedScenarioDefinition, GuidedVisualMarker
from app.main import app

client = TestClient(app)
ATTESTATION_HEADER = "X-EagleEye-Human-Attestation"


@pytest.fixture(autouse=True)
def isolated_guided_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "data" / "guided.sqlite3"
    runs = tmp_path / "artifacts"
    assets = tmp_path / "assets"
    monkeypatch.setattr(guided_storage, "DATABASE", database)
    monkeypatch.setattr(guided_storage, "GUIDED_RUNS", runs)
    monkeypatch.setattr(guided_storage, "GUIDED_ASSETS", assets)
    monkeypatch.setattr(guided_api, "GUIDED_ASSETS", assets)


def manual_step(step_id: str = "manual-one", authority: str = "user") -> dict:
    return {
        "id": step_id,
        "kind": "manual",
        "title": f"Manual {step_id}",
        "guidance": {
            "text": "案内された操作を行ってください。",
            "markers": [
                {
                    "shape": "point",
                    "x": 0.5,
                    "y": 0.5,
                    "label": "ここ",
                    "color": "#38d7c4",
                }
            ],
        },
        "preparation": "対象画面を開いてください。",
        "expected": "期待した画面になること。",
        "requirementIds": ["REQ-1"],
        "requiredConditions": ["対象画面を表示した"],
        "verdictAuthority": authority,
        "timeoutMs": 60_000,
    }


def telemetry_step(step_id: str = "telemetry-one", kind: str = "telemetry") -> dict:
    return {
        "id": step_id,
        "kind": kind,
        "title": f"Telemetry {step_id}",
        "guidance": {"text": "対象操作を行ってください。"},
        "expected": "ready状態とsavedイベントが観測されること。",
        "requirementIds": ["REQ-1"],
        "timeoutMs": 60_000,
        "verdictAuthority": "user",
        "telemetryOracle": {
            "name": "generic-state-oracle",
            "minObservations": 2,
            "predicates": [{"path": "values.state", "operator": "eq", "value": "ready"}],
            "minMatchingObservations": 2,
            "minConsecutiveMatches": 2,
            "maxMismatches": 0,
            "requiredEvents": {"saved": 1},
            "forbiddenEvents": ["fatal"],
            "maxP95LatencyMs": 100,
            "maxDropDelta": 0,
        },
    }


def scenario(steps: list[dict], scenario_id: str = "generic-guided-test") -> dict:
    return {
        "schemaVersion": "1.0",
        "id": scenario_id,
        "projectId": "generic-project",
        "title": "Generic guided user test",
        "description": "A product-neutral guided scenario.",
        "version": "1.0.0",
        "targetSource": "generic local UI",
        "safetyNotice": "テスト用データだけを使用してください。",
        "privacyNotice": "回答と構造化telemetryを保存します。",
        "requirements": [{"id": "REQ-1", "text": "対象フローを利用できること。"}],
        "steps": steps,
        "gateMode": "standard",
    }


def register(payload: dict) -> dict:
    response = client.post("/api/v1/guided/scenarios", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def prepare(scenario_id: str, observer: str | None = None) -> dict:
    payload = {"scenarioId": scenario_id, "operatorAlias": "tester"}
    if observer:
        payload["observerAlias"] = observer
    response = client.post("/api/v1/guided/sessions", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def runner_token(session: dict | str) -> str:
    session_id = session if isinstance(session, str) else session["id"]
    response = client.get(f"/guided/{session_id}")
    assert response.status_code == 200
    marker = "ATTESTATION="
    start = response.text.find(marker)
    end = response.text.find(";let state=", start)
    assert start >= 0 and end > start, "runner did not embed a human attestation token"
    return str(json.loads(response.text[start + len(marker) : end]))


def attestation_headers(session: dict | str) -> dict[str, str]:
    return {ATTESTATION_HEADER: runner_token(session)}


def control(session: dict, action: str, **extra: object) -> dict:
    payload = {"action": action, "expectedRevision": session["revision"], **extra}
    response = client.post(
        f"/api/v1/guided/sessions/{session['id']}/control",
        json=payload,
        headers=attestation_headers(session),
    )
    assert response.status_code == 200, response.text
    return response.json()


def activate(session: dict, conditions: list[str] | None = None) -> dict:
    session = control(session, "approve")
    return control(session, "activate", confirmedConditions=conditions or [])


def submit_verdict(
    session: dict,
    outcome: str,
    role: str = "user",
    notes: str = "",
) -> dict:
    response = client.post(
        f"/api/v1/guided/sessions/{session['id']}/feedback",
        json={
            "outcome": outcome,
            "reporterRole": role,
            "difficultyRating": 2,
            "confidenceRating": 5,
            "notes": notes,
        },
        headers=attestation_headers(session),
    )
    assert response.status_code == 200, response.text
    return response.json()


def observation(obs_id: str, sequence: int, event: str | None = None) -> dict:
    return {
        "id": obs_id,
        "sequence": sequence,
        "timestampMs": 1_800_000_000_000 + sequence,
        "source": "generic-adapter",
        "kind": "event" if event else "sample",
        "event": event,
        "values": {"state": "ready"},
        "latencyMs": 12.5,
        "drops": 0,
        "payload": {"adapterVersion": "1"},
    }


def test_manual_flow_requires_approval_supports_pause_and_never_auto_releases() -> None:
    register(scenario([manual_step()]))
    receipt = prepare("generic-guided-test")
    session = receipt["session"]
    assert session["status"] == "PREPARED"
    assert receipt["runnerUrl"].endswith(session["id"])

    premature = client.post(
        f"/api/v1/guided/sessions/{session['id']}/control",
        json={"action": "activate", "expectedRevision": session["revision"]},
        headers=attestation_headers(session),
    )
    assert premature.status_code == 409

    session = control(session, "approve")
    assert session["status"] == "READY"
    stale = client.post(
        f"/api/v1/guided/sessions/{session['id']}/control",
        json={"action": "activate", "expectedRevision": 0},
        headers=attestation_headers(session),
    )
    assert stale.status_code == 409
    session = control(
        session,
        "activate",
        confirmedConditions=["対象画面を表示した"],
    )
    session = control(session, "pause")
    assert session["status"] == "PAUSED"
    session = control(session, "resume")
    assert session["status"] == "RUNNING"

    session = submit_verdict(session, "passed", notes="期待どおり")
    result = session["results"][0]
    assert session["status"] == "COMPLETED"
    assert result["status"] == "PASSED"
    assert result["evidenceClass"] == "SELF_REPORTED"
    assert result["manualVerdict"]["notes"] == "期待どおり"
    assert session["gate"]["decision"] == "MANUAL_REVIEW"
    assert session["gate"]["humanApprovalRequired"] is True
    assert session["gate"]["releaseRecommended"] is False
    assert result["evidenceSha256"] == hashlib.sha256(Path(result["evidencePath"]).read_bytes()).hexdigest()
    assert session["reportSha256"] == hashlib.sha256(Path(session["reportPath"]).read_bytes()).hexdigest()
    assert (
        session["sessionEvidenceSha256"]
        == hashlib.sha256(Path(session["sessionEvidencePath"]).read_bytes()).hexdigest()
    )
    report = client.get(f"/api/v1/guided/sessions/{session['id']}/report").text
    assert "separate from automated tests" in report
    assert "SELF_REPORTED" in report


def test_telemetry_batch_is_idempotent_but_never_authorizes_release() -> None:
    register(scenario([telemetry_step()]))
    session = activate(prepare("generic-guided-test")["session"])
    batch = {"observations": [observation("obs-1", 1), observation("obs-2", 2, "saved")]}
    response = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json=batch,
    )
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["accepted"] == 2
    assert receipt["duplicates"] == 0
    assert receipt["status"] == "COMPLETED"

    duplicate = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json=batch,
    ).json()
    assert duplicate["accepted"] == 0
    assert duplicate["duplicates"] == 2
    assert duplicate["revision"] == receipt["revision"]
    completed = client.get(f"/api/v1/guided/sessions/{session['id']}").json()
    assert completed["results"][0]["evidenceClass"] == "TELEMETRY"
    assert completed["gate"]["decision"] == "PASS"
    assert completed["gate"]["releaseRecommended"] is False
    assert completed["gate"]["humanApprovalRequired"] is True
    assert any("リリースゲートの代替ではない" in warning for warning in completed["gate"]["warnings"])


def test_hybrid_waits_for_both_human_and_telemetry_and_requires_manual_review() -> None:
    register(scenario([telemetry_step(kind="hybrid")]))
    session = activate(prepare("generic-guided-test")["session"])
    session = submit_verdict(session, "passed", notes="最初の人による判定")
    assert session["status"] == "RUNNING"
    assert session["results"][0]["manualVerdict"]["outcome"] == "passed"
    overwrite = client.post(
        f"/api/v1/guided/sessions/{session['id']}/feedback",
        json={
            "outcome": "failed",
            "reporterRole": "user",
            "difficultyRating": 5,
            "confidenceRating": 1,
            "notes": "上書きを試みる",
        },
        headers=attestation_headers(session),
    )
    assert overwrite.status_code == 409
    response = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json={"observations": [observation("hybrid-1", 1), observation("hybrid-2", 2, "saved")]},
    )
    assert response.status_code == 200
    completed = client.get(f"/api/v1/guided/sessions/{session['id']}").json()
    assert completed["status"] == "COMPLETED"
    assert completed["results"][0]["evidenceClass"] == "HYBRID"
    assert completed["gate"]["decision"] == "MANUAL_REVIEW"
    assert completed["gate"]["releaseRecommended"] is False


def test_observer_authority_is_enforced_and_preserved_as_observer_reported() -> None:
    register(scenario([manual_step(authority="observer")]))
    missing_observer = client.post(
        "/api/v1/guided/sessions",
        json={"scenarioId": "generic-guided-test", "operatorAlias": "tester"},
    )
    assert missing_observer.status_code == 422
    session = activate(
        prepare("generic-guided-test", observer="qa-observer")["session"], ["対象画面を表示した"]
    )
    denied = client.post(
        f"/api/v1/guided/sessions/{session['id']}/feedback",
        json={
            "outcome": "passed",
            "reporterRole": "user",
            "difficultyRating": 1,
            "confidenceRating": 5,
        },
        headers=attestation_headers(session),
    )
    assert denied.status_code == 409
    completed = submit_verdict(session, "passed", role="observer")
    assert completed["results"][0]["evidenceClass"] == "OBSERVER_REPORTED"
    assert completed["gate"]["decision"] == "MANUAL_REVIEW"


def test_failed_and_blocked_steps_create_prepared_subset_retest() -> None:
    register(scenario([manual_step("first"), manual_step("second")]))
    session = activate(prepare("generic-guided-test")["session"], ["対象画面を表示した"])
    session = submit_verdict(session, "passed")
    assert session["status"] == "STEP_COMPLETE"
    session = control(session, "next")
    session = control(session, "activate", confirmedConditions=["対象画面を表示した"])
    session = submit_verdict(session, "failed", notes="保存結果が反映されない")
    assert session["status"] == "FAILED"
    assert session["retestSessionId"]

    retest = client.get(f"/api/v1/guided/sessions/{session['retestSessionId']}").json()
    assert retest["status"] == "PREPARED"
    assert retest["parentSessionId"] == session["id"]
    assert retest["selectedStepIds"] == ["second"]
    assert [result["stepId"] for result in retest["results"]] == ["second"]


def test_media_marker_and_asset_boundaries_are_validated(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        GuidedMedia(source="local_asset", src="../outside.png")
    with pytest.raises(ValidationError):
        GuidedMedia(source="local_asset", src="notes.txt")
    with pytest.raises(ValidationError):
        GuidedMedia(source="local_asset", src="active-content.svg")
    with pytest.raises(ValidationError):
        GuidedMedia(source="url", src="http://tracking.example/hint.png")
    assert GuidedMedia(source="url", src="https://example.test/hint.png").source == "url"
    assert GuidedMedia(source="url", src="http://127.0.0.1:8766/hint.png").source == "url"
    with pytest.raises(ValidationError):
        GuidedVisualMarker(shape="point", x=0.5, y=0.5, color="red;position:fixed")
    with pytest.raises(ValidationError):
        GuidedVisualMarker(shape="rect", x=0.9, y=0.9, width=0.2, height=0.2)
    marker = GuidedVisualMarker(shape="arrow", x=0.1, y=0.1, toX=0.9, toY=0.9)
    assert marker.shape == "arrow"

    guided_api.GUIDED_ASSETS.mkdir(parents=True)
    asset = guided_api.GUIDED_ASSETS / "hint.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert client.get("/api/v1/guided/assets/hint.png").status_code == 200
    assert client.get("/api/v1/guided/assets/active-content.svg").status_code == 404
    secret = tmp_path / "secret.txt"
    secret.write_text("no", encoding="utf-8")
    assert client.get("/api/v1/guided/assets/%2E%2E/secret.txt").status_code == 404


def test_ai_guide_contract_exposes_next_step_but_cannot_approve_or_invent_verdict() -> None:
    register(scenario([manual_step()]))
    receipt = mcp_server.guided_prepare_session("generic-guided-test")
    session_id = receipt["session"]["id"]
    instruction = mcp_server.guided_next_step(session_id)
    assert instruction["approvalRequired"] is True
    assert instruction["humanVerdictCannotBeOverriddenByAi"] is True
    assert instruction["step"]["guidance"]["markers"][0]["shape"] == "point"
    with pytest.raises(PermissionError):
        mcp_server.guided_control_session(session_id, "approve")
    with pytest.raises(PermissionError):
        mcp_server.guided_control_session(session_id, "activate")
    with pytest.raises(PermissionError):
        mcp_server.guided_control_session(session_id, "activate", human_confirmed=True)
    with pytest.raises(PermissionError):
        mcp_server.guided_record_human_result(session_id, "passed", human_attested=False)
    with pytest.raises(PermissionError):
        mcp_server.guided_record_human_result(session_id, "passed", human_attested=True)


def test_runner_declares_human_test_boundary_and_sanitizes_marker_color() -> None:
    register(scenario([manual_step()]))
    session_id = prepare("generic-guided-test")["session"]["id"]
    response = client.get(f"/guided/{session_id}")
    assert response.status_code == 200
    assert "自動テストとは別" in response.text
    assert "safeColor" in response.text
    assert "AIは案内のみ" in response.text
    assert "!state.approvedAtMs" in response.text
    assert "気づき・使用感" in response.text
    assert "X-EagleEye-Human-Attestation" in response.text
    assert client.get("/guided/%3Cscript%3Ealert(1)%3C/script%3E").status_code == 404
    assert "ATTESTATION=" in response.text
    assert response.headers["cache-control"] == "no-store, private"


def test_documented_generic_sample_is_a_valid_product_neutral_scenario() -> None:
    sample = Path("examples/guided-user-scenario.json").read_text(encoding="utf-8")
    parsed = GuidedScenarioDefinition.model_validate_json(sample)
    assert parsed.steps[0].kind == "manual"
    assert parsed.steps[0].guidance.markers[0].shape == "circle"
    assert parsed.steps[0].verdictAuthority == "either"


def test_user_block_without_telemetry_is_not_mislabeled_as_telemetry_evidence() -> None:
    register(scenario([telemetry_step()]))
    session = prepare("generic-guided-test")["session"]
    session = control(session, "approve")
    session = control(session, "block", reason="必要な周辺機器がない")
    assert session["status"] == "BLOCKED"
    assert session["results"][0]["observationCount"] == 0
    assert session["results"][0]["evidenceClass"] == "SELF_REPORTED"


def test_scenario_becomes_immutable_after_a_session_references_it() -> None:
    original = scenario([manual_step()])
    register(original)
    session = prepare("generic-guided-test")["session"]
    assert session["scenarioSha256"]

    assert client.post("/api/v1/guided/scenarios", json=original).status_code == 200
    changed = {**original, "title": "Changed while a session exists"}
    response = client.post("/api/v1/guided/scenarios", json=changed)
    assert response.status_code == 409
    assert "immutable" in response.json()["detail"]
    saved = client.get("/api/v1/guided/scenarios/generic-guided-test").json()
    assert saved["title"] == original["title"]
    with sqlite3.connect(guided_storage.DATABASE) as database:
        assert database.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_terminal_session_ignores_late_observations_and_keeps_evidence_immutable() -> None:
    register(scenario([telemetry_step()]))
    session = activate(prepare("generic-guided-test")["session"])
    first = {"observations": [observation("obs-1", 1), observation("obs-2", 2, "saved")]}
    client.post(f"/api/v1/guided/sessions/{session['id']}/observations:batch", json=first).raise_for_status()
    completed = client.get(f"/api/v1/guided/sessions/{session['id']}").json()
    revision = completed["revision"]
    evidence_sha = completed["sessionEvidenceSha256"]

    late = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json={"observations": [observation("late-3", 3)]},
    )
    assert late.status_code == 200
    assert late.json()["accepted"] == 0
    assert late.json()["duplicates"] == 1
    assert late.json()["revision"] == revision
    single = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=observation("late-4", 4),
    )
    assert single.status_code == 200
    assert single.json()["revision"] == revision
    after = client.get(f"/api/v1/guided/sessions/{session['id']}").json()
    assert after["sessionEvidenceSha256"] == evidence_sha
    stored = client.get(f"/api/v1/guided/sessions/{session['id']}/observations").json()
    assert [item["id"] for item in stored] == ["obs-1", "obs-2"]


def test_abort_prepares_a_retest_for_only_the_now_blocked_steps() -> None:
    register(scenario([manual_step("first"), manual_step("second")]))
    session = prepare("generic-guided-test")["session"]
    session = control(session, "abort", reason="ユーザーが後で再開する")
    assert session["status"] == "ABORTED"
    assert all(result["status"] == "BLOCKED" for result in session["results"])
    retest = client.get(f"/api/v1/guided/sessions/{session['retestSessionId']}").json()
    assert retest["status"] == "PREPARED"
    assert retest["selectedStepIds"] == ["first", "second"]


def test_human_attestation_is_required_not_serialized_and_revoked_at_terminal() -> None:
    register(scenario([manual_step()]))
    receipt = prepare("generic-guided-test")
    session = receipt["session"]
    runner = client.get(f"/guided/{session['id']}")
    token = runner_token(session)
    assert token
    assert runner.headers["cache-control"] == "no-store, private"
    assert runner.headers["referrer-policy"] == "no-referrer"
    assert token not in json.dumps(receipt)
    assert token not in client.get(f"/api/v1/guided/sessions/{session['id']}").text
    assert token not in client.get(f"/api/v1/guided/sessions/{session['id']}/next").text

    endpoint = f"/api/v1/guided/sessions/{session['id']}/control"
    missing = client.post(
        endpoint,
        json={"action": "approve", "expectedRevision": session["revision"]},
    )
    wrong = client.post(
        endpoint,
        json={"action": "approve", "expectedRevision": session["revision"]},
        headers={ATTESTATION_HEADER: "wrong-token"},
    )
    assert missing.status_code == 403
    assert wrong.status_code == 403
    unchanged = client.get(f"/api/v1/guided/sessions/{session['id']}").json()
    assert unchanged["status"] == "PREPARED"
    assert unchanged["revision"] == session["revision"]

    guided_api.service._human_attestations.pop(session["id"], None)
    approved = client.post(
        endpoint,
        json={"action": "approve", "expectedRevision": session["revision"]},
        headers={ATTESTATION_HEADER: token},
    )
    assert approved.status_code == 200
    session = approved.json()
    with sqlite3.connect(guided_storage.DATABASE) as database:
        digest = database.execute(
            "SELECT token_sha256 FROM guided_attestations WHERE session_id = ?", (session["id"],)
        ).fetchone()[0]
        assert digest == hashlib.sha256(token.encode()).hexdigest()
        serialized_rows = database.execute("SELECT body_json FROM guided_sessions").fetchall()
        serialized_rows += database.execute("SELECT body_json FROM guided_audit").fetchall()
        serialized = "\n".join(row[0] for row in serialized_rows)
    assert token not in serialized

    denied_activate = client.post(
        endpoint,
        json={
            "action": "activate",
            "expectedRevision": session["revision"],
            "confirmedConditions": ["対象画面を表示した"],
        },
    )
    assert denied_activate.status_code == 403
    session = control(
        session,
        "activate",
        confirmedConditions=["対象画面を表示した"],
    )
    denied_feedback = client.post(
        f"/api/v1/guided/sessions/{session['id']}/feedback",
        json={"outcome": "passed", "reporterRole": "user"},
    )
    assert denied_feedback.status_code == 403
    completed = submit_verdict(session, "passed")
    assert completed["status"] == "COMPLETED"
    assert token not in Path(completed["reportPath"]).read_text(encoding="utf-8")
    assert token not in Path(completed["sessionEvidencePath"]).read_text(encoding="utf-8")
    with sqlite3.connect(guided_storage.DATABASE) as database:
        assert (
            database.execute(
                "SELECT token_sha256 FROM guided_attestations WHERE session_id = ?",
                (session["id"],),
            ).fetchone()
            is None
        )
    replay = client.post(
        f"/api/v1/guided/sessions/{session['id']}/feedback",
        json={"outcome": "failed", "reporterRole": "user"},
        headers={ATTESTATION_HEADER: token},
    )
    assert replay.status_code == 403


def test_resume_block_abort_and_feedback_reject_missing_attestation() -> None:
    register(scenario([manual_step()]))
    session = activate(prepare("generic-guided-test")["session"], ["対象画面を表示した"])
    session = control(session, "pause")
    denied_resume = client.post(
        f"/api/v1/guided/sessions/{session['id']}/control",
        json={"action": "resume", "expectedRevision": session["revision"]},
    )
    assert denied_resume.status_code == 403
    session = control(session, "resume")
    denied_block = client.post(
        f"/api/v1/guided/sessions/{session['id']}/control",
        json={"action": "block", "expectedRevision": session["revision"]},
    )
    assert denied_block.status_code == 403

    second = prepare("generic-guided-test")["session"]
    denied_abort = client.post(
        f"/api/v1/guided/sessions/{second['id']}/control",
        json={"action": "abort", "expectedRevision": second["revision"]},
    )
    assert denied_abort.status_code == 403
    aborted = control(second, "abort", reason="attested abort")
    assert aborted["status"] == "ABORTED"


def test_prepared_and_ready_observations_are_ignored_without_persistence() -> None:
    register(scenario([telemetry_step()]))
    session = prepare("generic-guided-test")["session"]
    revision = session["revision"]
    single = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=observation("pre-single", 1),
    )
    assert single.status_code == 200
    assert single.json()["revision"] == revision
    batch = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json={"observations": [observation("pre-batch", 2)]},
    ).json()
    assert batch["accepted"] == 0
    assert batch["duplicates"] == 0
    assert client.get(f"/api/v1/guided/sessions/{session['id']}/observations").json() == []

    session = control(session, "approve")
    ready = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json={"observations": [observation("ready-batch", 3)]},
    ).json()
    assert ready["accepted"] == 0
    assert ready["duplicates"] == 0
    assert client.get(f"/api/v1/guided/sessions/{session['id']}/observations").json() == []

    session = control(session, "activate")
    active = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json={"observations": [observation("active-one", 4)]},
    ).json()
    assert active["accepted"] == 1
    stored = client.get(f"/api/v1/guided/sessions/{session['id']}/observations").json()
    assert [item["id"] for item in stored] == ["active-one"]


def test_event_count_and_settle_contract_rejects_impossible_scenarios() -> None:
    step = telemetry_step()
    step["telemetryOracle"]["exactEventCounts"] = {"saved": 1}
    with pytest.raises(ValidationError, match="positive settleWindowMs"):
        GuidedScenarioDefinition.model_validate(scenario([step]))

    step = telemetry_step()
    step["telemetryOracle"].update(
        {"exactEventCounts": {"saved": 2}, "maxEventCounts": {"saved": 1}, "settleWindowMs": 10}
    )
    with pytest.raises(ValidationError, match="cannot exceed maxEventCounts"):
        GuidedScenarioDefinition.model_validate(scenario([step]))

    step = telemetry_step()
    step["timeoutMs"] = 1_000
    step["telemetryOracle"].update({"minObservationMs": 800, "settleWindowMs": 300})
    with pytest.raises(ValidationError, match="cannot exceed timeoutMs"):
        GuidedScenarioDefinition.model_validate(scenario([step]))


def test_exact_event_waits_for_settle_and_guided_telemetry_never_releases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"now": 2_000_000_000_000}
    monkeypatch.setattr("app.guided_service.now_ms", lambda: clock["now"])
    step = telemetry_step()
    step["telemetryOracle"].update(
        {
            "minObservations": 1,
            "minMatchingObservations": 1,
            "minConsecutiveMatches": 1,
            "maxMismatches": 1,
            "requiredEvents": {"saved": 1},
            "exactEventCounts": {"saved": 1},
            "maxEventCounts": {"saved": 1, "pulse": 2},
            "settleWindowMs": 100,
        }
    )
    register(scenario([step]))
    session = activate(prepare("generic-guided-test")["session"])
    running = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=observation("saved-once", 1, "saved"),
    ).json()
    result = running["results"][0]
    assert running["status"] == "RUNNING"
    assert result["telemetrySatisfied"] is False
    assert result["settleDeadlineMs"] == clock["now"] + 100

    clock["now"] += 50
    restarted = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=observation("pulse-during-settle", 2, "pulse"),
    ).json()
    assert restarted["status"] == "RUNNING"
    assert restarted["results"][0]["settleDeadlineMs"] == clock["now"] + 100

    clock["now"] += 25
    unstable = observation("unstable-during-settle", 3)
    unstable["values"]["state"] = "idle"
    restarted_again = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=unstable,
    ).json()
    assert restarted_again["status"] == "RUNNING"
    assert restarted_again["results"][0]["settleDeadlineMs"] is None

    clock["now"] += 25
    recovered = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=observation("stable-again", 4),
    ).json()
    assert recovered["results"][0]["settleDeadlineMs"] == clock["now"] + 100

    clock["now"] += 99
    assert client.get(f"/api/v1/guided/sessions/{session['id']}").json()["status"] == "RUNNING"
    clock["now"] += 1
    completed = client.get(f"/api/v1/guided/sessions/{session['id']}").json()
    assert completed["status"] == "COMPLETED"
    assert completed["results"][0]["status"] == "PASSED"
    assert completed["gate"]["releaseRecommended"] is False


def test_exact_count_overflow_and_late_batch_forbidden_event_cannot_false_pass() -> None:
    exact = telemetry_step()
    exact["telemetryOracle"].update(
        {
            "minObservations": 1,
            "minMatchingObservations": 1,
            "minConsecutiveMatches": 1,
            "requiredEvents": {"saved": 1},
            "exactEventCounts": {"saved": 1},
            "settleWindowMs": 100,
        }
    )
    register(scenario([exact], "exact-overflow"))
    session = activate(prepare("exact-overflow")["session"])
    failed = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json={
            "observations": [
                observation("exact-1", 1, "saved"),
                observation("exact-2", 2, "saved"),
            ]
        },
    )
    assert failed.status_code == 200
    exact_result = client.get(f"/api/v1/guided/sessions/{session['id']}").json()
    assert exact_result["status"] == "FAILED"
    assert "EXACT_EVENT_COUNT_MISMATCH" in exact_result["results"][0]["failureCodes"]

    batch_step = telemetry_step()
    batch_step["telemetryOracle"].update(
        {
            "minObservations": 1,
            "minMatchingObservations": 1,
            "minConsecutiveMatches": 1,
            "requiredEvents": {},
        }
    )
    register(scenario([batch_step], "batch-forbidden"))
    second = activate(prepare("batch-forbidden")["session"])
    client.post(
        f"/api/v1/guided/sessions/{second['id']}/observations:batch",
        json={
            "observations": [
                observation("base-pass", 1),
                observation("late-fatal", 2, "fatal"),
            ]
        },
    ).raise_for_status()
    batch_result = client.get(f"/api/v1/guided/sessions/{second['id']}").json()
    assert batch_result["status"] == "FAILED"
    assert "FORBIDDEN_EVENT" in batch_result["results"][0]["failureCodes"]


def test_pause_does_not_consume_the_settle_window(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 2_050_000_000_000}
    monkeypatch.setattr("app.guided_service.now_ms", lambda: clock["now"])
    step = telemetry_step()
    step["telemetryOracle"].update(
        {
            "minObservations": 1,
            "minMatchingObservations": 1,
            "minConsecutiveMatches": 1,
            "requiredEvents": {"saved": 1},
            "exactEventCounts": {"saved": 1},
            "settleWindowMs": 100,
        }
    )
    register(scenario([step]))
    session = activate(prepare("generic-guided-test")["session"])
    session = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=observation("pause-saved", 1, "saved"),
    ).json()
    original_start = session["results"][0]["settleStartedAtMs"]
    original_deadline = session["results"][0]["settleDeadlineMs"]

    clock["now"] += 30
    session = control(session, "pause")
    clock["now"] += 500
    session = control(session, "resume")
    assert session["results"][0]["settleStartedAtMs"] == original_start + 500
    assert session["results"][0]["settleDeadlineMs"] == original_deadline + 500

    clock["now"] += 69
    assert client.get(f"/api/v1/guided/sessions/{session['id']}").json()["status"] == "RUNNING"
    clock["now"] += 1
    assert client.get(f"/api/v1/guided/sessions/{session['id']}").json()["status"] == "COMPLETED"


def test_awaiting_feedback_ignores_pose_mismatch_but_monitors_event_upper_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"now": 2_100_000_000_000}
    monkeypatch.setattr("app.guided_service.now_ms", lambda: clock["now"])
    step = telemetry_step(kind="hybrid")
    step["telemetryOracle"].update(
        {
            "minObservations": 1,
            "minMatchingObservations": 1,
            "minConsecutiveMatches": 1,
            "maxMismatches": 0,
            "requiredEvents": {"saved": 1},
            "exactEventCounts": {"saved": 1},
            "maxEventCounts": {"click": 1},
            "settleWindowMs": 50,
        }
    )
    register(scenario([step]))
    session = activate(prepare("generic-guided-test")["session"])
    client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations:batch",
        json={
            "observations": [
                observation("hybrid-saved", 1, "saved"),
                observation("hybrid-click", 2, "click"),
            ]
        },
    ).raise_for_status()
    clock["now"] += 50
    awaiting = client.get(f"/api/v1/guided/sessions/{session['id']}").json()
    assert awaiting["status"] == "AWAITING_FEEDBACK"
    before_mismatches = awaiting["results"][0]["mismatches"]

    moved_away = observation("moved-away", 3)
    moved_away["values"]["state"] = "idle"
    still_awaiting = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=moved_away,
    ).json()
    assert still_awaiting["status"] == "AWAITING_FEEDBACK"
    assert still_awaiting["results"][0]["mismatches"] == before_mismatches

    exceeded = client.post(
        f"/api/v1/guided/sessions/{session['id']}/observations",
        json=observation("second-click", 4, "click"),
    ).json()
    assert exceeded["status"] == "FAILED"
    assert "MAX_EVENT_COUNT_EXCEEDED" in exceeded["results"][0]["failureCodes"]

    second = activate(prepare("generic-guided-test")["session"])
    client.post(
        f"/api/v1/guided/sessions/{second['id']}/observations:batch",
        json={
            "observations": [
                observation("second-saved", 1, "saved"),
                observation("first-click", 2, "click"),
            ]
        },
    ).raise_for_status()
    clock["now"] += 50
    second = client.get(f"/api/v1/guided/sessions/{second['id']}").json()
    assert second["status"] == "AWAITING_FEEDBACK"
    forbidden = client.post(
        f"/api/v1/guided/sessions/{second['id']}/observations",
        json=observation("fatal-while-answering", 3, "fatal"),
    ).json()
    assert forbidden["status"] == "FAILED"
    assert "FORBIDDEN_EVENT" in forbidden["results"][0]["failureCodes"]
