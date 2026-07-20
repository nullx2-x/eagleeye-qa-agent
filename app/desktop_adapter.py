from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from .desktop_models import (
    DesktopCommandPayload,
    DesktopRunRequest,
    DesktopRunResult,
    DesktopTarget,
    DesktopTargetRegistry,
)
from .models import EvidenceArtifact
from .storage import RUNS, evidence_from_file, safe_id

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = ROOT / "profiles" / "desktop-targets.yaml"

_FORBIDDEN_EVAL_ARGUMENTS = {"-c", "/c", "-e", "--eval", "-p", "--print"}
_KIND_MIME_BY_SUFFIX = {
    ("screenshot", ".png"): "image/png",
    ("screenshot", ".jpg"): "image/jpeg",
    ("screenshot", ".jpeg"): "image/jpeg",
    ("video", ".webm"): "video/webm",
    ("video", ".mp4"): "video/mp4",
    ("log", ".log"): "text/plain",
    ("log", ".txt"): "text/plain",
    ("log", ".json"): "application/json",
    ("trace", ".zip"): "application/zip",
    ("trace", ".json"): "application/json",
}
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\b\s*([:=])\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_OPENAI_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_GITHUB_TOKEN = re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}\b")
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_URL_SECRET = re.compile(r"(?i)([?&](?:access_token|api[_-]?key|auth|code|key|secret|token)=)[^&#\s]+")


class UnknownDesktopTargetError(KeyError):
    """Raised when a request references a target absent from the fixed registry."""


class DesktopTargetValidationError(ValueError):
    """Raised when a registered command or artifact leaves its declared root."""


@dataclass(frozen=True)
class _ResolvedTarget:
    config: DesktopTarget
    root: Path
    working_directory: Path
    command: tuple[str, ...]


def load_desktop_registry(path: Path = DEFAULT_REGISTRY_PATH) -> DesktopTargetRegistry:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return DesktopTargetRegistry.model_validate(payload)


