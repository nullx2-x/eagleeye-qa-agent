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
    accepted = {"lint": "lint", "typecheck": "typecheck", "test": "unit", "build": "build"}
    ordered = [name for name in accepted if name in scripts]
    ordered.extend(
        sorted(
            name
            for name, command in scripts.items()
            if isinstance(name, str)
            and isinstance(command, str)
            and name.startswith("test:")
            and not _interactive_node_test(name)
        )
    )
    known = {
        "test:unit": "unit",
        "test:integration": "integration",
        "test:e2e": "e2e",
        "test:security": "security",
    }
    return [
        _suite(
            f"node-{name.replace(':', '-')}",
            f"Node {name}",
            accepted.get(name, known.get(name, "test")),
            [runner, "run", name],
        )
        for name in ordered
        if name in scripts
    ]


def _interactive_node_test(script: str) -> bool:
    interactive = {"dev", "interactive", "ui", "watch"}
    return any(segment.casefold() in interactive for segment in script.split(":")[1:])


def _python_suites(root: Path) -> list[ProjectSuiteDefinition]:
    prefix = ["uv", "run"] if (root / "uv.lock").is_file() else ["python", "-m"]
    return [
        _suite("python-pytest", "Python tests", "unit", [*prefix, "pytest", "-q"]),
        _suite("python-ruff-check", "Ruff lint", "lint", [*prefix, "ruff", "check", "."]),
        _suite(
            "python-ruff-format", "Ruff format check", "format", [*prefix, "ruff", "format", "--check", "."]
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
    suites = []
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
    suite_tmp = Path(tempfile.mkdtemp(prefix=f"ee-{_short_key(suite.id)}-"))
    env = {key: value for key, value in os.environ.items() if key.upper() in _ENV_ALLOWLIST}
    env.update(
        {
            "CI": "1",
            "NO_COLOR": "1",
            "TMP": str(suite_tmp),
            "TEMP": str(suite_tmp),
            "TMPDIR": str(suite_tmp),
        }
    )
    try:
        process = subprocess.Popen(
            suite.command,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            env=env,
            creationflags=flags,
        )
    except OSError as exc:
        payload = _redact_bytes(str(exc).encode())
        shutil.rmtree(suite_tmp, ignore_errors=True)
        return _write_suite_evidence(
            run_dir,
            suite,
            "INFRA_ERROR",
            None,
            int((time.monotonic() - started) * 1000),
            payload,
            f"Executable unavailable: {Path(suite.command[0]).name}",
        )

    assert process.stdout is not None
    lock = threading.Lock()

    def consume() -> None:
        nonlocal truncated
        while chunk := process.stdout.read(8192):
            clean = _redact_bytes(chunk)
            with lock:
                remaining = MAX_LOG_BYTES - len(output)
                if remaining <= 0:
                    truncated = True
                    continue
                output.extend(clean[:remaining])
                if len(clean) > remaining:
                    truncated = True

    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    error: str | None = None
    try:
        exit_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        exit_code = process.wait()
        error = f"Suite timed out after {timeout_seconds} seconds"
    finally:
        reader.join(timeout=5)
        shutil.rmtree(suite_tmp, ignore_errors=True)

    status = "PASSED" if exit_code == 0 and error is None else "FAILED"
    if truncated:
        output.extend(b"\n[EagleEye log truncated at 2 MiB]\n")
    return _write_suite_evidence(
        run_dir,
        suite,
        status,
        exit_code,
        int((time.monotonic() - started) * 1000),
        bytes(output),
        error,
    )


def _write_suite_evidence(
    run_dir: Path,
    suite: ProjectSuiteDefinition,
    status: str,
    exit_code: int | None,
    duration_ms: int,
    output: bytes,
    error: str | None,
) -> ProjectSuiteResult:
    path = run_dir / f"{_safe_id(suite.id)}.log"
    path.write_bytes(output)
    digest = hashlib.sha256(output).hexdigest()
    return ProjectSuiteResult(
        id=suite.id,
        name=suite.name,
        testType=suite.testType,
        status=status,
        exitCode=exit_code,
        durationMs=duration_ms,
        command=suite.command,
        errorMessage=error,
        evidencePath=str(path),
        evidenceSha256=digest,
        evidenceBytes=len(output),
    )


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            shell=False,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _authorized_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    allowed = _allowed_roots()
    if not allowed:
        raise PermissionError("EAGLEEYE_PROJECT_ROOTS must explicitly authorize project roots")
    if not any(root == parent or root.is_relative_to(parent) for parent in allowed):
        raise PermissionError("Project root is outside EAGLEEYE_PROJECT_ROOTS")
    return root


def _allowed_roots() -> list[Path]:
    raw = os.getenv("EAGLEEYE_PROJECT_ROOTS", "")
    return [Path(item).expanduser().resolve() for item in raw.split(os.pathsep) if item.strip()]


def _project_id(root: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", root.name).strip("-") or "project"
    return f"{slug[:60]}-{hashlib.sha256(str(root).casefold().encode()).hexdigest()[:12]}"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:120] or "suite"


def _short_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _redact_bytes(value: bytes) -> bytes:
    return _SECRET.sub(lambda match: match.group(1) + b"[redacted]", value)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content + ("\n" if not content.endswith("\n") else ""), encoding="utf-8")
    temporary.replace(path)


def _markdown(report: ProjectRunReport) -> str:
    lines = [
        f"# EagleEye Project QA — {report.projectId}",
        "",
        f"- Status: `{report.status}`",
        f"- Run: `{report.runId}`",
        f"- Project: `{report.projectRoot}`",
        f"- Gate: `{report.qualityGate.decision}`",
        "",
        "## Suites",
        "",
    ]
    for item in report.results:
        lines.append(
            f"- **{item.name}** — `{item.status}` — {item.durationMs} ms — `sha256:{item.evidenceSha256}`"
        )
    lines.extend(["", "Generated locally. Review before sharing; no upload occurs automatically.", ""])
    return "\n".join(lines)


def _now() -> str:
    return datetime.now(UTC).isoformat()
