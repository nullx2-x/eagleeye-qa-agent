from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from scripts.operational_benchmark import percentile
from scripts.operational_smoke import REQUIRED_MCP_TOOLS, passed
from scripts.runtime_backup import create_backup, restore_backup, verify_backup


def test_smoke_requires_every_check_to_pass() -> None:
    assert passed({"api": {"ok": True}, "mcp": {"ok": True}})
    assert not passed({"api": {"ok": True}, "mcp": {"ok": False}})
    assert "eagleeye_status" in REQUIRED_MCP_TOOLS
    assert "guided_control_session" in REQUIRED_MCP_TOOLS
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_runtime_backup_and_restore_drill(tmp_path: Path) -> None:
    root = tmp_path / "project"
    session = root / "data" / "sessions" / "sample.json"
    session.parent.mkdir(parents=True)
    session.write_text('{"status":"passed"}', encoding="utf-8")
    database = root / "data" / "guided" / "guided.sqlite3"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO evidence(value) VALUES ('verified')")
    secret = root / "data" / "sessions" / "access-token.txt"
    secret.write_text("must-not-back-up", encoding="utf-8")

    archive = tmp_path / "backup.zip"
    manifest = create_backup(root, archive)
    assert manifest["entryCount"] == 2
    assert verify_backup(archive)["status"] == "PASS"

    restored = tmp_path / "restored"
    restore_backup(archive, restored)
    assert (restored / "data" / "sessions" / "sample.json").read_text(encoding="utf-8")
    assert not (restored / "data" / "sessions" / "access-token.txt").exists()
    with sqlite3.connect(restored / "data" / "guided" / "guided.sqlite3") as db:
        assert db.execute("SELECT value FROM evidence").fetchone()[0] == "verified"


def test_runtime_backup_detects_manifest_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "project"
    source = root / "output" / "result.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"ok": True}), encoding="utf-8")
    archive = tmp_path / "backup.zip"
    create_backup(root, archive)
    with zipfile.ZipFile(archive, "a") as bundle:
        bundle.writestr("unexpected.txt", "tampered")
    with pytest.raises(ValueError, match="entries do not match"):
        verify_backup(archive)
