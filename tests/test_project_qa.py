from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import mcp_server, project_qa
from app.main import app
from app.project_qa import discover_project, load_project_run, run_project
from app.project_qa_models import ProjectRunRequest


def _manifest_project(tmp_path: Path, command: list[str]) -> Path:
    project = tmp_path / "authorized-project"
    manifest = project / ".eagleeye" / "qa.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "suites": [
                    {
                        "id": "custom-unit",
                        "name": "Custom unit",
                        "testType": "unit",
                        "command": command,
                        "required": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return project


def test_discovery_detects_node_scripts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = tmp_path / "node-project"
    project.mkdir()
    (project / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'", encoding="utf-8")
    (project / "package.json").write_text(
        json.dumps({"scripts": {"lint": "eslint .", "test:e2e": "playwright test"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))

    discovered = discover_project(str(project))

    assert discovered.ecosystems == ["node"]
    assert [suite.id for suite in discovered.suites] == ["node-lint", "node-test-e2e"]
    runner = "pnpm.cmd" if os.name == "nt" else "pnpm"
    assert discovered.suites[0].command == [runner, "run", "lint"]


def test_discovery_includes_custom_node_tests_but_skips_interactive_scripts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = tmp_path / "node-project"
    project.mkdir()
    (project / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'", encoding="utf-8")
    (project / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "test": "vitest run",
                    "test:server": "vitest run server",
                    "test:qa": "playwright test qa",
                    "test:watch": "vitest",
                    "test:e2e:ui": "playwright test --ui",
                    "dev": "vite",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))

    discovered = discover_project(str(project))

    assert [suite.id for suite in discovered.suites] == [
        "node-test",
        "node-test-qa",
        "node-test-server",
    ]
    assert [suite.testType for suite in discovered.suites] == ["unit", "test", "test"]


def test_manifest_rejects_unapproved_executable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _manifest_project(tmp_path, ["curl", "https://example.invalid"])
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))

    with pytest.raises(ValueError, match="Executable is not allowed"):
        discover_project(str(project))


def test_run_writes_hashed_redacted_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = Path(sys.executable).name
    project = _manifest_project(
        tmp_path,
        [executable, "-c", "print('api_key=should-not-survive')"],
    )
    run_root = tmp_path / "runs"
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setattr("app.project_qa.RUNS", run_root)

    report = run_project(
        ProjectRunRequest(
            projectRoot=str(project),
            authorized=True,
            suiteIds=["custom-unit"],
            timeoutSeconds=30,
        )
    )

    assert report.status == "PASS"
    assert report.qualityGate.decision == "PASS"
    evidence = Path(report.results[0].evidencePath).read_bytes()
    assert b"should-not-survive" not in evidence
    assert b"[REDACTED]" in evidence
    assert report.results[0].evidenceSha256 == hashlib.sha256(evidence).hexdigest()
    assert load_project_run(report.runId).runId == report.runId


def test_api_requires_authorization_and_returns_discovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = tmp_path / "python-project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='sample'\nversion='0.1.0'", encoding="utf-8")
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    client = TestClient(app)

    denied = client.post(
        "/api/v1/project-qa/discover",
        json={"projectRoot": str(project), "authorized": False},
    )
    allowed = client.post(
        "/api/v1/project-qa/discover",
        json={"projectRoot": str(project), "authorized": True},
    )

    assert denied.status_code == 422
    assert allowed.status_code == 200
    assert allowed.json()["ecosystems"] == ["python"]


def test_project_root_is_confined(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(allowed))

    with pytest.raises(PermissionError, match="outside"):
        discover_project(str(outside))


def test_project_root_defaults_to_repository_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    project = repository / "project"
    outside = tmp_path / "outside"
    project.mkdir(parents=True)
    outside.mkdir()
    monkeypatch.delenv("EAGLEEYE_PROJECT_ROOTS", raising=False)
    monkeypatch.setattr(project_qa, "ROOT", repository)

    assert discover_project(str(project)).projectRoot == str(project)
    with pytest.raises(PermissionError, match="outside"):
        discover_project(str(outside))


def test_project_root_rejects_allowed_prefix_sibling(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    allowed = tmp_path / "project"
    prefix_sibling = tmp_path / "project-private"
    allowed.mkdir()
    prefix_sibling.mkdir()
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(allowed))

    with pytest.raises(PermissionError, match="outside"):
        discover_project(str(prefix_sibling))


def test_project_root_rejects_symlink_escape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    link = allowed / "linked-outside"
    allowed.mkdir()
    outside.mkdir()
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this host")
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(allowed))

    with pytest.raises(PermissionError, match="outside"):
        discover_project(str(link))


def test_python3_executable_is_allowed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _manifest_project(tmp_path, ["python3", "-c", "print('ok')"])
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))

    discovered = discover_project(str(project))

    assert discovered.suites[0].command[0] == "python3"


def test_command_rejects_control_characters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = _manifest_project(tmp_path, ["python", "-c", "print(1)\nprint(2)"])
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))

    with pytest.raises(ValueError, match="control characters"):
        discover_project(str(project))


def test_load_project_run_rejects_invalid_id() -> None:
    with pytest.raises(ValueError, match="Invalid run id"):
        load_project_run("../escape")


def test_suite_temp_uses_system_tempdir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = Path(sys.executable).name
    project = _manifest_project(
        tmp_path,
        [executable, "-c", "import os; print(os.environ['TEMP']); print(os.environ['TMPDIR'])"],
    )
    run_root = tmp_path / "runs"
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setattr("app.project_qa.RUNS", run_root)

    report = run_project(
        ProjectRunRequest(
            projectRoot=str(project),
            authorized=True,
            suiteIds=["custom-unit"],
            timeoutSeconds=30,
        )
    )

    evidence = Path(report.results[0].evidencePath).read_text(encoding="utf-8")
    temp_root = str(project_qa._suite_temp_dir(report.runId, "custom-unit"))
    assert temp_root in evidence
    assert report.status == "PASS"
    assert not Path(temp_root).exists()


