from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .project_qa_models import (
    ProjectDiscoveryResponse,
    ProjectRunReport,
    ProjectRunRequest,
    ProjectSuiteDefinition,
    ProjectSuiteResult,
)
from .quality import evaluate_quality_gate
from .strategy_models import QualityGateRequest

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "artifacts" / "project-qa"
MANIFEST = Path(".eagleeye") / "qa.json"
MAX_LOG_BYTES = 2 * 1024 * 1024
_ALLOWED_EXECUTABLES = {
    "bun",
    "bun.exe",
    "cargo",
    "dotnet",
    "go",
    "gradlew",
    "gradlew.bat",
    "mvn",
    "mvnw",
    "mvnw.cmd",
    "npm",
    "npm.cmd",
    "pnpm",
    "pnpm.cmd",
    "python",
    "python.exe",
    "python3",
    "pytest",
    "ruff",
    "uv",
    "yarn",
    "yarn.cmd",
}
_ENV_ALLOWLIST = {
    "APPDATA",
    "CI",
    "COMSPEC",
    "FORCE_COLOR",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LC_ALL",
    "LOCALAPPDATA",
    "NO_COLOR",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "UV_PROJECT_ENVIRONMENT",
    "VIRTUAL_ENV",
    "WINDIR",
}
_SECRET = re.compile(
    rb"(?i)(bearer\s+|api[_-]?key\s*[:=]\s*|access[_-]?token\s*[:=]\s*|"
    rb"refresh[_-]?token\s*[:=]\s*|password\s*[:=]\s*)[^\s,;&]+"
)


def discover_project(project_root: str) -> ProjectDiscoveryResponse:
    root = _authorized_root(project_root)
    suites: list[ProjectSuiteDefinition] = []
    ecosystems: list[str] = []
    warnings: list[str] = []

    package_json = root / "package.json"
    if package_json.is_file():
        ecosystems.append("node")
        suites.extend(_node_suites(root, package_json, warnings))
    if (root / "pyproject.toml").is_file() or (root / "pytest.ini").is_file():
        ecosystems.append("python")
        suites.extend(_python_suites(root))
    if (root / "go.mod").is_file():
        ecosystems.append("go")
        suites.extend(
            [
                _suite("go-test", "Go tests", "unit", ["go", "test", "./..."]),
                _suite("go-vet", "Go vet", "lint", ["go", "vet", "./..."]),
            ]
        )
    if (root / "Cargo.toml").is_file():
        ecosystems.append("rust")
        suites.extend(
            [
                _suite("cargo-test", "Cargo tests", "unit", ["cargo", "test", "--all-targets"]),
                _suite(
                    "cargo-clippy",
                    "Cargo clippy",
                    "lint",
                    ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"],
                ),
            ]
        )
    if list(root.glob("*.sln")) or list(root.glob("*.csproj")):
        ecosystems.append("dotnet")
        suites.append(_suite("dotnet-test", ".NET tests", "unit", ["dotnet", "test"]))
    if (root / "gradlew.bat").is_file() or (root / "gradlew").is_file():
        ecosystems.append("gradle")
        executable = "gradlew.bat" if os.name == "nt" else "gradlew"
        suites.append(_suite("gradle-test", "Gradle tests", "unit", [executable, "test"]))
    elif (root / "pom.xml").is_file():
        ecosystems.append("maven")
        executable = "mvnw.cmd" if (root / "mvnw.cmd").is_file() else "mvn"
        suites.append(_suite("maven-test", "Maven tests", "unit", [executable, "test"]))

    manifest = root / MANIFEST
    if manifest.is_file():
        suites.extend(_manifest_suites(manifest))
    suites = _deduplicate(suites)
    if not suites:
        warnings.append("実行可能なテスト、lint、型検査、buildを検出できませんでした。")
    return ProjectDiscoveryResponse(
        projectId=_project_id(root),
        projectRoot=str(root),
        rootFingerprint=hashlib.sha256(str(root).casefold().encode()).hexdigest(),
        ecosystems=sorted(set(ecosystems)),
        suites=suites,
        warnings=warnings,
    )


