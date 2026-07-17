import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from .models import EagleEyeBundle, EvidenceArtifact, RunResult

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = ROOT / "data" / "sessions"
GENERATED = ROOT / "tests" / "generated"
RUNS = ROOT / "artifacts" / "runs"


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", value)[:80]
    if not cleaned:
        raise ValueError("Invalid session id")
    return cleaned


def save_bundle(bundle: EagleEyeBundle) -> tuple[Path, Path, Path]:
    from .security import sanitize_privacy

    bundle = sanitize_privacy(bundle)
    session_id = safe_id(bundle.session.id)
    SESSIONS.mkdir(parents=True, exist_ok=True)
    GENERATED.mkdir(parents=True, exist_ok=True)
    bundle_path = SESSIONS / f"{session_id}.json"
    spec_path = GENERATED / f"{session_id}.spec.ts"
    yaml_path = GENERATED / f"{session_id}.yaml"
    _atomic_write(bundle_path, json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2))
    _atomic_write(spec_path, bundle.generated.playwright)
    _atomic_write(yaml_path, bundle.generated.yaml)
    return bundle_path, spec_path, yaml_path


def load_bundle(session_id: str) -> EagleEyeBundle:
    path = SESSIONS / f"{safe_id(session_id)}.json"
    if not path.exists():
        raise FileNotFoundError(session_id)
    return EagleEyeBundle.model_validate_json(path.read_text(encoding="utf-8"))


def save_run(result: RunResult) -> Path:
    run_dir = RUNS / safe_id(result.session_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "result.json"
    _atomic_write(path, result.model_dump_json(indent=2))
    return path


def load_run(session_id: str) -> RunResult:
    path = RUNS / safe_id(session_id) / "result.json"
    if not path.exists():
        raise FileNotFoundError(session_id)
    return RunResult.model_validate_json(path.read_text(encoding="utf-8"))


def evidence_from_file(
    path: Path,
    *,
    kind: str,
    mime_type: str,
    capture_source: str,
    artifact_root: Path | None = None,
) -> EvidenceArtifact:
    """Build trusted evidence metadata for a server-created artifact."""
    root = (artifact_root or RUNS).resolve()
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("Evidence artifact is outside the configured artifact root.")
    if not resolved.is_file():
        raise ValueError("Evidence artifact is not a regular file.")

    digest = sha256()
    with resolved.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)

    return EvidenceArtifact(
        kind=kind,
        path=str(resolved),
        mime_type=mime_type,
        byte_size=resolved.stat().st_size,
        sha256=digest.hexdigest(),
        created_at=datetime.now(UTC).isoformat(),
        capture_source=capture_source,
    )


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
