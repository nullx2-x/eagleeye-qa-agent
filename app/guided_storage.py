from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .guided_models import GuidedObservation, GuidedScenarioDefinition, GuidedSession

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "guided" / "guided-qa.sqlite3"
GUIDED_RUNS = ROOT / "artifacts" / "guided-runs"
GUIDED_ASSETS = ROOT / "data" / "guided" / "assets"


class RevisionConflict(RuntimeError):
    pass


class ScenarioInUse(RuntimeError):
    pass


def _connect() -> sqlite3.Connection:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def init_db() -> None:
    with _connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS guided_scenarios (
                id TEXT PRIMARY KEY,
                body_json TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS guided_sessions (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                status TEXT NOT NULL,
                revision INTEGER NOT NULL,
                body_json TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES guided_scenarios(id)
            );
            CREATE INDEX IF NOT EXISTS idx_guided_sessions_scenario
                ON guided_sessions(scenario_id, updated_at_ms DESC);
            CREATE TABLE IF NOT EXISTS guided_observations (
                session_id TEXT NOT NULL,
                observation_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                body_json TEXT NOT NULL,
                PRIMARY KEY (session_id, observation_id),
                FOREIGN KEY (session_id) REFERENCES guided_sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_guided_observations_time
                ON guided_observations(session_id, timestamp_ms);
            CREATE TABLE IF NOT EXISTS guided_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                body_json TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES guided_sessions(id)
            );
            CREATE TABLE IF NOT EXISTS guided_attestations (
                session_id TEXT PRIMARY KEY,
                token_sha256 TEXT NOT NULL,
                issued_at_ms INTEGER NOT NULL,
                FOREIGN KEY (session_id) REFERENCES guided_sessions(id)
            );
            """
        )


def save_scenario(scenario: GuidedScenarioDefinition, now_ms: int) -> GuidedScenarioDefinition:
    init_db()
    body = scenario.model_dump_json()
    with _connect() as db:
        existing = db.execute(
            "SELECT body_json FROM guided_scenarios WHERE id = ?", (scenario.id,)
        ).fetchone()
        if existing is not None:
            current = GuidedScenarioDefinition.model_validate_json(existing["body_json"])
            if current.model_dump(mode="json") == scenario.model_dump(mode="json"):
                return current
            references = db.execute(
                "SELECT COUNT(*) AS count FROM guided_sessions WHERE scenario_id = ?",
                (scenario.id,),
            ).fetchone()["count"]
            if references:
                raise ScenarioInUse(
                    "A scenario referenced by a session is immutable; register a new id or version"
                )
        db.execute(
            """
            INSERT INTO guided_scenarios(id, body_json, created_at_ms, updated_at_ms)
            VALUES(?, ?, COALESCE((SELECT created_at_ms FROM guided_scenarios WHERE id = ?), ?), ?)
            ON CONFLICT(id) DO UPDATE SET
                body_json = excluded.body_json,
                updated_at_ms = excluded.updated_at_ms
            """,
            (scenario.id, body, scenario.id, now_ms, now_ms),
        )
    return scenario


def load_scenario(scenario_id: str) -> GuidedScenarioDefinition:
    init_db()
    with _connect() as db:
        row = db.execute("SELECT body_json FROM guided_scenarios WHERE id = ?", (scenario_id,)).fetchone()
    if row is None:
        raise FileNotFoundError(scenario_id)
    return GuidedScenarioDefinition.model_validate_json(row["body_json"])


def list_scenarios() -> list[GuidedScenarioDefinition]:
    init_db()
    with _connect() as db:
        rows = db.execute("SELECT body_json FROM guided_scenarios ORDER BY id").fetchall()
    return [GuidedScenarioDefinition.model_validate_json(row["body_json"]) for row in rows]


def create_session(session: GuidedSession) -> GuidedSession:
    init_db()
    with _connect() as db:
        db.execute(
            """
            INSERT INTO guided_sessions(
                id, scenario_id, status, revision, body_json, created_at_ms, updated_at_ms
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.scenarioId,
                session.status,
                session.revision,
                session.model_dump_json(),
                session.createdAtMs,
                session.updatedAtMs,
            ),
        )
    return session


