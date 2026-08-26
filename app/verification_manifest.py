from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .verification_models import VerificationManifest


def manifest_digest(document: dict) -> str:
    payload = dict(document)
    payload.pop("manifestSha256", None)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def save_manifest(path: Path, manifest: VerificationManifest) -> tuple[Path, str]:
    document = manifest.model_dump(mode="json")
    document["manifestSha256"] = manifest_digest(document)
    validated = VerificationManifest.model_validate(document)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(validated.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
    return path, validated.manifestSha256


def verify_manifest_file(path: Path) -> bool:
    document = json.loads(path.read_text(encoding="utf-8"))
    expected = document.get("manifestSha256")
    if not isinstance(expected, str):
        return False
    return expected == manifest_digest(document)