def run_desktop_target(
    request: DesktopRunRequest,
    *,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    artifacts_root: Path = RUNS,
    allowed_system_executables: tuple[Path, ...] | None = None,
) -> DesktopRunResult:
    registry = load_desktop_registry(registry_path)
    target = registry.targets.get(request.target_id)
    if target is None:
        raise UnknownDesktopTargetError(request.target_id)
    resolved = _resolve_target(
        target,
        registry_path=registry_path,
        allowed_system_executables=allowed_system_executables,
    )

    started = time.perf_counter()
    timed_out = False
    exit_code: int | None = None
    launch_error: str | None = None
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        try:
            process_options = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            process = subprocess.Popen(  # noqa: S603 -- argv comes only from the validated fixed registry
                list(resolved.command),
                cwd=resolved.working_directory,
                env=_minimal_environment(request.run_id),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                shell=False,
                **process_options,
            )
            try:
                exit_code = process.wait(timeout=resolved.config.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                _terminate_process_tree(process, request.run_id)
                try:
                    exit_code = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    exit_code = None
        except OSError:
            launch_error = "The registered desktop command could not be launched."

        raw_stdout = _read_capped(stdout_file, resolved.config.max_output_bytes)
        raw_stderr = _read_capped(stderr_file, resolved.config.max_output_bytes)

    duration_ms = round((time.perf_counter() - started) * 1000)
    stdout = _redact_output(raw_stdout)
    stderr = _redact_output(raw_stderr)
    if launch_error is not None:
        return _failed_result(request, duration_ms, stdout, stderr, exit_code, launch_error)
    if timed_out:
        return _failed_result(
            request,
            duration_ms,
            stdout,
            stderr,
            exit_code,
            f"Desktop command timed out after {resolved.config.timeout_seconds:g} seconds.",
            timed_out=True,
        )

    try:
        payload = _parse_terminal_payload(raw_stdout)
    except (ValueError, ValidationError):
        return _failed_result(
            request,
            duration_ms,
            stdout,
            stderr,
            exit_code,
            "Desktop command did not return valid terminal JSON.",
        )
    summary = _redact_output(payload.summary) if payload.summary is not None else None

    try:
        evidence = _import_artifacts(
            payload,
            resolved,
            run_id=request.run_id,
            artifacts_root=artifacts_root,
        )
    except (OSError, ValueError) as exc:
        return _failed_result(
            request,
            duration_ms,
            stdout,
            stderr,
            exit_code,
            f"Desktop artifact validation failed: {exc}",
            summary=summary,
        )

    if exit_code != 0:
        return _failed_result(
            request,
            duration_ms,
            stdout,
            stderr,
            exit_code,
            f"Desktop command exited with code {exit_code}.",
            evidence=evidence,
            summary=summary,
        )
    if not payload.passed:
        return _failed_result(
            request,
            duration_ms,
            stdout,
            stderr,
            exit_code,
            "Desktop command reported a failed outcome.",
            evidence=evidence,
            summary=summary,
        )
    return DesktopRunResult(
        target_id=request.target_id,
        run_id=request.run_id,
        status="passed",
        evidence=evidence,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
        summary=summary,
    )


def _resolve_target(
    target: DesktopTarget,
    *,
    registry_path: Path,
    allowed_system_executables: tuple[Path, ...] | None,
) -> _ResolvedTarget:
    registry_root = registry_path.resolve().parent
    root = _resolve_existing(target.root, registry_root)
    if not root.is_dir():
        raise DesktopTargetValidationError("Desktop target root is not a directory.")
    working_directory = _resolve_existing(target.working_directory, root)
    _require_inside(working_directory, root, "working directory")
    if not working_directory.is_dir():
        raise DesktopTargetValidationError("Desktop working directory is not a directory.")

    allowed = _resolve_system_executables(allowed_system_executables)
    executable = _resolve_executable(target.command[0], working_directory, root, allowed)
    command = [str(executable)]
    for argument in target.command[1:]:
        if argument.casefold() in _FORBIDDEN_EVAL_ARGUMENTS:
            raise DesktopTargetValidationError("Inline command evaluation is not allowed.")
        if _looks_like_path(argument, working_directory):
            resolved_argument = _resolve_existing(Path(argument), working_directory)
            _require_inside(resolved_argument, root, "command argument")
            command.append(str(resolved_argument))
        else:
            command.append(argument)
    return _ResolvedTarget(target, root, working_directory, tuple(command))


def _resolve_system_executables(configured: tuple[Path, ...] | None) -> tuple[Path, ...]:
    candidates: tuple[Path, ...]
    if configured is None:
        node = shutil.which("node", path=os.environ.get("PATH"))
        candidates = (Path(node),) if node else ()
    else:
        candidates = configured
    resolved: list[Path] = []
    for candidate in candidates:
        try:
            path = candidate.resolve(strict=True)
        except OSError as exc:
            raise DesktopTargetValidationError("An allowed system executable does not exist.") from exc
        if not path.is_file():
            raise DesktopTargetValidationError("An allowed system executable is not a file.")
        resolved.append(path)
    return tuple(resolved)


def _resolve_executable(
    value: str,
    working_directory: Path,
    root: Path,
    allowed_system_executables: tuple[Path, ...],
) -> Path:
    requested = Path(value)
    if not requested.is_absolute() and not _has_path_separator(value):
        normalized = value.casefold()
        matches = [
            executable
            for executable in allowed_system_executables
            if normalized in {executable.name.casefold(), executable.stem.casefold()}
        ]
        if len(matches) != 1:
            raise DesktopTargetValidationError("Desktop executable is not on the fixed system allowlist.")
        return matches[0]

    executable = _resolve_existing(requested, working_directory)
    if not executable.is_file():
        raise DesktopTargetValidationError("Desktop executable is not a file.")
    if executable.is_relative_to(root) or executable in allowed_system_executables:
        return executable
    raise DesktopTargetValidationError("Desktop executable is outside the target root and allowlist.")


def _resolve_existing(path: Path, base: Path) -> Path:
    candidate = path if path.is_absolute() else base / path
    try:
        return candidate.resolve(strict=True)
    except OSError as exc:
        raise DesktopTargetValidationError("A registered desktop path does not exist.") from exc


def _require_inside(path: Path, root: Path, label: str) -> None:
    if not path.is_relative_to(root):
        raise DesktopTargetValidationError(f"Desktop {label} escapes the target root.")


def _looks_like_path(argument: str, working_directory: Path) -> bool:
    return (
        _has_path_separator(argument)
        or Path(argument).is_absolute()
        or (working_directory / argument).exists()
    )


def _has_path_separator(value: str) -> bool:
    return "/" in value or "\\" in value


def _minimal_environment(run_id: str) -> dict[str, str]:
    allowed = (
        "APPDATA",
        "HOME",
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
    environment = {name: os.environ[name] for name in allowed if name in os.environ}
    environment.update(
        {
            "CI": "1",
            "EAGLEEYE_CAPTURE_VIDEO": "1",
            "EAGLEEYE_DESKTOP_RUN_ID": run_id,
            "NO_COLOR": "1",
        }
    )
    return environment


def _terminate_process_tree(process: subprocess.Popen, run_id: str) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        system_root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
        taskkill = system_root / "System32" / "taskkill.exe"
        if taskkill.is_file():
            try:
                subprocess.run(  # noqa: S603 -- executable and argv are fixed; PID is from Popen
                    [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                    env=_minimal_environment(run_id),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
    if process.poll() is None:
        process.kill()


def _read_capped(stream, limit: int) -> str:
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    marker = b"\n[TRUNCATED]\n"
    if size <= limit:
        stream.seek(0)
        payload = stream.read(limit)
    else:
        available = max(0, limit - len(marker))
        head_size = available // 2
        tail_size = available - head_size
        stream.seek(0)
        head = stream.read(head_size)
        stream.seek(-tail_size, os.SEEK_END)
        tail = stream.read(tail_size)
        payload = head + marker + tail
    return payload.decode("utf-8", errors="replace")


def _redact_output(value: str) -> str:
    redacted = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)
    redacted = _BEARER.sub("Bearer [REDACTED]", redacted)
    redacted = _OPENAI_KEY.sub("[REDACTED]", redacted)
    redacted = _JWT.sub("[REDACTED]", redacted)
    redacted = _GITHUB_TOKEN.sub("[REDACTED]", redacted)
    redacted = _AWS_ACCESS_KEY.sub("[REDACTED]", redacted)
    return _URL_SECRET.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)


def _parse_terminal_payload(stdout: str) -> DesktopCommandPayload:
    stripped = stdout.rstrip()
    decoder = json.JSONDecoder()
    for offset in range(len(stripped) - 1, -1, -1):
        if stripped[offset] != "{":
            continue
        try:
            value, end = decoder.raw_decode(stripped[offset:])
        except json.JSONDecodeError:
            continue
        if stripped[offset + end :].strip() or not isinstance(value, dict):
            continue
        return DesktopCommandPayload.model_validate(value)
    raise ValueError("No terminal JSON object was found.")


def _import_artifacts(
    payload: DesktopCommandPayload,
    target: _ResolvedTarget,
    *,
    run_id: str,
    artifacts_root: Path,
) -> list[EvidenceArtifact]:
    if len(payload.artifacts) > target.config.max_artifacts:
        raise ValueError("Desktop command returned too many artifacts.")
    destination_root = artifacts_root.resolve() / safe_id(run_id) / "desktop"
    destination_root.mkdir(parents=True, exist_ok=True)
    _require_inside(destination_root.resolve(strict=True), artifacts_root.resolve(), "artifact destination")

    evidence: list[EvidenceArtifact] = []
    total_size = 0
    for index, declaration in enumerate(payload.artifacts, start=1):
        source = _resolve_existing(Path(declaration.path), target.working_directory)
        _require_inside(source, target.root, "artifact source")
        if not source.is_file():
            raise ValueError("Desktop artifact is not a regular file.")
        mime_type = _KIND_MIME_BY_SUFFIX.get((declaration.kind, source.suffix.casefold()))
        if mime_type is None:
            raise ValueError("Desktop artifact kind and extension are not allowlisted.")
        total_size += source.stat().st_size
        if total_size > target.config.max_artifact_bytes:
            raise ValueError("Desktop artifacts exceed the configured byte limit.")

        destination = destination_root / f"artifact-{index:02d}{source.suffix.casefold()}"
        if destination.is_symlink():
            raise ValueError("Desktop artifact destination must not be a symbolic link.")
        shutil.copy2(source, destination)
        evidence.append(
            evidence_from_file(
                destination,
                kind=declaration.kind,
                mime_type=mime_type,
                capture_source=f"desktop:{target.root.name}",
                artifact_root=artifacts_root,
            )
        )
    return evidence


def _failed_result(
    request: DesktopRunRequest,
    duration_ms: int,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    error: str,
    *,
    evidence: list[EvidenceArtifact] | None = None,
    summary: str | None = None,
    timed_out: bool = False,
) -> DesktopRunResult:
    return DesktopRunResult(
        target_id=request.target_id,
        run_id=request.run_id,
        status="failed",
        evidence=evidence or [],
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
        summary=summary,
        error=error,
        timed_out=timed_out,
    )