def save_session(session: GuidedSession) -> GuidedSession:
    init_db()
    previous_revision = session.revision
    next_revision = previous_revision + 1
    updated = session.model_copy(update={"revision": next_revision})
    with _connect() as db:
        cursor = db.execute(
            """
            UPDATE guided_sessions
            SET status = ?, revision = ?, body_json = ?, updated_at_ms = ?
            WHERE id = ? AND revision = ?
            """,
            (
                updated.status,
                next_revision,
                updated.model_dump_json(),
                updated.updatedAtMs,
                updated.id,
                previous_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise RevisionConflict(updated.id)
    return updated


def load_session(session_id: str) -> GuidedSession:
    init_db()
    with _connect() as db:
        row = db.execute("SELECT body_json FROM guided_sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise FileNotFoundError(session_id)
    return GuidedSession.model_validate_json(row["body_json"])


def list_sessions(scenario_id: str | None = None, limit: int = 100) -> list[GuidedSession]:
    init_db()
    limit = max(1, min(limit, 500))
    query = "SELECT body_json FROM guided_sessions"
    params: tuple[Any, ...] = ()
    if scenario_id:
        query += " WHERE scenario_id = ?"
        params = (scenario_id,)
    query += " ORDER BY updated_at_ms DESC LIMIT ?"
    params += (limit,)
    with _connect() as db:
        rows = db.execute(query, params).fetchall()
    return [GuidedSession.model_validate_json(row["body_json"]) for row in rows]


def save_attestation_digest(session_id: str, token_sha256: str, issued_at_ms: int) -> None:
    init_db()
    with _connect() as db:
        db.execute(
            """
            INSERT INTO guided_attestations(session_id, token_sha256, issued_at_ms)
            VALUES(?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                token_sha256 = excluded.token_sha256,
                issued_at_ms = excluded.issued_at_ms
            """,
            (session_id, token_sha256, issued_at_ms),
        )


def load_attestation_digest(session_id: str) -> str | None:
    init_db()
    with _connect() as db:
        row = db.execute(
            "SELECT token_sha256 FROM guided_attestations WHERE session_id = ?", (session_id,)
        ).fetchone()
    return str(row["token_sha256"]) if row is not None else None


def delete_attestation_digest(session_id: str) -> None:
    init_db()
    with _connect() as db:
        db.execute("DELETE FROM guided_attestations WHERE session_id = ?", (session_id,))


def append_observation(session_id: str, observation: GuidedObservation) -> bool:
    init_db()
    with _connect() as db:
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO guided_observations
                (session_id, observation_id, sequence, timestamp_ms, body_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                session_id,
                observation.id,
                observation.sequence,
                observation.timestampMs,
                observation.model_dump_json(),
            ),
        )
    return cursor.rowcount == 1


def observations_for_session(session_id: str) -> list[GuidedObservation]:
    init_db()
    with _connect() as db:
        rows = db.execute(
            "SELECT body_json FROM guided_observations WHERE session_id = ? ORDER BY sequence, timestamp_ms",
            (session_id,),
        ).fetchall()
    return [GuidedObservation.model_validate_json(row["body_json"]) for row in rows]


def append_audit(session_id: str, timestamp_ms: int, event_type: str, body: dict[str, Any]) -> None:
    init_db()
    with _connect() as db:
        db.execute(
            "INSERT INTO guided_audit(session_id, timestamp_ms, event_type, body_json) VALUES(?, ?, ?, ?)",
            (
                session_id,
                timestamp_ms,
                event_type,
                json.dumps(body, ensure_ascii=False, separators=(",", ":")),
            ),
        )


def audits_for_session(session_id: str) -> list[dict[str, Any]]:
    init_db()
    with _connect() as db:
        rows = db.execute(
            """
            SELECT timestamp_ms, event_type, body_json
            FROM guided_audit WHERE session_id = ? ORDER BY id
            """,
            (session_id,),
        ).fetchall()
    return [
        {
            "timestampMs": row["timestamp_ms"],
            "eventType": row["event_type"],
            "body": json.loads(row["body_json"]),
        }
        for row in rows
    ]


def _write(path: Path, content: str) -> tuple[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return str(path), digest


def write_step_evidence(session_id: str, step_id: str, attempt: int, body: dict[str, Any]) -> tuple[str, str]:
    content = json.dumps(body, ensure_ascii=False, indent=2)
    return _write(GUIDED_RUNS / session_id / "steps" / f"{step_id}-attempt-{attempt}.json", content)


def write_report(session_id: str, content: str) -> tuple[str, str]:
    return _write(GUIDED_RUNS / session_id / "report.md", content)


def write_session_evidence(session_id: str, body: dict[str, Any]) -> tuple[str, str]:
    content = json.dumps(body, ensure_ascii=False, indent=2)
    return _write(GUIDED_RUNS / session_id / "evidence.json", content)
