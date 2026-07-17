import base64
import hashlib
import json
import os
import re
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse

from .models import EagleEyeBundle

_EXTENSION_ORIGIN_RE = re.compile(r"chrome-extension://[a-z]{32}")
_LOCAL_BROWSER_ORIGINS = ("http://127.0.0.1:8766", "http://localhost:8766")


@lru_cache(maxsize=1)
def _packaged_demo_extension_origin() -> str | None:
    """Derive the public extension identity without hard-coding it in source."""

    manifest_path = Path(__file__).resolve().parents[1] / "chrome-extension" / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        public_key = base64.b64decode(manifest["key"], validate=True)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Packaged extension manifest has an invalid public identity") from exc

    digest = hashlib.sha256(public_key).hexdigest()[:32]
    extension_id = "".join(chr(ord("a") + int(character, 16)) for character in digest)
    return f"chrome-extension://{extension_id}"


def allowed_browser_origins(configured: str | None = None) -> list[str]:
    """Return exact browser origins; extension access is opt-in, never wildcarded."""

    raw = os.getenv("EAGLEEYE_ALLOWED_EXTENSION_ORIGINS", "") if configured is None else configured
    extensions: list[str] = []
    for value in (item.strip() for item in raw.split(",")):
        if not value:
            continue
        if not _EXTENSION_ORIGIN_RE.fullmatch(value):
            raise RuntimeError("Configured extension origins must be exact chrome-extension origins")
        extensions.append(value)
    packaged_origin = _packaged_demo_extension_origin()
    origins = [*_LOCAL_BROWSER_ORIGINS]
    if packaged_origin:
        origins.append(packaged_origin)
    origins.extend(extensions)
    return list(dict.fromkeys(origins))


def is_run_url_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if os.getenv("EAGLEEYE_ALLOW_REMOTE", "0") == "1":
        return True
    host = parsed.hostname or ""
    if host == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def validate_privacy(bundle: EagleEyeBundle) -> None:
    for event in bundle.session.events:
        if event.action in {"fill", "select"} and event.value and not event.redacted:
            raise ValueError("Input-bearing events must be marked as redacted or synthetic.")
        if event.valueType in {"password", "credit-card", "otp", "secret"}:
            raise ValueError("Secret input types are not accepted.")


def sanitize_privacy(bundle: EagleEyeBundle) -> EagleEyeBundle:
    """Validate a bundle and remove every value that was marked as redacted."""

    validate_privacy(bundle)
    payload = bundle.model_dump(mode="json")
    for event in payload["session"]["events"]:
        if event.get("redacted"):
            event["value"] = None
    return EagleEyeBundle.model_validate(payload)
