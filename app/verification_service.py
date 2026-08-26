from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import project_qa as project_qa_module
from . import storage as storage_module
from .project_qa import discover_project, run_project
from .project_qa_models import ProjectRunRequest
from .quality import evaluate_quality_gate
from .runner import run_bundle
from .storage import load_bundle, load_run, save_run
from .strategy_models import QualityGateRequest
from .verification_git import collect_git_context
from .verification_manifest import save_manifest
from .verification_models import (
    ManifestAI,
    ManifestExecution,
    ManifestPolicy,
    ManifestRepository,
    ManifestVerdict,
    ReverificationLink,
    VerificationEvidence,
    VerificationManifest,
    VerificationReport,
    VerificationRequest,
)
from .verification_plan import build_verification_plan

ROOT = Path(__file__).resolve().parents[1]
VERIFICATIONS = ROOT / "artifacts" / "verifications"


def run_verification(request: VerificationRequest) -> VerificationReport:
    verification_id = uuid4().hex
    discovery = discover_project(request.projectRoot)
    context = collect_git_context(
        request.projectRoot,
        base_ref=request.baseRef,
        head_ref=request.headRef,
        allow_dirty=request.allowDirty,
    )
    plan, profile = build_verification_plan(request, context, discovery, verification_id)
    run_dir = VERIFICATIONS / verification_id
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=False)
    started_at = _now()

    project_report = run_project(
        ProjectRunRequest(
            projectRoot=discovery.projectRoot,
            authorized=True,
            suiteIds=request.suiteIds,
            mode=plan.recommendedMode,
            failFast=request.failFast,
            timeoutSeconds=request.timeoutSeconds,
        )
    )

    browser_runs = []
    for session_id in request.browserSessionIds:
        bundle = load_bundle(session_id)
        result = run_bundle(bundle)
        save_run(result)
        browser_runs.append(load_run(session_id))

    combined = [
        {
            "testId": item.id,
            "testType": item.testType,
            "status": item.status,
            "severity": "high" if item.status != "PASSED" else "medium",
            "criticalFlow": False,
            "durationMs": item.durationMs,
            "errorMessage": item.errorMessage,
            "evidencePath": item.evidencePath,
            "evidenceSha256": item.evidenceSha256,
        }
        for item in project_report.results
    ]
    for browser in browser_runs:
        primary = browser.evidence[0] if browser.evidence else None
        combined.append(
            {
                "testId": f"browser-{browser.session_id}",
                "testType": "e2e",
                "status": "PASSED" if browser.status == "passed" else "FAILED",
                "severity": "medium" if browser.status == "passed" else "high",
                "criticalFlow": True,
                "durationMs": browser.duration_ms,
                "errorMessage": browser.error,
                "evidencePath": primary.path if primary else None,
                "evidenceSha256": primary.sha256 if primary else None,
            }
        )

    required_types = {item.testType for item in project_report.results}
    if browser_runs:
        required_types.add("e2e")
    quality_gate = evaluate_quality_gate(
        QualityGateRequest.model_validate(
            {
                "profileId": profile.id,
                "mode": plan.recommendedMode,
                "results": combined,
                "requiredTestTypes": sorted(required_types),
                "serviceType": request.serviceType,
            }
        )
    )
    status = _verification_status(quality_gate.decision)
    evidence = _collect_evidence(evidence_dir, project_report, browser_runs)
    reverification = (
        _reverification_link(request.previousVerificationId) if request.previousVerificationId else None
    )
    completed_at = _now()
    policy_sha = _sha256_json(profile.model_dump(mode="json"))
    environment_sha = _sha256_json(
        {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        }
    )
    clean_reason = (
        "Repository is clean, but verification ran in the authorized working tree "
        "rather than an isolated worktree."
        if not context.dirty
        else "Verification includes an explicitly allowed dirty working-tree fingerprint."
    )

    manifest = VerificationManifest(
        verificationId=verification_id,
        repository=ManifestRepository(
            rootFingerprint=context.rootFingerprint,
            branch=context.branch,
            baseCommit=context.baseCommit,
            headCommit=context.headCommit,
            mergeBase=context.mergeBase,
            diffSha256=context.diffSha256,
            workingTreeSha256=context.workingTreeSha256,
            dirty=context.dirty,
        ),
        policy=ManifestPolicy(
            mode=plan.recommendedMode,
            riskScore=plan.riskScore,
            policySha256=policy_sha,
        ),
        execution=ManifestExecution(
            startedAt=started_at,
            completedAt=completed_at,
            environmentFingerprint=environment_sha,
            cleanRoom=False,
            cleanRoomReason=clean_reason,
        ),
        tests=[
            {
                "id": item.id,
                "name": item.name,
                "type": item.testType,
                "status": item.status,
                "durationMs": item.durationMs,
                "evidenceSha256": item.evidenceSha256,
            }
            for item in project_report.results
        ],
        browser=[
            {
                "sessionId": item.session_id,
                "status": item.status,
                "durationMs": item.duration_ms,
                "evidenceSha256": [artifact.sha256 for artifact in item.evidence],
            }
            for item in browser_runs
        ],
        ai=ManifestAI(
            used=False,
            provider=None,
            model=None,
            authoritative=False,
        ),
        evidence=evidence,
        verdict=ManifestVerdict(
            decision=status,
            blockers=quality_gate.blockers,
            warnings=quality_gate.warnings,
        ),
        reverification=reverification,
        manifestSha256="0" * 64,
    )
    manifest_path, manifest_sha = save_manifest(run_dir / "manifest.json", manifest)
    report_json = run_dir / "verification.json"
    report_markdown = run_dir / "verification.md"
    report = VerificationReport(
        verificationId=verification_id,
        status=status,
        gitContext=context,
        plan=plan,
        projectQa=project_report,
        browserRuns=browser_runs,
        qualityGate=quality_gate,
        evidence=evidence,
        reverification=reverification,
        manifestPath=str(manifest_path),
        manifestSha256=manifest_sha,
        reportJson=str(report_json),
        reportMarkdown=str(report_markdown),
    )
    _atomic_write(report_json, report.model_dump_json(indent=2))
    _atomic_write(report_markdown, _markdown(report))
    return report


