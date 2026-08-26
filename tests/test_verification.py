from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import project_qa, storage, verification_service
from app.main import app
from app.mcp_entrypoint import verify_project_change
from app.models import EvidenceArtifact, RunResult
from app.verification_git import collect_git_context
from app.verification_manifest import verify_manifest_file
from app.verification_models import VerificationRequest
from app.verification_service import run_verification


def _git(project: Path, *args: str) -> str:
    executable = shutil.which("git")
    assert executable is not None
    result = subprocess.run(  # noqa: S603 - test-only fixed git executable and argv
        [executable, *args],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    return result.stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, str, str]:
    project = tmp_path / "authorized-project"
    project.mkdir()
    _git(project, "init")
    _git(project, "config", "user.email", "verification@example.invalid")
    _git(project, "config", "user.name", "EagleEye Verification Test")
    manifest = project / ".eagleeye" / "qa.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "suites": [
                    {
                        "id": "custom-unit",
                        "name": "Custom unit",
                        "testType": "unit",
                        "command": ["python", "-c", "print('verification-ok')"],
                        "required": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    target = project / "app.txt"
    target.write_text("before\n", encoding="utf-8")
    _git(project, "add", ".")
    _git(project, "commit", "-m", "initial")
    base = _git(project, "rev-parse", "HEAD")
    target.write_text("after\n", encoding="utf-8")
    _git(project, "add", "app.txt")
    _git(project, "commit", "-m", "change")
    head = _git(project, "rev-parse", "HEAD")
    return project, base, head


def _configure_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setattr(project_qa, "RUNS", tmp_path / "project-runs")
    monkeypatch.setattr(storage, "RUNS", tmp_path / "browser-runs")
    monkeypatch.setattr(verification_service, "VERIFICATIONS", tmp_path / "verifications")


def test_git_context_binds_base_head_and_diff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project, base, head = _repository(tmp_path)
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))

    context = collect_git_context(str(project), base_ref=base, head_ref=head)

    assert context.baseCommit == base
    assert context.headCommit == head
    assert context.changedFiles == ["app.txt"]
    assert context.dirty is False
    assert len(context.diffSha256) == 64


def test_git_context_rejects_dirty_tree_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project, base, head = _repository(tmp_path)
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    (project / "dirty.txt").write_text("uncommitted", encoding="utf-8")

    with pytest.raises(ValueError, match="dirty"):
        collect_git_context(str(project), base_ref=base, head_ref=head)


def test_git_context_fingerprints_explicit_dirty_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project, base, head = _repository(tmp_path)
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    (project / "dirty.txt").write_text("uncommitted", encoding="utf-8")

    context = collect_git_context(str(project), base_ref=base, head_ref=head, allow_dirty=True)

    assert context.dirty is True
    assert context.untrackedPresent is True
    assert context.workingTreeSha256 is not None
    assert "dirty.txt" in context.changedFiles


def test_verification_generates_hashed_manifest_and_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project, base, head = _repository(tmp_path)
    _configure_roots(monkeypatch, tmp_path)

    report = run_verification(
        VerificationRequest(
            projectRoot=str(project),
            authorized=True,
            baseRef=base,
            headRef=head,
            serviceType="business",
        )
    )

    assert report.status == "PASS"
    assert report.gitContext.headCommit == head
    assert report.evidence
    manifest = Path(report.manifestPath)
    assert manifest.is_file()
    assert verify_manifest_file(manifest)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    assert document["ai"]["authoritative"] is False
    assert document["repository"]["headCommit"] == head
    assert document["manifestSha256"] == report.manifestSha256
    copied = manifest.parent / report.evidence[0].path
    assert copied.is_file()
    assert hashlib.sha256(copied.read_bytes()).hexdigest() == report.evidence[0].sha256


def test_manifest_tampering_is_detected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project, base, head = _repository(tmp_path)
    _configure_roots(monkeypatch, tmp_path)
    report = run_verification(
        VerificationRequest(projectRoot=str(project), authorized=True, baseRef=base, headRef=head)
    )
    manifest = Path(report.manifestPath)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["verdict"]["warnings"].append("tampered")
    manifest.write_text(json.dumps(document), encoding="utf-8")

    assert verify_manifest_file(manifest) is False


def test_browser_failure_prevents_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project, base, head = _repository(tmp_path)
    _configure_roots(monkeypatch, tmp_path)
    session_id = "browser-session"
    browser_dir = storage.RUNS / session_id
    browser_dir.mkdir(parents=True)
    artifact_path = browser_dir / "failure.log"
    artifact_path.write_text("browser regression", encoding="utf-8")
    artifact_sha = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    result = RunResult(
        session_id=session_id,
        status="failed",
        duration_ms=25,
        error="checkout regression",
        evidence=[
            EvidenceArtifact(
                kind="log",
                path=str(artifact_path),
                mime_type="text/plain",
                byte_size=artifact_path.stat().st_size,
                sha256=artifact_sha,
                created_at="2026-08-26T00:00:00+00:00",
                capture_source="test-browser",
            )
        ],
    )
    monkeypatch.setattr(verification_service, "load_bundle", lambda _session_id: object())
    monkeypatch.setattr(verification_service, "run_bundle", lambda _bundle: result)

    report = run_verification(
        VerificationRequest(
            projectRoot=str(project),
            authorized=True,
            baseRef=base,
            headRef=head,
            browserSessionIds=[session_id],
        )
    )

    assert report.status != "PASS"
    assert any("browser" in item.relatedTestId for item in report.evidence if item.relatedTestId)


def test_reverification_links_previous_proof(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project, base, head = _repository(tmp_path)
    _configure_roots(monkeypatch, tmp_path)
    first = run_verification(
        VerificationRequest(projectRoot=str(project), authorized=True, baseRef=base, headRef=head)
    )
    (project / "app.txt").write_text("repaired\n", encoding="utf-8")
    _git(project, "add", "app.txt")
    _git(project, "commit", "-m", "repair")
    repaired_head = _git(project, "rev-parse", "HEAD")

    second = run_verification(
        VerificationRequest(
            projectRoot=str(project),
            authorized=True,
            baseRef=head,
            headRef=repaired_head,
            previousVerificationId=first.verificationId,
        )
    )

    assert second.reverification is not None
    assert second.reverification.previousVerificationId == first.verificationId
    assert len(second.reverification.failureFingerprint) == 64


def test_verification_api_requires_explicit_authorization() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/verifications",
        json={"projectRoot": ".", "authorized": False},
    )

    assert response.status_code == 422


def test_mcp_verification_requires_explicit_authorization() -> None:
    with pytest.raises(PermissionError, match="authorization"):
        verify_project_change(".", authorized=False)
