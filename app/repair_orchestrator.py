from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from .repair_lock import ProjectRepairBusyError, ProjectRepairLock
from .repair_models import (
    RepairAttemptRecord,
    RepairPlan,
    RepairPlannerInput,
    RepairRequest,
    RepairResponse,
    VerificationCommand,
    VerificationCommandResult,
)
from .repair_policy import PreparedPlan, RepairAuthorization, RepairPolicy, RepairPolicyError
from .repair_worktree import DisposableWorktree, DisposableWorktreeError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = ROOT / ".runtime" / "self-repair"
REPARSE_POINT_ATTRIBUTE = 0x400
REDACTIONS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)((?:api[_-]?key|client[_-]?secret|password|token)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


Planner = Callable[[RepairPlannerInput], RepairPlan | dict[str, Any]]


class RepairOrchestrator:
    """Bounded repair executor; an App Server planner can be injected by the caller."""

    def __init__(
        self,
        planner: Planner,
        policy: RepairPolicy,
        *,
        artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    ) -> None:
        self.planner = planner
        self.policy = policy
        self.artifact_root = artifact_root

    def execute(self, request: RepairRequest) -> RepairResponse:
        request_id = f"repair-{uuid4().hex}"
        self._prepare_artifact_root()
        audit_dir = self.artifact_root / request_id
        audit_dir.mkdir(parents=True, exist_ok=False)
        attempts: list[RepairAttemptRecord] = []
        reasons: list[str] = []
        authorization: RepairAuthorization | None = None
        try:
            project_root = self.policy.resolve_project_root(request.projectId)
            self._validate_artifact_boundary(project_root)
            with ProjectRepairLock(project_root, self.artifact_root / ".locks"):
                return self._execute_locked(request_id, request, audit_dir, attempts, reasons)
        except (ProjectRepairBusyError, RepairPolicyError) as exc:
            reasons.append(_safe_message(exc))
            return self._finish(
                request_id,
                request,
                audit_dir,
                authorization,
                "denied",
                "DENIED",
                reasons,
                None,
                attempts,
            )

    def _execute_locked(
        self,
        request_id: str,
        request: RepairRequest,
        audit_dir: Path,
        attempts: list[RepairAttemptRecord],
        reasons: list[str],
    ) -> RepairResponse:
        authorization: RepairAuthorization | None = None
        final_plan: RepairPlan | None = None
        try:
            authorization = self.policy.authorize(request)
            reasons.extend(authorization.reasons)
        except RepairPolicyError as exc:
            reasons.append(_safe_message(exc))
            return self._finish(
                request_id,
                request,
                audit_dir,
                authorization,
                "denied",
                "DENIED",
                reasons,
                None,
                attempts,
            )

        previous_failures: list[str] = []
        limits = self.policy.capabilities.limits
        for attempt_number in range(1, limits.maxAttempts + 1):
            try:
                planner_input = RepairPlannerInput(
                    request=request,
                    projectRoot=authorization.root,
                    attempt=attempt_number,
                    limits=limits,
                    previousFailures=previous_failures,
                )
                raw_plan = self.planner(planner_input)
                plan = raw_plan if isinstance(raw_plan, RepairPlan) else RepairPlan.model_validate(raw_plan)
                final_plan = plan
                if plan.action == "no_safe_repair":
                    reasons.append(plan.summary)
                    attempts.append(
                        RepairAttemptRecord(
                            attempt=attempt_number,
                            status="NO_SAFE_REPAIR",
                            reason=plan.summary,
                        )
                    )
                    return self._finish(
                        request_id,
                        request,
                        audit_dir,
                        authorization,
                        "proposal_only",
                        "NO_SAFE_REPAIR",
                        reasons,
                        plan,
                        attempts,
                    )
                original_prepared = self.policy.prepare_plan(authorization.root, plan)
            except (RepairPolicyError, ValidationError, ValueError, TypeError) as exc:
                failure = _safe_message(exc)
                previous_failures.append(failure)
                attempts.append(
                    RepairAttemptRecord(
                        attempt=attempt_number,
                        status="PLAN_REJECTED",
                        reason=failure,
                    )
                )
                if attempt_number == limits.maxAttempts:
                    reasons.append("Planner did not produce an eligible bounded repair plan")
                continue
            except Exception as exc:  # noqa: BLE001 - planner boundary is intentionally contained
                failure = f"Planner failed: {_safe_message(exc)}"
                previous_failures.append(failure)
                attempts.append(RepairAttemptRecord(attempt=attempt_number, status="FAILED", reason=failure))
                if attempt_number == limits.maxAttempts:
                    reasons.append("Planner failed within the bounded attempt budget")
                continue

            if authorization.effective_mode == "proposal_only":
                attempts.append(self._attempt_record(attempt_number, "PROPOSED", original_prepared))
                return self._finish(
                    request_id,
                    request,
                    audit_dir,
                    authorization,
                    "proposal_only",
                    "PROPOSED",
                    reasons,
                    plan,
                    attempts,
                )

            prepared: PreparedPlan | None = None
            checkpoint_path: Path | None = None
            verification: list[VerificationCommandResult] = []
            postimages: dict[str, str] = {}
            failure = ""
            try:
                with DisposableWorktree(authorization.root) as execution_root:
                    self._synchronize_worktree(execution_root, original_prepared)
                    prepared = self.policy.prepare_plan(execution_root, plan)
                    checkpoint_path = self._create_checkpoint(
                        execution_root, audit_dir, attempt_number, prepared
                    )
                    self._apply(execution_root, prepared)
                    postimages = self._verify_postimages(prepared)
                    verification = self._run_verification(execution_root, authorization.project.verification)
                    failed_commands = [item for item in verification if item.timedOut or item.returnCode != 0]
                    if failed_commands:
                        failure = "Verification command failed"
                    else:
                        self._verify_postimages(prepared)
                        planned = {item.relative_path for item in prepared.files}
                        if self.policy.git_changed_paths(execution_root) != planned:
                            failure = "Verification produced unapproved worktree changes"
                    if not failure:
                        self.policy.require_clean_git(authorization.root)
                        self._apply(authorization.root, original_prepared)
                        self._verify_postimages(original_prepared)
                        if self.policy.git_changed_paths(authorization.root) != planned:
                            raise RepairPolicyError(
                                "Publication produced unapproved original worktree changes"
                            )
                        attempts.append(
                            self._attempt_record(
                                attempt_number,
                                "APPLIED",
                                prepared,
                                checkpoint_path=checkpoint_path,
                                postimages=postimages,
                                verification=verification,
                            )
                        )
                        return self._finish(
                            request_id,
                            request,
                            audit_dir,
                            authorization,
                            "apply",
                            "APPLIED",
                            reasons,
                            plan,
                            attempts,
                        )
            except (DisposableWorktreeError, OSError, RepairPolicyError) as exc:
                failure = _safe_message(exc)

            if prepared is None or checkpoint_path is None:
                attempts.append(RepairAttemptRecord(attempt=attempt_number, status="FAILED", reason=failure))
                previous_failures.append(failure or "Disposable repair worktree failed")
                continue

            rollback_verified = not self.policy.git_changed_paths(authorization.root)
            if not rollback_verified:
                rollback_verified = self._rollback(
                    authorization.root, original_prepared, checkpoint_path
                ) and not self.policy.git_changed_paths(authorization.root)
            attempts.append(
                self._attempt_record(
                    attempt_number,
                    "ROLLED_BACK" if rollback_verified else "FAILED",
                    prepared,
                    reason=failure,
                    checkpoint_path=checkpoint_path,
                    postimages=postimages,
                    rollback_verified=rollback_verified,
                    verification=verification,
                )
            )
            previous_failures.append(failure or "Repair attempt failed")
            if not rollback_verified:
                reasons.append("Rollback could not prove the original clean worktree")
                break

        status = "ROLLED_BACK" if any(item.status == "ROLLED_BACK" for item in attempts) else "FAILED"
        if not reasons:
            reasons.append("Repair exhausted its bounded attempt budget")
        return self._finish(
            request_id,
            request,
            audit_dir,
            authorization,
            authorization.effective_mode,
            status,
            reasons,
            final_plan,
            attempts,
        )

    @staticmethod
    def _synchronize_worktree(execution_root: Path, prepared: PreparedPlan) -> None:
        """Make planned temp files byte-identical to the locked clean source worktree."""

        for item in prepared.files:
            target = execution_root / Path(item.relative_path)
            current_sha = _sha256(target.read_bytes())
            _require_safe_current_file(execution_root, target, current_sha)
            _atomic_replace_bytes(target, item.preimage)
            if _sha256(target.read_bytes()) != item.preimage_sha256:
                raise RepairPolicyError(f"Disposable preimage sync failed for {item.relative_path}")

    def _validate_artifact_boundary(self, project_root: Path) -> None:
        resolved = self.artifact_root.resolve()
        try:
            resolved.relative_to(project_root)
        except ValueError:
            return
        if ".runtime" not in resolved.parts:
            raise RepairPolicyError("Repair audit storage inside a project must be under ignored .runtime")

    def _prepare_artifact_root(self) -> None:
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        for candidate in (self.artifact_root, *self.artifact_root.parents):
            if not candidate.exists():
                continue
            attributes = getattr(candidate.lstat(), "st_file_attributes", 0)
            if candidate.is_symlink() or attributes & REPARSE_POINT_ATTRIBUTE:
                raise RepairPolicyError("Repair artifact path may not traverse a symlink or reparse point")

    @staticmethod
    def _create_checkpoint(
        project_root: Path,
        audit_dir: Path,
        attempt: int,
        prepared: PreparedPlan,
    ) -> Path:
        staging = audit_dir / f".checkpoint-{attempt}-{uuid4().hex}.tmp"
        final = audit_dir / f"checkpoint-{attempt}"
        staging.mkdir(parents=True, exist_ok=False)
        manifest: list[dict[str, str]] = []
        for item in prepared.files:
            destination = staging / "files" / Path(item.relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            _write_new_bytes(destination, item.preimage)
            manifest.append({"path": item.relative_path, "preimageSha256": item.preimage_sha256})
        _write_new_bytes(
            staging / "manifest.json",
            json.dumps(
                {
                    "schema": "eagleeye.repair-checkpoint.v1",
                    "projectRootSha256": _sha256(str(project_root).encode()),
                    "files": manifest,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        os.replace(staging, final)
        return final

    @staticmethod
    def _apply(root: Path, prepared: PreparedPlan) -> None:
        for item in prepared.files:
            _require_safe_current_file(root, item.path, item.preimage_sha256)
            _atomic_replace_bytes(item.path, item.postimage)
            if _sha256(item.path.read_bytes()) != item.postimage_sha256:
                raise RepairPolicyError(f"Postimage verification failed for {item.relative_path}")

    @staticmethod
    def _verify_postimages(prepared: PreparedPlan) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for item in prepared.files:
            current = _sha256(item.path.read_bytes())
            if current != item.postimage_sha256:
                raise RepairPolicyError(f"Postimage changed unexpectedly for {item.relative_path}")
            hashes[item.relative_path] = current
        return hashes

    @staticmethod
    def _rollback(root: Path, prepared: PreparedPlan, checkpoint_path: Path) -> bool:
        try:
            for item in prepared.files:
                current_sha = _sha256(item.path.read_bytes())
                if current_sha not in {item.preimage_sha256, item.postimage_sha256}:
                    return False
                _require_safe_current_file(root, item.path, current_sha)
                checkpoint_file = checkpoint_path / "files" / Path(item.relative_path)
                preimage = checkpoint_file.read_bytes()
                if _sha256(preimage) != item.preimage_sha256:
                    return False
                _atomic_replace_bytes(item.path, preimage)
            return all(_sha256(item.path.read_bytes()) == item.preimage_sha256 for item in prepared.files)
        except OSError:
            return False

    @staticmethod
    def _run_verification(root: Path, commands: list[VerificationCommand]) -> list[VerificationCommandResult]:
        results: list[VerificationCommandResult] = []
        for command in commands:
            started = time.perf_counter()
            try:
                completed = subprocess.run(  # noqa: S603 -- argv comes only from trusted project policy
                    command.argv,
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=command.timeoutSeconds,
                    check=False,
                    shell=False,
                    env=_minimal_environment(),
                )
                results.append(
                    VerificationCommandResult(
                        name=command.name,
                        argv=command.argv,
                        returnCode=completed.returncode,
                        durationMs=_elapsed(started),
                        stdout=_redact(completed.stdout),
                        stderr=_redact(completed.stderr),
                    )
                )
            except subprocess.TimeoutExpired as exc:
                results.append(
                    VerificationCommandResult(
                        name=command.name,
                        argv=command.argv,
                        timedOut=True,
                        durationMs=_elapsed(started),
                        stdout=_redact(_to_text(exc.stdout)),
                        stderr=_redact(_to_text(exc.stderr)),
                    )
                )
                break
            except OSError as exc:
                results.append(
                    VerificationCommandResult(
                        name=command.name,
                        argv=command.argv,
                        durationMs=_elapsed(started),
                        stderr=_safe_message(exc),
                    )
                )
                break
            if results[-1].returnCode != 0:
                break
        return results

    @staticmethod
    def _attempt_record(
        attempt: int,
        status: str,
        prepared: PreparedPlan,
        *,
        reason: str = "",
        checkpoint_path: Path | None = None,
        postimages: dict[str, str] | None = None,
        rollback_verified: bool | None = None,
        verification: list[VerificationCommandResult] | None = None,
    ) -> RepairAttemptRecord:
        return RepairAttemptRecord(
            attempt=attempt,
            status=status,
            reason=reason,
            changedFiles=[item.relative_path for item in prepared.files],
            changedLines=prepared.changed_lines,
            totalBytes=prepared.total_bytes,
            preimageSha256={item.relative_path: item.preimage_sha256 for item in prepared.files},
            postimageSha256=postimages or {},
            checkpointPath=str(checkpoint_path) if checkpoint_path else None,
            rollbackVerified=rollback_verified,
            verification=verification or [],
        )

    def _finish(
        self,
        request_id: str,
        request: RepairRequest,
        audit_dir: Path,
        authorization: RepairAuthorization | None,
        effective_mode: str,
        status: str,
        reasons: list[str],
        plan: RepairPlan | None,
        attempts: list[RepairAttemptRecord],
    ) -> RepairResponse:
        audit_path = audit_dir / "audit.json"
        audit = {
            "schema": "eagleeye.self-repair-audit.v1",
            "requestId": request_id,
            "recordedAt": datetime.now(UTC).isoformat(),
            "request": {
                "projectId": request.projectId,
                "environment": request.environment,
                "production": request.production,
                "provider": request.provider,
                "model": request.model,
                "requestedMode": request.requestedMode,
                "explicitApplyRequested": request.explicitApplyRequested,
                "failureFingerprint": request.failureFingerprint,
                "failureSummary": _redact(request.failureSummary),
                "evidencePathHashes": [_sha256(value.encode()) for value in request.evidencePaths],
                "evidenceContentSha256": request.evidenceContentSha256,
                "attestationId": request.attestation.id if request.attestation else None,
            },
            "authorization": {
                "effectiveMode": effective_mode,
                "rootSha256": (
                    _sha256(str(authorization.root).encode()) if authorization is not None else None
                ),
                "reasons": [_redact(value) for value in reasons],
            },
            "plan": _audit_plan(plan),
            "attempts": [item.model_dump(mode="json") for item in attempts],
            "status": status,
        }
        body = json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        _atomic_replace_bytes(audit_path, body, create=True)
        audit_sha = _sha256(body)
        _atomic_replace_bytes(
            audit_path.with_suffix(".sha256"), f"{audit_sha}  audit.json\n".encode(), create=True
        )
        return RepairResponse(
            requestId=request_id,
            projectId=request.projectId,
            requestedMode=request.requestedMode,
            effectiveMode=effective_mode,
            status=status,
            reasons=reasons,
            plan=plan,
            attempts=attempts,
            auditPath=str(audit_path),
            auditSha256=audit_sha,
        )


def _audit_plan(plan: RepairPlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "action": plan.action,
        "summarySha256": _sha256(plan.summary.encode()),
        "confidence": plan.confidence,
        "files": [
            {
                "path": item.path,
                "expectedSha256": item.expectedSha256,
                "replacementCount": len(item.replacements),
                "replacementSha256": [
                    _sha256((replacement.old + "\x00" + replacement.new).encode())
                    for replacement in item.replacements
                ],
            }
            for item in plan.files
        ],
    }


def _require_safe_current_file(root: Path, path: Path, expected_sha: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RepairPolicyError("Repair target escaped the allowlisted root") from exc
    current = root
    for part in relative.parts:
        current /= part
        attributes = getattr(current.lstat(), "st_file_attributes", 0)
        if current.is_symlink() or attributes & REPARSE_POINT_ATTRIBUTE:
            raise RepairPolicyError("Repair target became a symlink or reparse point")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RepairPolicyError("Repair target escaped the allowlisted root") from exc
    if path.stat().st_nlink > 1:
        raise RepairPolicyError("Repair target became hard-linked")
    if not path.is_file() or _sha256(path.read_bytes()) != expected_sha:
        raise RepairPolicyError("Repair target changed after plan validation")


def _atomic_replace_bytes(path: Path, value: bytes, *, create: bool = False) -> None:
    if not create and not path.is_file():
        raise OSError("Atomic replacement target does not exist")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.eagleeye-{uuid4().hex}.tmp"
    try:
        _write_new_bytes(temporary, value)
        if path.exists():
            shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_new_bytes(path: Path, value: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _minimal_environment() -> dict[str, str]:
    allowed = (
        "COMSPEC",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    )
    return {name: os.environ[name] for name in allowed if name in os.environ}


def _redact(value: str) -> str:
    result = value[:4_000]
    for pattern in REDACTIONS:
        result = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", result)
    return result


def _safe_message(error: BaseException) -> str:
    return _redact(str(error) or error.__class__.__name__)


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _elapsed(started: float) -> int:
    return round((time.perf_counter() - started) * 1_000)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