def load_verification(verification_id: str) -> VerificationReport:
    if not re.fullmatch(r"[a-f0-9]{32}", verification_id):
        raise ValueError("Invalid verification id")
    path = VERIFICATIONS / verification_id / "verification.json"
    if not path.is_file():
        raise FileNotFoundError(verification_id)
    return VerificationReport.model_validate_json(path.read_text(encoding="utf-8"))


def _collect_evidence(evidence_dir: Path, project_report, browser_runs) -> list[VerificationEvidence]:
    values: list[VerificationEvidence] = []
    for item in project_report.results:
        source = Path(item.evidencePath)
        values.append(
            _copy_evidence(
                source,
                evidence_dir,
                allowed_root=Path(project_qa_module.RUNS),
                identifier=f"project-{item.id}",
                kind="log",
                expected_sha=item.evidenceSha256,
                source_name="project-qa",
                related_test_id=item.id,
            )
        )
    for run in browser_runs:
        for index, artifact in enumerate(run.evidence):
            values.append(
                _copy_evidence(
                    Path(artifact.path),
                    evidence_dir,
                    allowed_root=Path(storage_module.RUNS),
                    identifier=f"browser-{run.session_id}-{index}-{artifact.kind}",
                    kind=artifact.kind,
                    expected_sha=artifact.sha256,
                    source_name=artifact.capture_source,
                    related_test_id=f"browser-{run.session_id}",
                )
            )
    return values


def _copy_evidence(
    source: Path,
    evidence_dir: Path,
    *,
    allowed_root: Path,
    identifier: str,
    kind: str,
    expected_sha: str,
    source_name: str,
    related_test_id: str,
) -> VerificationEvidence:
    root = allowed_root.resolve()
    resolved = source.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Evidence source is outside its trusted artifact root")
    actual_sha = _sha256_file(resolved)
    if actual_sha != expected_sha.lower():
        raise ValueError("Evidence hash mismatch")
    safe_identifier = re.sub(r"[^A-Za-z0-9_.-]", "-", identifier)[:140]
    suffix = resolved.suffix if len(resolved.suffix) <= 12 else ""
    destination = evidence_dir / f"{safe_identifier}{suffix}"
    shutil.copyfile(resolved, destination)
    copied_sha = _sha256_file(destination)
    if copied_sha != actual_sha:
        raise ValueError("Evidence copy verification failed")
    return VerificationEvidence(
        id=safe_identifier,
        kind=kind,
        path=str(destination.relative_to(evidence_dir.parent)).replace("\\", "/"),
        sha256=copied_sha,
        bytes=destination.stat().st_size,
        createdAt=_now(),
        source=source_name,
        relatedTestId=related_test_id,
    )


def _reverification_link(previous_id: str) -> ReverificationLink:
    previous = load_verification(previous_id)
    fingerprint = _sha256_json(
        {
            "verificationId": previous.verificationId,
            "status": previous.status,
            "blockers": previous.qualityGate.blockers,
            "evidence": [item.sha256 for item in previous.evidence],
        }
    )
    return ReverificationLink(
        previousVerificationId=previous.verificationId,
        previousVerdict=previous.status,
        failureFingerprint=fingerprint,
        repairSource=None,
    )


def _verification_status(decision: str) -> str:
    if decision in {"PASS", "PASS_WITH_WARNING"}:
        return "PASS"
    if decision in {"BLOCKED", "MANUAL_REVIEW"}:
        return "BLOCKED"
    return "FAIL"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(document: dict) -> str:
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _markdown(report: VerificationReport) -> str:
    rows = "\n".join(
        f"| {item.name} | {item.testType} | {item.status} | {item.durationMs} |"
        for item in report.projectQa.results
    )
    blockers = "\n".join(f"- {value}" for value in report.qualityGate.blockers) or "- None"
    return (
        f"# EagleEye Verification — {report.verificationId}\n\n"
        f"- Verdict: **{report.status}**\n"
        f"- Base: `{report.gitContext.baseCommit}`\n"
        f"- Head: `{report.gitContext.headCommit}`\n"
        f"- Diff SHA-256: `{report.gitContext.diffSha256}`\n"
        f"- Manifest SHA-256: `{report.manifestSha256}`\n\n"
        "| Suite | Type | Result | Duration ms |\n"
        "|---|---|---:|---:|\n"
        f"{rows}\n\n## Blockers\n\n{blockers}\n"
    )


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat()
