"""Runtime hardening applied before browser-agent API functions are bound.

This module keeps security fixes isolated from legacy demo history while the
public repository transitions to the operational Project QA baseline.
"""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qsl, urlencode, unquote, urljoin, urlsplit, urlunsplit

from . import browser_agent as _agent
from .browser_agent_models import BrowserAIResult, BrowserDomSnapshot, BrowserObservation, BrowserSessionCreate

_SECRET_QUERY_KEYS = re.compile(
    r"(?i)(token|secret|password|passwd|api[_-]?key|auth|code|session|nonce|wpnonce|rest[_-]?nonce)"
)
_SENSITIVE_ADMIN_PATHS = ("/wp-admin", "/wp-login.php")


def sanitize_browser_url(value: str) -> str:
    """Remove credentials, fragments, and secret-like query parameters."""

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) browser URLs are accepted.")

    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    query = urlencode(
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not _SECRET_QUERY_KEYS.search(key)
    )
    return urlunsplit((parsed.scheme, netloc, parsed.path or "/", query, ""))


def is_sensitive_admin_url(value: str) -> bool:
    """Identify WordPress administration/login URLs that must stay local and human-controlled."""

    try:
        path = unquote(urlsplit(value).path).casefold().rstrip("/")
    except ValueError:
        return True
    return path == "/wp-login.php" or path == "/wp-admin" or path.startswith("/wp-admin/")


def _session_has_sensitive_admin_path(session) -> bool:
    urls = [str(session.startUrl), *(str(item.url) for item in session.observations)]
    return any(is_sensitive_admin_url(value) for value in urls)


_original_ai_cases = _agent._ai_cases
_original_run_session = _agent.run_session


def _guarded_ai_cases(session):
    if _session_has_sensitive_admin_path(session):
        provider = os.getenv("EAGLEEYE_AI_PROVIDER", "codex-agent").strip().casefold()
        model = (
            os.getenv("EAGLEEYE_BROWSER_AI_MODEL", "").strip()
            or os.getenv("EAGLEEYE_CODEX_MODEL", "").strip()
            or "gpt-5.6-terra"
        )
        return (
            [],
            BrowserAIResult(
                provider=provider,
                model=model,
                available=False,
                fallbackUsed=True,
                message=(
                    "AI generation is disabled for WordPress administration and login paths; "
                    "only the local deterministic recording is retained."
                ),
            ),
            [],
            ["管理画面ではAI送信を行わず、非破壊の手動レビューを使用する"],
        )
    return _original_ai_cases(session)


def _guarded_run_session(session_id: str):
    session = _agent.load_session(session_id)
    if _session_has_sensitive_admin_path(session):
        raise PermissionError(
            "Replay is disabled for WordPress administration and login paths. "
            "Use a disposable local fixture or a reviewed non-destructive test environment."
        )
    return _original_run_session(session_id)


def create_local_sample():
    """Create the login-free generic sample without WordPress-shaped routes or labels."""

    target = os.getenv("EAGLEEYE_SAMPLE_TARGET", "http://127.0.0.1:8766/demo-site/")
    target = sanitize_browser_url(target)
    if not _agent.is_run_url_allowed(target):
        raise ValueError("The sample target must be a loopback HTTP(S) URL.")

    sample_target = urljoin(target if target.endswith("/") else target + "/", "sample")
    session = _agent.create_session(
        BrowserSessionCreate(
            name="Authorized local sample journey",
            goal="普段の閲覧操作から回帰テストを生成し、公開ページの主要導線を検証する",
            startUrl=target,
            locale="ja",
        )
    )
    _agent.append_observation(
        session.id,
        BrowserObservation(
            id="sample-goto",
            timestamp=1,
            action="goto",
            url=target,
            redacted=False,
            dom=BrowserDomSnapshot(
                pageTitle="EagleEye Local QA Lab",
                headings=["EagleEye Local QA Lab"],
                landmarks=["main"],
                controls=[],
            ),
        ),
    )
    _agent.append_observation(
        session.id,
        BrowserObservation(
            id="sample-click",
            timestamp=2,
            action="click",
            url=target,
            target={"role": "link", "name": "Sample Page", "tagName": "a"},
            redacted=False,
        ),
    )
    _agent.append_observation(
        session.id,
        BrowserObservation(
            id="sample-snapshot",
            timestamp=3,
            action="snapshot",
            url=sample_target,
            redacted=False,
            dom=BrowserDomSnapshot(
                pageTitle="EagleEye Local QA Lab",
                headings=["Sample Page"],
                landmarks=["main"],
                controls=[],
            ),
        ),
    )
    return _agent.generate_session(session.id)


# Apply before browser_agent_api imports individual functions.
_agent._SECRET_QUERY_KEYS = _SECRET_QUERY_KEYS
_agent._sanitize_url = sanitize_browser_url
_agent._ai_cases = _guarded_ai_cases
_agent.run_session = _guarded_run_session
_agent.create_local_sample = create_local_sample