def run_project(request: ProjectRunRequest) -> ProjectRunReport:
    discovery = discover_project(request.projectRoot)
    selected = discovery.suites
    if request.suiteIds:
        wanted = set(request.suiteIds)
        selected = [suite for suite in selected if suite.id in wanted]
        missing = sorted(wanted - {suite.id for suite in selected})
        if missing:
            raise ValueError(f"Unknown suiteIds: {', '.join(missing)}")
    if not selected:
        raise ValueError("No executable QA suites were selected.")

    run_id = uuid4().hex
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started = _now()
    results: list[ProjectSuiteResult] = []
    for suite in selected:
        result = _run_suite(Path(discovery.projectRoot), run_dir, suite, request.timeoutSeconds)
        results.append(result)
        if request.failFast and result.status != "PASSED":
            break

    gate = evaluate_quality_gate(
        QualityGateRequest.model_validate(
            {
                "profileId": f"project-{discovery.projectId}",
                "mode": request.mode,
                "results": [
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
                    for item in results
                ],
                "requiredTestTypes": sorted({suite.testType for suite in selected if suite.required}),
            }
        )
    )
    status = "PASS" if gate.decision in {"PASS", "PASS_WITH_WARNING"} else "BLOCKED"
    if gate.decision == "FAIL":
        status = "FAIL"
    report_json = run_dir / "report.json"
    report_markdown = run_dir / "report.md"
    report = ProjectRunReport(
        runId=run_id,
        projectId=discovery.projectId,
        projectRoot=discovery.projectRoot,
        startedAt=started,
        completedAt=_now(),
        status=status,
        results=results,
        qualityGate=gate,
        reportJson=str(report_json),
        reportMarkdown=str(report_markdown),
    )
    _atomic_write(report_json, report.model_dump_json(indent=2))
    _atomic_write(report_markdown, _markdown(report))
    return report


def load_project_run(run_id: str) -> ProjectRunReport:
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("Invalid run id")
    path = RUNS / run_id / "report.json"
    if not path.is_file():
        raise FileNotFoundError(run_id)
    return ProjectRunReport.model_validate_json(path.read_text(encoding="utf-8"))


def _node_suites(root: Path, package_json: Path, warnings: list[str]) -> list[ProjectSuiteDefinition]:
    try:
        document = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"package.jsonを解析できません: {exc.__class__.__name__}")
        return []
    scripts = document.get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    runner = _node_runner(root)
    suites: list[ProjectSuiteDefinition] = []
    accepted = {
        "lint": "lint",
        "typecheck": "typecheck",
        "test": "unit",
        "build": "build",
    }
    ordered_scripts = [script for script in accepted if script in scripts]
    ordered_scripts.extend(
        sorted(
            script
            for script, command in scripts.items()
            if isinstance(script, str)
            and isinstance(command, str)
            and script.startswith("test:")
            and not _interactive_node_test(script)
        )
    )
    known_test_types = {
        "test:unit": "unit",
        "test:integration": "integration",
        "test:e2e": "e2e",
        "test:security": "security",
    }
    for script in ordered_scripts:
        test_type = accepted.get(script, known_test_types.get(script, "test"))
        if script in scripts:
            suites.append(
                _suite(
                    f"node-{script.replace(':', '-')}",
                    f"Node {script}",
                    test_type,
                    [runner, "run", script],
                )
            )
    return suites


def _interactive_node_test(script: str) -> bool:
    interactive_segments = {"dev", "interactive", "ui", "watch"}
    return any(segment.casefold() in interactive_segments for segment in script.split(":")[1:])


def _python_suites(root: Path) -> list[ProjectSuiteDefinition]:
    prefix = ["uv", "run"] if (root / "uv.lock").is_file() else ["python", "-m"]
    return [
        _suite("python-pytest", "Python tests", "unit", [*prefix, "pytest", "-q"]),
        _suite("python-ruff-check", "Ruff lint", "lint", [*prefix, "ruff", "check", "."]),
        _suite(
            "python-ruff-format",
            "Ruff format check",
            "format",
            [*prefix, "ruff", "format", "--check", "."],
        ),
    ]


def _node_runner(root: Path) -> str:
    if (root / "pnpm-lock.yaml").is_file():
        runner = "pnpm"
    elif (root / "yarn.lock").is_file():
        runner = "yarn"
    elif (root / "bun.lock").is_file() or (root / "bun.lockb").is_file():
        runner = "bun"
    else:
        runner = "npm"
    if os.name == "nt":
        return f"{runner}.exe" if runner == "bun" else f"{runner}.cmd"
    return runner


