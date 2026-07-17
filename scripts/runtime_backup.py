from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

ALLOWED_ROOTS = (
    "data/sessions",
    "data/guided",
    "artifacts/runs",
    "artifacts/guided-runs",
    "profiles",
    "output",
)
DENIED_NAMES = {".env", ".env.router", ".env.private", "auth.json"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_allowed(relative: Path) -> bool:
    lowered = relative.name.lower()
    if lowered in DENIED_NAMES or any(word in lowered for word in ("token", "secret", "credential")):
        return False
    return not relative.name.endswith(("-wal", "-shm", ".tmp"))


def source_files(root: Path) -> Iterable[Path]:
    for allowed in ALLOWED_ROOTS:
        directory = root / allowed
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file() and is_allowed(path.relative_to(root)):
                yield path


def sqlite_snapshot(path: Path) -> bytes:
    with tempfile.TemporaryDirectory() as temp_dir:
        snapshot = Path(temp_dir) / path.name
        source = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        return snapshot.read_bytes()


def file_bytes(path: Path) -> bytes:
    if path.suffix == ".sqlite3":
        return sqlite_snapshot(path)
    return path.read_bytes()


def create_backup(root: Path, output: Path) -> dict:
    root = root.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files(root):
            relative = path.relative_to(root).as_posix()
            data = file_bytes(path)
            archive.writestr(relative, data)
            entries.append({"path": relative, "size": len(data), "sha256": sha256(data)})
        manifest = {
            "schemaVersion": 1,
            "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": str(root),
            "entryCount": len(entries),
            "entries": entries,
        }
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest | {"archive": str(output.resolve()), "archiveSha256": sha256(output.read_bytes())}


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and name != "manifest.json"


def verify_backup(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json"))
        expected = {entry["path"]: entry for entry in manifest["entries"]}
        actual_names = {name for name in archive.namelist() if name != "manifest.json"}
        if actual_names != set(expected):
            raise ValueError("archive entries do not match manifest")
        for name, entry in expected.items():
            if not safe_member(name):
                raise ValueError(f"unsafe archive path: {name}")
            data = archive.read(name)
            if len(data) != entry["size"] or sha256(data) != entry["sha256"]:
                raise ValueError(f"checksum mismatch: {name}")
    return {
        "status": "PASS",
        "archive": str(archive_path.resolve()),
        "archiveSha256": sha256(archive_path.read_bytes()),
        "entryCount": len(expected),
    }


def restore_backup(archive_path: Path, target: Path) -> dict:
    verification = verify_backup(archive_path)
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        for name in archive.namelist():
            if name == "manifest.json":
                continue
            destination = (target / Path(PurePosixPath(name))).resolve()
            if target not in destination.parents:
                raise ValueError(f"restore path escaped target: {name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
    return verification | {"restoredTo": str(target)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup and verify EagleEye runtime evidence")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    restore = sub.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--target", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "backup":
            result = create_backup(args.root, args.output)
        elif args.command == "verify":
            result = verify_backup(args.archive)
        else:
            result = restore_backup(args.archive, args.target)
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