def test_windows_suite_temp_path_is_short_enough_for_nested_test_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if os.name != "nt":
        pytest.skip("Windows path-length regression")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    suite_temp = project_qa._suite_temp_dir("a" * 32, "python-pytest")

    assert suite_temp == tmp_path / "EagleEye" / "q" / ("a" * 12) / "0285ef919ba9"
    assert len(str(suite_temp)) < len(str(tmp_path)) + 48


def test_suite_timeout_terminates_process_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = Path(sys.executable).name
    project = _manifest_project(
        tmp_path,
        [executable, "-c", "import time; time.sleep(30)"],
    )
    run_root = tmp_path / "runs"
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setattr("app.project_qa.RUNS", run_root)

    report = run_project(
        ProjectRunRequest(
            projectRoot=str(project),
            authorized=True,
            suiteIds=["custom-unit"],
            timeoutSeconds=5,
        )
    )

    assert report.results[0].status == "INFRA_ERROR"
    assert report.results[0].exitCode is None
    assert "timeout" in (report.results[0].errorMessage or "").lower()
    evidence = Path(report.results[0].evidencePath).read_text(encoding="utf-8")
    assert "timed out after 5s" in evidence


def test_missing_suite_executable_returns_infra_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _manifest_project(tmp_path, ["python", "-c", "print('never-starts')"])
    run_root = tmp_path / "runs"
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setattr("app.project_qa.RUNS", run_root)

    def missing_popen(*args, **kwargs):  # noqa: ANN002, ANN003
        raise FileNotFoundError("simulated missing executable")

    monkeypatch.setattr(project_qa.subprocess, "Popen", missing_popen)

    report = run_project(
        ProjectRunRequest(
            projectRoot=str(project),
            authorized=True,
            suiteIds=["custom-unit"],
            timeoutSeconds=30,
        )
    )

    result = report.results[0]
    assert result.status == "INFRA_ERROR"
    assert result.exitCode is None
    assert result.errorMessage == "Unable to start suite executable: FileNotFoundError."
    assert Path(result.evidencePath).is_file()


def test_suite_output_is_bounded_and_hashed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = Path(sys.executable).name
    project = _manifest_project(
        tmp_path,
        [executable, "-c", "print('X' * (3 * 1024 * 1024))"],
    )
    run_root = tmp_path / "runs"
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setattr("app.project_qa.RUNS", run_root)
    monkeypatch.setattr("app.project_qa.MAX_LOG_BYTES", 8_192)

    report = run_project(
        ProjectRunRequest(
            projectRoot=str(project),
            authorized=True,
            suiteIds=["custom-unit"],
            timeoutSeconds=30,
        )
    )

    evidence = Path(report.results[0].evidencePath).read_bytes()
    assert len(evidence) < 16_384
    assert b"[EagleEye: output truncated at 2 MiB]" in evidence
    assert report.results[0].evidenceSha256 == hashlib.sha256(evidence).hexdigest()


def test_run_suite_disables_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = Path(sys.executable).name
    project = _manifest_project(tmp_path, [executable, "-c", "print('shell-check')"])
    run_root = tmp_path / "runs"
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setattr("app.project_qa.RUNS", run_root)
    calls: list[dict[str, object]] = []
    real_popen = subprocess.Popen

    def tracking_popen(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(kwargs)
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(project_qa.subprocess, "Popen", tracking_popen)

    report = run_project(
        ProjectRunRequest(
            projectRoot=str(project),
            authorized=True,
            suiteIds=["custom-unit"],
            timeoutSeconds=30,
        )
    )

    assert report.status == "PASS"
    assert calls
    assert calls[0]["shell"] is False


def test_mcp_project_qa_requires_authorization(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = tmp_path / "mcp-project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='sample'\nversion='0.1.0'", encoding="utf-8")
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))

    with pytest.raises(PermissionError, match="authorization"):
        mcp_server.discover_project_qa(str(project), authorized=False)
    with pytest.raises(PermissionError, match="authorization"):
        mcp_server.run_project_qa(str(project), authorized=False)

    discovered = mcp_server.discover_project_qa(str(project), authorized=True)
    assert discovered["ecosystems"] == ["python"]


def test_minimal_env_forwards_uv_project_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    venv_path = str(Path.cwd() / "example-venv")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", venv_path)
    monkeypatch.setenv("VIRTUAL_ENV", venv_path)
    monkeypatch.setenv("SECRET_TOKEN", "must-not-leak")

    environment = project_qa._minimal_env()

    assert environment["UV_PROJECT_ENVIRONMENT"] == venv_path
    assert environment["VIRTUAL_ENV"] == venv_path
    assert "SECRET_TOKEN" not in environment
    assert environment["CI"] == "1"


def test_api_bounded_run_and_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = Path(sys.executable).name
    project = _manifest_project(tmp_path, [executable, "-c", "print('api-run')"])
    run_root = tmp_path / "runs"
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.setattr("app.project_qa.RUNS", run_root)
    client = TestClient(app)

    created = client.post(
        "/api/v1/project-qa/runs",
        json={
            "projectRoot": str(project),
            "authorized": True,
            "suiteIds": ["custom-unit"],
            "timeoutSeconds": 30,
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["status"] == "PASS"
    assert len(payload["results"][0]["evidenceSha256"]) == 64

    loaded = client.get(f"/api/v1/project-qa/runs/{payload['runId']}")
    assert loaded.status_code == 200
    assert loaded.json()["runId"] == payload["runId"]