def _manifest_suites(path: Path) -> list[ProjectSuiteDefinition]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid .eagleeye/qa.json manifest") from exc
    values = document.get("suites", []) if isinstance(document, dict) else []
    if not isinstance(values, list) or len(values) > 200:
        raise ValueError("Manifest suites must be an array with at most 200 entries")
    suites: list[ProjectSuiteDefinition] = []
    for raw in values:
        if not isinstance(raw, dict):
            raise ValueError("Every manifest suite must be an object")
        suite = ProjectSuiteDefinition.model_validate({**raw, "source": "manifest"})
        _validate_command(suite.command)
        suites.append(suite)
    return suites


def _suite(identifier: str, name: str, test_type: str, command: list[str]) -> ProjectSuiteDefinition:
    return ProjectSuiteDefinition(id=identifier, name=name, testType=test_type, command=command)


def _deduplicate(suites: list[ProjectSuiteDefinition]) -> list[ProjectSuiteDefinition]:
    unique: dict[str, ProjectSuiteDefinition] = {}
    for suite in suites:
        _validate_command(suite.command)
        if suite.id in unique:
            raise ValueError(f"Duplicate suite id: {suite.id}")
        unique[suite.id] = suite
    return list(unique.values())


def _validate_command(command: list[str]) -> None:
    executable = Path(command[0]).name.casefold()
    if executable not in _ALLOWED_EXECUTABLES:
        raise ValueError(f"Executable is not allowed: {executable}")
    if any("\x00" in value or "\n" in value or "\r" in value for value in command):
        raise ValueError("Command arguments contain control characters")


def _run_suite(
    project_root: Path,
    run_dir: Path,
    suite: ProjectSuiteDefinition,
    timeout_seconds: int,
) -> ProjectSuiteResult:
    _validate_command(suite.command)
    started = time.monotonic()
    output = bytearray()
    truncated = False
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    suite_tmp = _suite_temp_dir(run_dir.name, suite.id)
    suite_tmp.mkdir(parents=True, exist_ok=True)
    environment = _minimal_env()
    environment["TEMP"] = str(suite_tmp)
    environment["TMP"] = str(suite_tmp)
    environment["TMPDIR"] = str(suite_tmp)
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed allowlist, shell disabled, approved root
            suite.command,
            cwd=project_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            creationflags=flags,
            start_new_session=os.name != "nt",
        )
    except OSError as exc:
        clean = (f"[EagleEye: suite executable could not be started: {exc.__class__.__name__}]\n").encode()
        log_path = run_dir / f"{suite.id}.log"
        log_path.write_bytes(clean)
        shutil.rmtree(suite_tmp, ignore_errors=True)
        return ProjectSuiteResult(
            id=suite.id,
            name=suite.name,
            testType=suite.testType,
            status="INFRA_ERROR",
            exitCode=None,
            durationMs=round((time.monotonic() - started) * 1_000),
            command=suite.command,
            errorMessage=f"Unable to start suite executable: {exc.__class__.__name__}.",
            evidencePath=str(log_path),
            evidenceSha256=hashlib.sha256(clean).hexdigest(),
            evidenceBytes=len(clean),
        )

    def consume() -> None:
        nonlocal truncated
        assert process.stdout is not None
        while chunk := process.stdout.read(64 * 1024):
            remaining = MAX_LOG_BYTES - len(output)
            if remaining > 0:
                output.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True

    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    timed_out = False
    try:
        exit_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(process)
        exit_code = None
    reader.join(timeout=5)
    duration_ms = round((time.monotonic() - started) * 1_000)
    clean = _SECRET.sub(rb"\1[REDACTED]", bytes(output))
    if truncated:
        clean += b"\n[EagleEye: output truncated at 2 MiB]\n"
    if timed_out:
        clean += f"\n[EagleEye: suite timed out after {timeout_seconds}s]\n".encode()
    log_path = run_dir / f"{suite.id}.log"
    log_path.write_bytes(clean)
    digest = hashlib.sha256(clean).hexdigest()
    status = "INFRA_ERROR" if timed_out else ("PASSED" if exit_code == 0 else "FAILED")
    error = None
    if timed_out:
        error = f"Suite exceeded the {timeout_seconds}s timeout."
    elif exit_code != 0:
        error = f"Suite exited with code {exit_code}."
    shutil.rmtree(suite_tmp, ignore_errors=True)
    return ProjectSuiteResult(
        id=suite.id,
        name=suite.name,
        testType=suite.testType,
        status=status,
        exitCode=exit_code,
        durationMs=duration_ms,
        command=suite.command,
        errorMessage=error,
        evidencePath=str(log_path),
        evidenceSha256=digest,
        evidenceBytes=len(clean),
    )


