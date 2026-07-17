from __future__ import annotations

import sys
from hashlib import sha256
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.desktop_adapter import (
    DesktopTargetValidationError,
    UnknownDesktopTargetError,
    run_desktop_target,
)
from app.desktop_models import DesktopRunRequest


def _write_registry(root: Path, script: Path, *, timeout: float = 5) -> Path:
    registry = root.parent / "desktop-targets.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "targets": {
                    "fixture": {
                        "root": str(root),
                        "workingDirectory": str(root),
                        "command": [sys.executable, str(script)],
                        "timeoutSeconds": timeout,
                        "maxOutputBytes": 4096,
                        "maxArtifacts": 4,
                        "maxArtifactBytes": 4096,
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return registry


def _run(tmp_path: Path, script_body: str, *, timeout: float = 5):
    target = tmp_path / "target"
    target.mkdir()
    script = target / "fixture.py"
    script.write_text(script_body, encoding="utf-8")
    registry = _write_registry(target, script, timeout=timeout)
    request = DesktopRunRequest.model_validate({"targetId": "fixture", "runId": "desktop-run"})
    return run_desktop_target(
        request,
        registry_path=registry,
        artifacts_root=tmp_path / "eagleeye-artifacts",
        allowed_system_executables=(Path(sys.executable),),
    )


def test_fixed_target_success_imports_and_rehashes_artifact(tmp_path) -> None:
    result = _run(
        tmp_path,
        """
import json
from pathlib import Path

artifact = Path("capture.png")
artifact.write_bytes(b"fixture-png")
print("token=do-not-return-this")
fixture_jwt_header = "eyJhbGciOiJIUzI1NiJ9"
fixture_jwt_body = "eyJzdWIiOiJmaXh0dXJlIn0"
print("jwt=" + ".".join((fixture_jwt_header, fixture_jwt_body, "signaturefixture")))
print("github=" + "ghp_" + "abcdefghijklmnopqrstuvwxyz123456")
fixture_aws_prefix = "AK" + "IA"
fixture_aws_body = "ABCDEFGHIJKLMNOP"
print("aws=" + fixture_aws_prefix + fixture_aws_body)
print("url=https://example.test/callback?code=oauth-code-value&safe=yes")
print(json.dumps({
    "ok": True,
    "packaged": True,
    "artifacts": [{
        "kind": "screenshot",
        "path": str(artifact.resolve()),
        "mimeType": "application/untrusted",
        "sha256": "untrusted",
    }],
}))
""",
    )

    assert result.status == "passed"
    assert result.exit_code == 0
    assert result.timed_out is False
    assert "do-not-return-this" not in result.stdout
    assert "signaturefixture" not in result.stdout
    assert "ghp_" not in result.stdout
    assert ("AK" + "IA" + "ABCDEFGHIJKLMNOP") not in result.stdout
    assert "oauth-code-value" not in result.stdout
    assert "token=[REDACTED]" in result.stdout
    assert "code=[REDACTED]&safe=yes" in result.stdout
    assert len(result.evidence) == 1
    artifact = result.evidence[0]
    assert artifact.kind == "screenshot"
    assert artifact.mime_type == "image/png"
    assert artifact.byte_size == len(b"fixture-png")
    assert artifact.sha256 == sha256(b"fixture-png").hexdigest()
    assert Path(artifact.path).is_relative_to((tmp_path / "eagleeye-artifacts").resolve())


def test_nonzero_exit_is_failed_even_with_terminal_json(tmp_path) -> None:
    result = _run(
        tmp_path,
        """
import json
import sys

print(json.dumps({"status": "failed", "summary": "fixture failed", "artifacts": []}))
sys.exit(7)
""",
    )

    assert result.status == "failed"
    assert result.exit_code == 7
    assert result.summary == "fixture failed"
    assert result.error == "Desktop command exited with code 7."


def test_unknown_target_and_request_extra_fields_are_rejected(tmp_path) -> None:
    root = tmp_path / "target"
    root.mkdir()
    script = root / "fixture.py"
    script.write_text("print('{}')", encoding="utf-8")
    registry = _write_registry(root, script)

    with pytest.raises(ValidationError):
        DesktopRunRequest.model_validate({"targetId": "fixture", "runId": "run", "command": ["malicious"]})
    with pytest.raises(UnknownDesktopTargetError):
        run_desktop_target(
            DesktopRunRequest.model_validate({"targetId": "missing", "runId": "run"}),
            registry_path=registry,
            artifacts_root=tmp_path / "artifacts",
            allowed_system_executables=(Path(sys.executable),),
        )


def test_artifact_path_escape_is_failed_without_copying(tmp_path) -> None:
    result = _run(
        tmp_path,
        """
import json
from pathlib import Path

artifact = Path("..") / "outside.png"
artifact.write_bytes(b"outside")
print(json.dumps({
    "ok": True,
    "artifacts": [{"kind": "screenshot", "path": str(artifact.resolve())}],
}))
""",
    )

    assert result.status == "failed"
    assert result.evidence == []
    assert result.error is not None and "escapes the target root" in result.error


def test_registered_command_argument_cannot_escape_target_root(tmp_path) -> None:
    root = tmp_path / "target"
    root.mkdir()
    outside_script = tmp_path / "outside.py"
    outside_script.write_text("print('{}')", encoding="utf-8")
    registry = _write_registry(root, outside_script)
    request = DesktopRunRequest.model_validate({"targetId": "fixture", "runId": "run"})

    with pytest.raises(DesktopTargetValidationError, match="command argument"):
        run_desktop_target(
            request,
            registry_path=registry,
            artifacts_root=tmp_path / "artifacts",
            allowed_system_executables=(Path(sys.executable),),
        )


def test_timeout_kills_process_and_returns_bounded_failure(tmp_path) -> None:
    result = _run(
        tmp_path,
        """
import time

print("starting", flush=True)
time.sleep(10)
""",
        timeout=0.1,
    )

    assert result.status == "failed"
    assert result.timed_out is True
    assert result.duration_ms < 5000
    assert result.error is not None and "timed out" in result.error
