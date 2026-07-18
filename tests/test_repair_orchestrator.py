from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import pytest

from app.repair_models import (
    FreshEvalAttestation,
    RepairCapabilities,
    RepairCapability,
    RepairLimits,
    RepairPlan,
    RepairProject,
    RepairProjects,
    RepairRequest,
    VerificationCommand,
)
from app.repair_orchestrator import RepairOrchestrator
from app.repair_policy import RepairPolicy, load_repair_projects

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="Git is required")
NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
FINGERPRINT = hashlib.sha256(b"deterministic-failure").hexdigest()
EVIDENCE_SHA = hashlib.sha256(b"evaluation-evidence").hexdigest()


def test_load_repair_projects_resolves_relative_root_from_profile_directory(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    config = profiles / "repair-projects.yaml"
    config.write_text(
        """
version: "1.0"
projects:
  - id: fixture
    root: ../repository
    enabled: true
    allowedEnvironments: [local]
    verification:
      - name: verify
        argv: [uv, run, pytest, -q]
        timeoutSeconds: 30
""".strip(),
        encoding="utf-8",
    )

    projects = load_repair_projects(config)

    assert projects.projects[0].root == repository.resolve()


def _git(root: Path, *arguments: str) -> None:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("Git is required for this test")
    subprocess.run(  # noqa: S603 -- test helper uses fixed git setup commands
        [executable, "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )


def _repository(tmp_path: Path, files: dict[str, bytes] | None = None) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    payloads = files or {"target.txt": b"VALUE = 1\n"}
    for relative, body in payloads.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "eagleeye-test@example.invalid")
    _git(root, "config", "user.name", "EagleEye Test")
    _git(root, "add", "--all")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def _policy(
    root: Path,
    *,
    expected: str = "VALUE = 2\n",
    verifier=lambda *_: True,
    verification: VerificationCommand | None = None,
) -> RepairPolicy:
    verification = verification or VerificationCommand(
        name="content-check",
        argv=[
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"raise SystemExit(0 if Path('target.txt').read_text() == {expected!r} else 1)"
            ),
        ],
        timeoutSeconds=30,
    )
    capabilities = RepairCapabilities(
        version="test",
        featureFlag="EAGLEEYE_SELF_REPAIR_ENABLED",
        limits=RepairLimits(),
        capabilities=[
            RepairCapability(
                provider="codex-agent",
                models=["gpt-5.6-sol"],
                automaticApplyAllowed=True,
            )
        ],
    )
    projects = RepairProjects(
        version="test",
        projects=[
            RepairProject(
                id="fixture",
                root=root,
                verification=[verification],
            )
        ],
    )
    return RepairPolicy(
        capabilities,
        projects,
        attestation_verifier=verifier,
        clock=lambda: NOW,
    )


def _attestation() -> FreshEvalAttestation:
    return FreshEvalAttestation(
        id="eval-attestation-0001",
        projectId="fixture",
        failureFingerprint=FINGERPRINT,
        evidenceSha256=EVIDENCE_SHA,
        decision="eligible_for_repair",
        issuedAt=NOW - timedelta(seconds=30),
        expiresAt=NOW + timedelta(minutes=2),
    )


def _request(
    *,
    mode: str = "apply",
    explicit: bool = True,
    attestation: FreshEvalAttestation | None = None,
    model: str = "gpt-5.6-sol",
) -> RepairRequest:
    return RepairRequest(
        projectId="fixture",
        environment="local",
        provider="codex-agent",
        model=model,
        requestedMode=mode,
        explicitApplyRequested=explicit,
        failureFingerprint=FINGERPRINT,
        failureSummary="A deterministic fixture assertion failed.",
        evidencePaths=["artifacts/result.json"],
        attestation=attestation,
    )


def _plan(root: Path, replacement: str, *, path: str = "target.txt") -> RepairPlan:
    target = root / path
    expected_sha = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else "0" * 64
    return RepairPlan.model_validate(
        {
            "summary": "Replace the exact failing fixture value.",
            "confidence": 0.99,
            "files": [
                {
                    "operation": "replace",
                    "path": path,
                    "expectedSha256": expected_sha,
                    "replacements": [{"old": "VALUE = 1", "new": replacement}],
                }
            ],
        }
    )


def _assert_audit(response) -> dict:
    audit_path = Path(response.auditPath)
    body = audit_path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == response.auditSha256
    assert audit_path.with_suffix(".sha256").read_text().startswith(response.auditSha256)
    return json.loads(body)


def test_missing_attestation_forces_proposal_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    orchestrator = RepairOrchestrator(
        lambda _: _plan(root, "VALUE = 2"),
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    )

    response = orchestrator.execute(_request(attestation=None))

    assert response.status == "PROPOSED"
    assert response.effectiveMode == "proposal_only"
    assert "attestation is missing" in " ".join(response.reasons)
    assert (root / "target.txt").read_text() == "VALUE = 1\n"
    assert response.attempts[0].status == "PROPOSED"
    _assert_audit(response)


def test_apply_requires_clean_allowlisted_git_and_writes_hashed_audit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    orchestrator = RepairOrchestrator(
        lambda _: _plan(root, "VALUE = 2"),
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    )

    response = orchestrator.execute(_request(attestation=_attestation()))

    assert response.status == "APPLIED"
    assert response.effectiveMode == "apply"
    assert (root / "target.txt").read_text() == "VALUE = 2\n"
    attempt = response.attempts[0]
    assert attempt.status == "APPLIED"
    assert attempt.verification[0].returnCode == 0
    checkpoint = Path(attempt.checkpointPath)
    assert checkpoint.is_dir()
    assert not list(checkpoint.parent.glob(".checkpoint-*.tmp"))
    assert (
        hashlib.sha256((checkpoint / "files" / "target.txt").read_bytes()).hexdigest()
        == (attempt.preimageSha256["target.txt"])
    )
    audit = _assert_audit(response)
    assert audit["request"]["evidencePathHashes"] != ["artifacts/result.json"]
    assert "old" not in json.dumps(audit["plan"])


def test_no_safe_repair_is_a_normal_zero_write_result(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    orchestrator = RepairOrchestrator(
        lambda _: RepairPlan(
            action="no_safe_repair",
            summary="Evidence is insufficient for a bounded eligible edit.",
            confidence=0.15,
            files=[],
        ),
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    )

    response = orchestrator.execute(_request(attestation=_attestation()))

    assert response.status == "NO_SAFE_REPAIR"
    assert response.effectiveMode == "proposal_only"
    assert response.attempts[0].status == "NO_SAFE_REPAIR"
    assert response.plan is not None and response.plan.files == []
    assert (root / "target.txt").read_text() == "VALUE = 1\n"


def test_project_lock_rejects_a_concurrent_repair(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    started = Event()
    release = Event()

    def blocking_planner(_):
        started.set()
        assert release.wait(timeout=10)
        return _plan(root, "VALUE = 2")

    first = RepairOrchestrator(
        blocking_planner,
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    )
    second = RepairOrchestrator(
        lambda _: _plan(root, "VALUE = 2"),
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    )
    request = _request(mode="proposal_only")

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(first.execute, request)
        assert started.wait(timeout=10)
        blocked = second.execute(request)
        release.set()
        completed = future.result(timeout=10)

    assert blocked.status == "DENIED"
    assert "already active" in " ".join(blocked.reasons)
    assert completed.status == "PROPOSED"


def test_verification_side_effects_stay_in_disposable_worktree(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    verification = VerificationCommand(
        name="side-effecting-failure",
        argv=[
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "Path('verification-side-effect.txt').write_text('isolated'); "
                "raise SystemExit(1)"
            ),
        ],
        timeoutSeconds=30,
    )
    orchestrator = RepairOrchestrator(
        lambda _: _plan(root, "VALUE = 2"),
        _policy(root, verification=verification),
        artifact_root=tmp_path / "artifacts",
    )

    response = orchestrator.execute(_request(attestation=_attestation()))

    assert response.status == "ROLLED_BACK"
    assert all(item.rollbackVerified is True for item in response.attempts)
    assert not (root / "verification-side-effect.txt").exists()
    assert (root / "target.txt").read_text() == "VALUE = 1\n"


def test_dirty_git_is_denied_before_planner(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    (root / "target.txt").write_text("DIRTY\n")
    called = False

    def planner(_):
        nonlocal called
        called = True
        return _plan(root, "VALUE = 2")

    response = RepairOrchestrator(
        planner,
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    ).execute(_request(attestation=_attestation()))

    assert response.status == "DENIED"
    assert response.effectiveMode == "denied"
    assert called is False
    assert "Dirty Git" in " ".join(response.reasons)
    _assert_audit(response)


def test_feature_flag_and_exact_model_allowlist_fail_closed(monkeypatch, tmp_path: Path) -> None:
    root = _repository(tmp_path)

    def planner(_):
        return _plan(root, "VALUE = 2")

    orchestrator = RepairOrchestrator(
        planner,
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    )

    monkeypatch.delenv("EAGLEEYE_SELF_REPAIR_ENABLED", raising=False)
    disabled = orchestrator.execute(_request(attestation=_attestation()))
    assert disabled.status == "DENIED"
    assert "feature flag" in " ".join(disabled.reasons)

    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    wrong_model = orchestrator.execute(_request(attestation=_attestation(), model="gpt-5.6-sol-preview"))
    assert wrong_model.status == "DENIED"
    assert "exact repair allowlist" in " ".join(wrong_model.reasons)


@pytest.mark.parametrize(
    ("files", "path", "replacement", "reason"),
    [
        (
            {"target.txt": b"VALUE = 1\n", "package-lock.json": b"VALUE = 1\n"},
            "package-lock.json",
            "VALUE = 2",
            "lockfiles are forbidden",
        ),
        ({"target.txt": b"VALUE = 1\n"}, "../outside.txt", "VALUE = 2", "relative in-root"),
        (
            {"target.txt": b"VALUE = 1\n"},
            "target.txt",
            "password = supersecretvalue",
            "apparent secrets",
        ),
        (
            {"target.txt": b"VALUE = 1\n", "image.bin": b"VALUE = 1\n"},
            "image.bin",
            "VALUE = 2",
            "Binary files are forbidden",
        ),
    ],
)
def test_unsafe_plans_are_rejected_without_writes(
    monkeypatch,
    tmp_path: Path,
    files: dict[str, bytes],
    path: str,
    replacement: str,
    reason: str,
) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path, files)

    def planner(_):
        target = root / path
        expected = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else "0" * 64
        return {
            "summary": "Unsafe planner canary",
            "confidence": 0.9,
            "files": [
                {
                    "path": path,
                    "expectedSha256": expected,
                    "replacements": [{"old": "VALUE = 1", "new": replacement}],
                }
            ],
        }

    response = RepairOrchestrator(
        planner,
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    ).execute(_request(mode="proposal_only"))

    assert response.status == "FAILED"
    assert len(response.attempts) == 2
    assert all(attempt.status == "PLAN_REJECTED" for attempt in response.attempts)
    assert reason in " ".join(attempt.reason for attempt in response.attempts)
    assert (root / "target.txt").read_bytes() == files["target.txt"]


def test_symlink_target_is_rejected_when_supported(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    link = root / "link.txt"
    try:
        os.symlink(root / "target.txt", link)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    _git(root, "add", "link.txt")
    _git(root, "commit", "-q", "-m", "symlink fixture")

    response = RepairOrchestrator(
        lambda _: _plan(root, "VALUE = 2", path="link.txt"),
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    ).execute(_request(mode="proposal_only"))

    assert response.status == "FAILED"
    assert "Symlink" in " ".join(attempt.reason for attempt in response.attempts)
    assert (root / "target.txt").read_text() == "VALUE = 1\n"


def test_failed_verification_rolls_back_then_second_attempt_applies(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)

    def planner(input_value):
        replacement = "VALUE = broken" if input_value.attempt == 1 else "VALUE = 2"
        return _plan(root, replacement)

    response = RepairOrchestrator(
        planner,
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    ).execute(_request(attestation=_attestation()))

    assert response.status == "APPLIED"
    assert [attempt.status for attempt in response.attempts] == ["ROLLED_BACK", "APPLIED"]
    assert response.attempts[0].rollbackVerified is True
    assert (
        response.attempts[0].preimageSha256["target.txt"] == response.attempts[1].preimageSha256["target.txt"]
    )
    assert (root / "target.txt").read_text() == "VALUE = 2\n"
    _assert_audit(response)


def test_stale_attestation_and_missing_authenticity_verifier_remain_proposal_only(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    stale = _attestation().model_copy(
        update={
            "issuedAt": NOW - timedelta(minutes=10),
            "expiresAt": NOW + timedelta(minutes=1),
        }
    )
    policy = _policy(root, verifier=None)
    response = RepairOrchestrator(
        lambda _: _plan(root, "VALUE = 2"),
        policy,
        artifact_root=tmp_path / "artifacts",
    ).execute(_request(attestation=stale))

    assert response.status == "PROPOSED"
    combined = " ".join(response.reasons)
    assert "stale" in combined
    assert "No trusted evaluation attestation verifier" in combined
    assert (root / "target.txt").read_text() == "VALUE = 1\n"


def test_production_and_nonlocal_requests_are_denied(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(tmp_path)
    orchestrator = RepairOrchestrator(
        lambda _: _plan(root, "VALUE = 2"),
        _policy(root),
        artifact_root=tmp_path / "artifacts",
    )

    production = _request(attestation=_attestation()).model_copy(
        update={"environment": "production", "production": True}
    )
    response = orchestrator.execute(production)

    assert response.status == "DENIED"
    assert "non-production local" in " ".join(response.reasons)
    assert (root / "target.txt").read_text() == "VALUE = 1\n"


def test_security_boundaries_build_controls_and_delete_operations_are_rejected(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    root = _repository(
        tmp_path,
        {
            "target.txt": b"VALUE = 1\n",
            ".github/workflows/verify.yml": b"VALUE = 1\n",
            "app/ai_advisor.py": b"VALUE = 1\n",
            "app/mcp_server.py": b"VALUE = 1\n",
            "app/providers.py": b"VALUE = 1\n",
            "app/repair_policy.py": b"VALUE = 1\n",
            "app/main.py": b"VALUE = 1\n",
            "profiles/desktop-targets.yaml": b"VALUE = 1\n",
            "package.json": b"VALUE = 1\n",
            "scripts/run_ai_safety_evals.py": b"VALUE = 1\n",
            "tests/test_api.py": b"VALUE = 1\n",
        },
    )
    policy = _policy(root)
    request = _request(mode="proposal_only")
    protected_responses = [
        RepairOrchestrator(
            lambda _, path=path: _plan(root, "VALUE = 2", path=path),
            policy,
            artifact_root=tmp_path / "artifacts",
        ).execute(request)
        for path in (
            ".github/workflows/verify.yml",
            "app/ai_advisor.py",
            "app/main.py",
            "app/mcp_server.py",
            "app/providers.py",
            "app/repair_policy.py",
            "package.json",
            "profiles/desktop-targets.yaml",
            "scripts/run_ai_safety_evals.py",
            "tests/test_api.py",
        )
    ]

    expected_sha = hashlib.sha256((root / "target.txt").read_bytes()).hexdigest()

    def delete_planner(_):
        return {
            "summary": "Forbidden deletion",
            "confidence": 1,
            "files": [
                {
                    "operation": "delete",
                    "path": "target.txt",
                    "expectedSha256": expected_sha,
                    "replacements": [{"old": "VALUE = 1", "new": ""}],
                }
            ],
        }

    deletion = RepairOrchestrator(
        delete_planner,
        policy,
        artifact_root=tmp_path / "artifacts",
    ).execute(request)

    assert all(response.status == "FAILED" for response in protected_responses)
    assert all(
        "safety policy" in " ".join(item.reason for item in response.attempts)
        for response in protected_responses
    )
    assert deletion.status == "FAILED"
    assert all(item.status == "PLAN_REJECTED" for item in deletion.attempts)
    assert (root / "target.txt").read_text() == "VALUE = 1\n"


def test_changed_line_and_total_byte_budgets_are_enforced(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_SELF_REPAIR_ENABLED", "1")
    line_root = _repository(
        tmp_path / "line-budget",
        {"target.txt": (("A\n" * 101) + "VALUE = 1\n").encode()},
    )
    original = line_root.joinpath("target.txt").read_text()
    expected_sha = hashlib.sha256(original.encode()).hexdigest()

    def line_planner(_):
        return {
            "summary": "Oversized changed-line plan",
            "confidence": 1,
            "files": [
                {
                    "path": "target.txt",
                    "expectedSha256": expected_sha,
                    "replacements": [{"old": "A\n" * 101, "new": "B\n" * 101}],
                }
            ],
        }

    line_response = RepairOrchestrator(
        line_planner,
        _policy(line_root),
        artifact_root=tmp_path / "line-artifacts",
    ).execute(_request(mode="proposal_only"))

    byte_root = _repository(
        tmp_path / "byte-budget",
        {"target.txt": b"VALUE = 1\n" + (b"A" * 262_144)},
    )
    byte_response = RepairOrchestrator(
        lambda _: _plan(byte_root, "VALUE = 2"),
        _policy(byte_root),
        artifact_root=tmp_path / "byte-artifacts",
    ).execute(_request(mode="proposal_only"))

    assert line_response.status == "FAILED"
    assert "changed-line limit" in " ".join(item.reason for item in line_response.attempts)
    assert byte_response.status == "FAILED"
    assert "oversized" in " ".join(item.reason for item in byte_response.attempts)
    assert line_root.joinpath("target.txt").read_text() == original
