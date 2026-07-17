from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def run_step(name: str, command: list[str], root: Path) -> dict:
    started = now()
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)  # noqa: S603
    output = (completed.stdout + completed.stderr).strip()
    return {
        "name": name,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "exitCode": completed.returncode,
        "startedAt": started,
        "finishedAt": now(),
        "command": command,
        "outputTail": output[-4000:],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the EagleEye deterministic quality gate")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    python = root / ".venv" / "Scripts" / "python.exe"
    ruff = root / ".venv" / "Scripts" / "ruff.exe"
    if not python.exists():
        python = Path(sys.executable)
    steps = [
        run_step("pytest", [str(python), "-m", "pytest", "-q"], root),
        run_step("ruff-check", [str(ruff), "check", "."], root),
        run_step("ruff-format", [str(ruff), "format", "--check", "."], root),
    ]
    if not args.skip_live:
        smoke_output = root / ".runtime" / "operational-smoke" / "latest.json"
        steps.append(
            run_step(
                "operational-smoke",
                [str(python), "scripts/operational_smoke.py", "--output", str(smoke_output)],
                root,
            )
        )
        steps.append(
            run_step(
                "browser-matrix",
                [str(python), "scripts/browser_matrix.py"],
                root,
            )
        )
        steps.append(
            run_step(
                "operational-benchmark",
                [str(python), "scripts/operational_benchmark.py"],
                root,
            )
        )
        steps.append(
            run_step(
                "ai-safety-evals",
                [str(python), "scripts/run_ai_safety_evals.py"],
                root,
            )
        )
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive = root / ".runtime" / "backups" / f"eagleeye-runtime-{stamp}.zip"
        restore = root / ".runtime" / "restore-drill" / stamp
        steps.append(
            run_step(
                "backup-create",
                [str(python), "scripts/runtime_backup.py", "backup", "--output", str(archive)],
                root,
            )
        )
        if steps[-1]["status"] == "PASS":
            steps.append(
                run_step(
                    "backup-restore-drill",
                    [
                        str(python),
                        "scripts/runtime_backup.py",
                        "restore",
                        str(archive),
                        "--target",
                        str(restore),
                    ],
                    root,
                )
            )
    status = "PASS" if all(step["status"] == "PASS" for step in steps) else "FAIL"
    report = {"schemaVersion": 1, "status": status, "finishedAt": now(), "steps": steps}
    output = args.output or root / ".runtime" / "quality-gate" / "latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