def _kill_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        taskkill = str(Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "taskkill.exe")
        subprocess.run(  # noqa: S603 - fixed Windows process-tree utility
            [taskkill, "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
    else:
        os.killpg(process.pid, signal.SIGKILL)


def _minimal_env() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key.upper() in _ENV_ALLOWLIST}
    environment["CI"] = "1"
    environment["NO_COLOR"] = "1"
    return environment


def _suite_temp_dir(run_id: str, suite_id: str) -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "EagleEye" / "q"
        suite_key = hashlib.sha256(suite_id.encode()).hexdigest()[:12]
        return base / run_id[:12] / suite_key
    return Path(tempfile.gettempdir()) / "eagleeye-project-qa" / run_id / suite_id


def _authorized_root(value: str) -> Path:
    allowed = _allowed_roots()
    candidate = _normalized_absolute_path(value)
    for declared_root, resolved_root in allowed:
        resolved_text = os.path.normcase(os.path.normpath(str(resolved_root)))
        for normalized_root in (declared_root, resolved_text):
            if candidate == normalized_root:
                return resolved_root
            root_prefix = (
                normalized_root if normalized_root.endswith(os.sep) else f"{normalized_root}{os.sep}"
            )
            if candidate.startswith(root_prefix):
                requested = Path(candidate).resolve(strict=True)
                if not any(
                    requested == allowed_root or requested.is_relative_to(allowed_root)
                    for _, allowed_root in allowed
                ):
                    raise PermissionError("Project root is outside EAGLEEYE_PROJECT_ROOTS")
                if not requested.is_dir():
                    raise ValueError("Project root must be a directory")
                return requested
    raise PermissionError("Project root is outside EAGLEEYE_PROJECT_ROOTS")


def _normalized_absolute_path(value: str) -> str:
    if any(ord(character) < 32 for character in value):
        raise ValueError("Project root contains control characters")
    if not os.path.isabs(value):
        raise ValueError("Project root must be an absolute path")
    return os.path.normcase(os.path.normpath(value))


def _allowed_roots() -> list[tuple[str, Path]]:
    configured = os.getenv("EAGLEEYE_PROJECT_ROOTS", "").strip()
    values = configured.split(os.pathsep) if configured else [str(ROOT.parents[1])]
    roots: list[tuple[str, Path]] = []
    for value in values:
        if not value.strip():
            continue
        declared = Path(value).expanduser()
        if not declared.is_absolute():
            declared = Path(os.path.abspath(declared))
        declared_text = os.path.normcase(os.path.normpath(str(declared)))
        resolved = declared.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("EAGLEEYE_PROJECT_ROOTS entries must be directories")
        roots.append((declared_text, resolved))
    return roots


def _project_id(root: Path) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", root.name.casefold()).strip("-") or "project"
    digest = hashlib.sha256(str(root).casefold().encode()).hexdigest()[:10]
    return f"{slug[:60]}-{digest}"


def _markdown(report: ProjectRunReport) -> str:
    rows = "\n".join(
        f"| {item.name} | {item.testType} | {item.status} | {item.durationMs} | `{item.evidenceSha256}` |"
        for item in report.results
    )
    blockers = "\n".join(f"- {item}" for item in report.qualityGate.blockers) or "- None"
    return (
        f"# EagleEye Project QA — {report.projectId}\n\n"
        f"- Run: `{report.runId}`\n"
        f"- Status: **{report.status}**\n"
        f"- Gate: **{report.qualityGate.decision}**\n"
        f"- Started: {report.startedAt}\n"
        f"- Completed: {report.completedAt}\n\n"
        "| Suite | Type | Result | Duration ms | Evidence SHA-256 |\n"
        "|---|---|---:|---:|---|\n"
        f"{rows}\n\n## Blockers\n\n{blockers}\n"
    )


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat()
