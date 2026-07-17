from __future__ import annotations

import argparse
import compileall
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def run(root: Path, ref: str, target: Path) -> dict:
    root = root.resolve()
    target = target.resolve()
    archive = target.parent / f"{ref.replace('/', '-')}.zip"
    target.mkdir(parents=True, exist_ok=True)
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git executable was not found")
    completed = subprocess.run(  # noqa: S603 - fixed git executable and validated local arguments
        [git, "archive", "--format=zip", f"--output={archive}", ref],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git archive failed: {ref}")
    with zipfile.ZipFile(archive, "r") as bundle:
        if not all(safe_name(name) for name in bundle.namelist()):
            raise RuntimeError("rollback archive contains an unsafe path")
        bundle.extractall(target)
    version = (target / "VERSION").read_text(encoding="utf-8").strip()
    compiled = compileall.compile_dir(target / "app", quiet=1, force=True)
    return {
        "schemaVersion": 1,
        "finishedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "PASS" if compiled else "FAIL",
        "ref": ref,
        "restoredVersion": version,
        "target": str(target),
        "pythonCompile": compiled,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a tagged EagleEye release into a sandbox")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ref", default="v0.5.0")
    parser.add_argument("--target", type=Path, default=Path(".runtime/rollback-drill/v0.5.0"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/rollback-drill/latest.json"))
    args = parser.parse_args()
    try:
        report = run(args.root, args.ref, args.target)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        report = {"status": "FAIL", "ref": args.ref, "error": str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
