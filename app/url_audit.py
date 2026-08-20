from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from pathlib import Path
from threading import BoundedSemaphore, Timer
from typing import Protocol
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
from uuid import uuid4

from .test_case_checker import check_test_cases
from .test_case_models import TestCaseCheckRequest, TestCaseDefinition
from .url_audit_models import (
    UrlAuditAsset,
    UrlAuditFinding,
    UrlAuditObservation,
    UrlAuditProjectSeed,
    UrlAuditReport,
    UrlAuditRequest,
)

ROOT = Path(__file__).resolve().parents[1]
URL_AUDITS = ROOT / "artifacts" / "url-audits"
_MAX_ROOT_BYTES = 512 * 1024
_MAX_DISCOVERY_BYTES = 512 * 1024
_MAX_REDIRECTS = 3
_MAX_REQUESTS = 10
_MAX_TOTAL_BODY_BYTES = 4 * 1024 * 1024
_MAX_WALL_SECONDS = 30.0
_SECRET_QUERY = re.compile(r"(?i)(?:token|secret|password|passwd|api[_-]?key|auth|code|session)")
_SAFE_RESPONSE_HEADERS = {
    "access-control-allow-credentials",
    "access-control-allow-headers",
    "access-control-allow-methods",
    "access-control-allow-origin",
    "cache-control",
    "content-length",
    "content-security-policy",
    "content-type",
    "cross-origin-embedder-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "location",
    "permissions-policy",
    "referrer-policy",
    "server",
    "strict-transport-security",
    "vary",
    "x-content-type-options",
    "x-frame-options",
    "x-powered-by",
}
_AUDIT_SLOTS = BoundedSemaphore(value=2)
_DNS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="eagleeye-url-audit-dns")
_IPV6_TRANSLATION_NETWORKS = (
    ip_network("64:ff9b::/96"),
    ip_network("64:ff9b:1::/48"),
)


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    truncated: bool
    tls_version: str | None
    duration_ms: int


@dataclass
class AuditBudget:
    request_limit: int = _MAX_REQUESTS
    body_limit: int = _MAX_TOTAL_BODY_BYTES
    deadline: float = field(default_factory=lambda: time.monotonic() + _MAX_WALL_SECONDS)
    request_count: int = 0
    body_bytes: int = 0

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def ensure_within_deadline(self) -> None:
        if self.remaining_seconds() <= 0:
            raise ValueError("URL audit wall-clock budget exhausted")

    def before_request(self, method: str) -> int:
        if self.request_count >= self.request_limit:
            raise ValueError("URL audit request budget exhausted")
        self.ensure_within_deadline()
        remaining = self.body_limit - self.body_bytes
        if method == "GET" and remaining <= 0:
            raise ValueError("URL audit response-byte budget exhausted")
        self.request_count += 1
        return max(0, remaining)

    def record_body(self, size: int) -> None:
        self.body_bytes += size
        if self.body_bytes > self.body_limit:
            raise ValueError("URL audit response-byte budget exhausted")


class AuditTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        resolved_ip: str,
        headers: dict[str, str],
        max_bytes: int,
        deadline: float,
    ) -> TransportResponse: ...


class PinnedHttpTransport:
    """Issue one HTTP/1.1 request to the already validated IP address."""

    def __init__(self, timeout_seconds: float = 3.0) -> None:
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        url: str,
        resolved_ip: str,
        headers: dict[str, str],
        max_bytes: int,
        deadline: float,
    ) -> TransportResponse:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        started = time.monotonic()
        raw_socket = socket.create_connection(
            (resolved_ip, port),
            timeout=self._remaining_timeout(deadline),
        )
        connection: socket.socket | ssl.SSLSocket = raw_socket
        connection_box: list[socket.socket | ssl.SSLSocket] = [connection]
        watchdog = Timer(
            max(0.001, deadline - time.monotonic()),
            self._abort_connection,
            args=(connection_box,),
        )
        watchdog.daemon = True
        watchdog.start()
        tls_version = None
        try:
            if parsed.scheme == "https":
                context = _secure_tls_context()
                raw_socket.settimeout(self._remaining_timeout(deadline))
                connection = context.wrap_socket(raw_socket, server_hostname=host)
                connection_box[0] = connection
                tls_version = connection.version()
            connection.settimeout(self._remaining_timeout(deadline))
            request_headers = {
                "Host": _host_header(parsed),
                "User-Agent": "EagleEye-URL-Audit/1.0 (+observation-only)",
                "Accept": "text/html, application/json, application/xml, text/plain, */*;q=0.1",
                "Accept-Encoding": "identity",
                "Connection": "close",
                **headers,
            }
            target = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
            if parsed.query:
                target = f"{target}?{parsed.query}"
            lines = [f"{method} {target} HTTP/1.1"]
            lines.extend(f"{name}: {value}" for name, value in request_headers.items())
            payload = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")
            connection.sendall(payload)
            connection.settimeout(self._remaining_timeout(deadline))
            response = http.client.HTTPResponse(connection)
            response.begin()
            connection.settimeout(self._remaining_timeout(deadline))
            body = b"" if method == "HEAD" else response.read(max_bytes + 1)
            if time.monotonic() >= deadline:
                raise TimeoutError("URL audit wall-clock budget exhausted")
            if (
                method != "HEAD"
                and response.length is not None
                and response.length > 0
                and len(body) < max_bytes + 1
            ):
                raise http.client.IncompleteRead(body, len(body) + response.length)
            truncated = len(body) > max_bytes
            body = body[:max_bytes]
            safe_headers = _safe_headers(response.getheaders())
            return TransportResponse(
                status_code=response.status,
                headers=safe_headers,
                body=body,
                truncated=truncated,
                tls_version=tls_version,
                duration_ms=round((time.monotonic() - started) * 1_000),
            )
        finally:
            watchdog.cancel()
            connection.close()

    def _remaining_timeout(self, deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("URL audit wall-clock budget exhausted")
        return max(0.001, min(self.timeout_seconds, remaining))

    @staticmethod
    def _abort_connection(connection_box: list[socket.socket | ssl.SSLSocket]) -> None:
        connection = connection_box[0]
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        connection.close()


class _AuditHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.icon_hrefs: list[str] = []
        self.login_hrefs: list[tuple[str, str]] = []
        self.script_sources: list[str] = []
        self.generator: str | None = None
        self.has_password_input = False
        self._anchor_href: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.casefold(): value or "" for name, value in attrs}
        normalized = tag.casefold()
        if normalized == "link" and "icon" in values.get("rel", "").casefold():
            if values.get("href"):
                self.icon_hrefs.append(values["href"])
        elif normalized == "a":
            self._anchor_href = values.get("href") or None
            self._anchor_text = []
        elif normalized == "input" and values.get("type", "").casefold() == "password":
            self.has_password_input = True
        elif normalized == "script" and values.get("src"):
            self.script_sources.append(values["src"])
        elif normalized == "meta" and values.get("name", "").casefold() == "generator":
            self.generator = values.get("content") or None

    def handle_data(self, data: str) -> None:
        if self._anchor_href is not None:
            self._anchor_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._anchor_href is None:
            return
        text = " ".join("".join(self._anchor_text).split())
        if re.search(r"(?i)\b(?:login|log in|sign in|signin)\b|ログイン|サインイン", text):
            self.login_hrefs.append((self._anchor_href, text or "login"))
        self._anchor_href = None
        self._anchor_text = []


def run_url_audit(
    request: UrlAuditRequest,
    *,
    transport: AuditTransport | None = None,
) -> UrlAuditReport:
    if not _AUDIT_SLOTS.acquire(blocking=False):
        raise RuntimeError("URL audit concurrency limit reached")
    try:
        return _run_url_audit(request, transport=transport)
    finally:
        _AUDIT_SLOTS.release()


def _run_url_audit(
    request: UrlAuditRequest,
    *,
    transport: AuditTransport | None = None,
) -> UrlAuditReport:
    audit_id = uuid4().hex
    started_at = _now()
    target = _normalize_url(str(request.targetUrl))
    audit_transport = transport or PinnedHttpTransport()
    budget = AuditBudget()
    observations: list[UrlAuditObservation] = []
    findings: list[UrlAuditFinding] = []
    assets: list[UrlAuditAsset] = []

    root_head, _ = _observe(
        "root-head",
        "HEAD",
        target,
        request.allowLocalhost,
        audit_transport,
        _MAX_ROOT_BYTES,
        budget=budget,
    )
    observations.append(root_head)
    root_get, root_body = _observe(
        "root-get",
        "GET",
        target,
        request.allowLocalhost,
        audit_transport,
        _MAX_ROOT_BYTES,
        budget=budget,
    )
    observations.append(root_get)
    final_url = root_get.finalUrl or root_head.finalUrl

    if root_get.error or root_get.statusCode is None:
        findings.append(
            _finding(
                "network-unavailable",
                "network",
                "BLOCKED",
                "high",
                "Target could not be observed",
                root_get.error or "The target did not return an HTTP response.",
                ["root-get"],
            )
        )
        report = UrlAuditReport(
            auditId=audit_id,
            requestedUrl=_safe_url(target),
            finalUrl=final_url,
            authorized=True,
            localhostAllowed=request.allowLocalhost,
            startedAt=started_at,
            completedAt=_now(),
            decision="BLOCKED",
            findings=findings,
            observations=observations,
            assets=assets,
            technologies=[],
            project=None,
            reportJson=_report_relative(audit_id, "report.json"),
            reportMarkdown=_report_relative(audit_id, "report.md"),
        )
        return _save_report(report)

    base_url = _origin_url(final_url or target)
    cors, _ = _observe(
        "cors-preflight",
        "OPTIONS",
        base_url,
        request.allowLocalhost,
        audit_transport,
        0,
        {
            "Origin": "https://eagleeye.invalid",
            "Access-Control-Request-Method": "GET",
        },
        budget,
    )
    observations.append(cors)
    _add_https_findings(findings, target, root_head, root_get)
    _add_header_findings(findings, root_get)
    _add_cors_findings(findings, cors)

    discovery_specs = (
        ("robots", "robots", "/robots.txt"),
        ("sitemap", "sitemap", "/sitemap.xml"),
        ("security-txt", "security_txt", "/.well-known/security.txt"),
    )
    for observation_id, kind, path in discovery_specs:
        observation, body = _observe(
            observation_id,
            "GET",
            urljoin(base_url, path),
            request.allowLocalhost,
            audit_transport,
            _MAX_DISCOVERY_BYTES,
            budget=budget,
        )
        observations.append(observation)
        assets.append(_asset(kind, observation, _discovery_detail(kind, body)))

    openapi_observation: UrlAuditObservation | None = None
    openapi_detail: str | None = None
    for index, path in enumerate(
        ("/openapi.json", "/.well-known/openapi.json", "/swagger.json"),
        1,
    ):
        observation, body = _observe(
            f"openapi-{index}",
            "GET",
            urljoin(base_url, path),
            request.allowLocalhost,
            audit_transport,
            _MAX_DISCOVERY_BYTES,
            budget=budget,
        )
        observations.append(observation)
        parsed = _openapi_detail(body)
        if observation.statusCode and 200 <= observation.statusCode < 300 and parsed:
            openapi_observation = observation
            openapi_detail = parsed
            break
    if openapi_observation:
        assets.append(_asset("openapi", openapi_observation, openapi_detail))
        findings.append(
            _finding(
                "openapi-discovered",
                "openapi",
                "INFO",
                "info",
                "OpenAPI document discovered",
                openapi_detail or "A bounded OpenAPI document was observed.",
                [openapi_observation.id],
            )
        )
    else:
        findings.append(
            _finding(
                "openapi-not-observed",
                "openapi",
                "INFO",
                "info",
                "OpenAPI document not observed",
                "None of the three fixed OpenAPI well-known paths returned a valid document.",
                [f"openapi-{index}" for index in range(1, 4)],
            )
        )

    parser = _parse_html(root_body, root_get.responseHeaders.get("content-type", ""))
    favicon_url = _favicon_url(parser, final_url or target)
    if favicon_url and _same_origin(favicon_url, base_url):
        favicon, _ = _observe(
            "favicon",
            "HEAD",
            favicon_url,
            request.allowLocalhost,
            audit_transport,
            0,
            budget=budget,
        )
        observations.append(favicon)
        assets.append(_asset("favicon", favicon, "HTML icon link or conventional favicon path"))
    elif favicon_url:
        assets.append(
            UrlAuditAsset(
                kind="favicon",
                url=_safe_url(favicon_url),
                available=False,
                detail="An external favicon hint was observed but was not requested.",
            )
        )

    login_assets = _login_assets(parser, final_url or target)
    assets.extend(login_assets)
    _add_discovery_findings(findings, assets)
    if login_assets:
        findings.append(
            _finding(
                "login-hint-observed",
                "login",
                "INFO",
                "info",
                "Login flow hint observed",
                "A password field or login-labelled link was observed; it was not opened or submitted.",
                ["root-get"],
            )
        )

    technologies = _technology_hints(parser, root_body, root_get.responseHeaders)
    if technologies:
        findings.append(
            _finding(
                "technology-hints",
                "technology",
                "INFO",
                "info",
                "Technology hints observed",
                ", ".join(technologies),
                ["root-get"],
            )
        )

    _add_observation_completeness_findings(findings, observations)

    project = _project_seed(
        audit_id,
        request.projectName,
        final_url or target,
        findings,
        bool(openapi_observation),
        bool(login_assets),
    )
    decision = "PASS_WITH_WARNING" if any(item.status == "WARN" for item in findings) else "PASS"
    report = UrlAuditReport(
        auditId=audit_id,
        requestedUrl=_safe_url(target),
        finalUrl=final_url,
        authorized=True,
        localhostAllowed=request.allowLocalhost,
        startedAt=started_at,
        completedAt=_now(),
        decision=decision,
        findings=findings,
        observations=observations,
        assets=assets,
        technologies=technologies,
        project=project,
        reportJson=_report_relative(audit_id, "report.json"),
        reportMarkdown=_report_relative(audit_id, "report.md"),
    )
    return _save_report(report)


def load_url_audit(audit_id: str) -> UrlAuditReport:
    if not re.fullmatch(r"[a-f0-9]{32}", audit_id):
        raise ValueError("Invalid URL audit id")
    path = URL_AUDITS / audit_id / "report.json"
    if not path.is_file():
        raise FileNotFoundError(audit_id)
    return UrlAuditReport.model_validate_json(path.read_text(encoding="utf-8"))


def url_audit_markdown(audit_id: str) -> str:
    load_url_audit(audit_id)
    path = URL_AUDITS / audit_id / "report.md"
    if not path.is_file():
        raise FileNotFoundError(audit_id)
    return path.read_text(encoding="utf-8")


def delete_url_audit(audit_id: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{32}", audit_id):
        raise ValueError("Invalid URL audit id")
    directory = URL_AUDITS / audit_id
    if not directory.is_dir():
        raise FileNotFoundError(audit_id)
    shutil.rmtree(directory)


def _observe(
    observation_id: str,
    method: str,
    url: str,
    allow_localhost: bool,
    transport: AuditTransport,
    max_bytes: int,
    headers: dict[str, str] | None = None,
    budget: AuditBudget | None = None,
) -> tuple[UrlAuditObservation, bytes]:
    started = time.monotonic()
    current = _normalize_url(url)
    initial = current
    chain: list[str] = []
    try:
        for _ in range(_MAX_REDIRECTS + 1):
            remaining_bytes = budget.before_request(method) if budget else max_bytes
            deadline = budget.deadline if budget else time.monotonic() + _MAX_WALL_SECONDS
            resolved_ip = _resolve_url(current, allow_localhost, deadline)
            response = transport.request(
                method,
                current,
                resolved_ip,
                headers or {},
                min(max_bytes, remaining_bytes),
                deadline,
            )
            if budget:
                budget.record_body(len(response.body))
                budget.ensure_within_deadline()
            location = response.headers.get("location")
            if response.status_code not in {301, 302, 303, 307, 308} or not location or method == "OPTIONS":
                return (
                    UrlAuditObservation(
                        id=observation_id,
                        method=method,
                        url=_safe_url(initial),
                        finalUrl=_safe_url(current),
                        statusCode=response.status_code,
                        durationMs=round((time.monotonic() - started) * 1_000),
                        responseHeaders=_semantic_headers(response.headers),
                        redirectChain=chain,
                        bodySha256=hashlib.sha256(response.body).hexdigest() if response.body else None,
                        bodyBytes=len(response.body),
                        truncated=response.truncated,
                        tlsVersion=response.tls_version,
                    ),
                    response.body,
                )
            next_url = _normalize_url(urljoin(current, location))
            if not _redirect_allowed(current, next_url):
                return (
                    UrlAuditObservation(
                        id=observation_id,
                        method=method,
                        url=_safe_url(initial),
                        finalUrl=_safe_url(current),
                        statusCode=response.status_code,
                        durationMs=round((time.monotonic() - started) * 1_000),
                        responseHeaders=_semantic_headers(response.headers),
                        redirectChain=[*chain, _safe_url(next_url)],
                        error="Redirect left the authorized hostname or transport boundary.",
                    ),
                    b"",
                )
            chain.append(_safe_url(next_url))
            current = next_url
        raise ValueError("Redirect limit exceeded")
    except (OSError, ssl.SSLError, ValueError, PermissionError, http.client.HTTPException) as exc:
        return (
            UrlAuditObservation(
                id=observation_id,
                method=method,
                url=_safe_url(initial),
                finalUrl=_safe_url(current),
                durationMs=round((time.monotonic() - started) * 1_000),
                redirectChain=chain,
                error=_safe_error(exc),
            ),
            b"",
        )


def _resolve_url(url: str, allow_localhost: bool, deadline: float) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError("URL audit wall-clock budget exhausted")
    future = _DNS_EXECUTOR.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
    try:
        records = future.result(timeout=remaining)
    except FutureTimeoutError as exc:
        future.cancel()
        raise ValueError("Target DNS resolution exceeded the URL audit wall-clock budget") from exc
    except socket.gaierror as exc:
        raise ValueError("Target hostname could not be resolved") from exc
    addresses = sorted({record[4][0].split("%", 1)[0] for record in records})
    if not addresses:
        raise ValueError("Target hostname returned no usable address")
    parsed_addresses = [ip_address(value) for value in addresses]
    explicit_loopback = _explicit_loopback_host(host)
    forbidden = [
        address
        for address in parsed_addresses
        if _is_forbidden_address(address) and not (explicit_loopback and address.is_loopback)
    ]
    if forbidden:
        raise PermissionError(
            "LAN, link-local, metadata, multicast, reserved, and DNS-derived loopback targets "
            "are never audited"
        )
    if explicit_loopback and any(not address.is_loopback for address in parsed_addresses):
        raise PermissionError("An explicit localhost target must resolve only to loopback addresses")
    if explicit_loopback and not allow_localhost:
        raise PermissionError("Loopback targets require explicit request opt-in")
    if explicit_loopback and os.getenv("EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST", "0") != "1":
        raise PermissionError("Loopback audits also require EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST=1")
    return addresses[0]


def _is_forbidden_address(address: IPv4Address | IPv6Address) -> bool:
    return (
        not address.is_global
        or address.is_private
        or address.is_link_local
        or address.is_loopback
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or (
            isinstance(address, IPv6Address)
            and any(address in network for network in _IPV6_TRANSLATION_NETWORKS)
        )
    )


def _explicit_loopback_host(host: str) -> bool:
    normalized = host.rstrip(".").casefold()
    if normalized == "localhost":
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def _secure_tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def _normalize_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only absolute HTTP(S) URLs are accepted")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not accepted")
    if any(ord(character) < 32 for character in value):
        raise ValueError("URL contains control characters")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL port is invalid") from exc
    if port is not None and not 1 <= port <= 65_535:
        raise ValueError("URL port is invalid")
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    if any(_SECRET_QUERY.search(name) for name, _ in query_items):
        raise ValueError("Secret-like query parameters are not accepted")
    hostname = parsed.hostname.encode("idna").decode("ascii")
    netloc = _format_netloc(hostname, port, parsed.scheme.casefold())
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            netloc,
            parsed.path or "/",
            urlencode(query_items, doseq=True),
            "",
        )
    )


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    query = urlencode([(name, "[redacted]") for name, _ in parse_qsl(parsed.query, keep_blank_values=True)])
    host = parsed.hostname or ""
    netloc = _format_netloc(host, parsed.port, parsed.scheme)
    return urlunsplit((parsed.scheme, netloc, parsed.path or "/", query, ""))


def _format_netloc(host: str, port: int | None, scheme: str) -> str:
    rendered = f"[{host}]" if ":" in host else host
    default = 443 if scheme == "https" else 80
    return rendered if port is None or port == default else f"{rendered}:{port}"


def _host_header(parsed) -> str:  # type: ignore[no-untyped-def]
    return _format_netloc(parsed.hostname or "", parsed.port, parsed.scheme)


def _safe_headers(headers: list[tuple[str, str]]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for raw_name, raw_value in headers:
        name = raw_name.casefold()
        if name not in _SAFE_RESPONSE_HEADERS or name in safe:
            continue
        value = " ".join(raw_value.replace("\r", " ").replace("\n", " ").split())[:1_000]
        safe[name] = _safe_url(value) if name == "location" else value
    return safe


def _semantic_headers(headers: dict[str, str]) -> dict[str, str]:
    semantic: dict[str, str] = {}
    content_type = headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if content_type:
        semantic["content-type"] = content_type[:100]
    length = headers.get("content-length", "")
    if length.isdigit():
        semantic["content-length"] = length[:20]
    presence_headers = (
        "strict-transport-security",
        "referrer-policy",
        "permissions-policy",
        "cross-origin-embedder-policy",
        "cross-origin-opener-policy",
        "cross-origin-resource-policy",
    )
    for name in presence_headers:
        if headers.get(name):
            semantic[name] = "present"
    csp = headers.get("content-security-policy", "").casefold()
    if csp:
        frame = "yes" if "frame-ancestors" in csp else "no"
        semantic["content-security-policy"] = f"present; frame-ancestors={frame}"
    nosniff = headers.get("x-content-type-options", "").casefold()
    if nosniff:
        semantic["x-content-type-options"] = "nosniff" if "nosniff" in nosniff else "present"
    frame_options = headers.get("x-frame-options", "").casefold()
    if frame_options:
        semantic["x-frame-options"] = frame_options if frame_options in {"deny", "sameorigin"} else "present"
    allow_origin = headers.get("access-control-allow-origin", "")
    if allow_origin:
        if allow_origin == "*":
            semantic["access-control-allow-origin"] = "*"
        elif allow_origin == "https://eagleeye.invalid":
            semantic["access-control-allow-origin"] = "synthetic-audit-origin"
        else:
            semantic["access-control-allow-origin"] = "specific-origin"
    allow_credentials = headers.get("access-control-allow-credentials", "").casefold()
    if allow_credentials:
        semantic["access-control-allow-credentials"] = "true" if allow_credentials == "true" else "present"
    for name in ("access-control-allow-methods", "access-control-allow-headers", "vary"):
        if headers.get(name):
            semantic[name] = "present"
    cache_control = headers.get("cache-control", "").casefold()
    if cache_control:
        semantic["cache-control"] = "no-store" if "no-store" in cache_control else "present"
    known_products = {
        "server": ("nginx", "apache", "cloudflare", "uvicorn", "gunicorn", "microsoft-iis"),
        "x-powered-by": ("express", "php", "asp.net"),
    }
    for name, products in known_products.items():
        value = headers.get(name, "").casefold()
        product = next((item for item in products if item in value), None)
        if product:
            semantic[name] = product
    return semantic


def _redirect_allowed(current: str, candidate: str) -> bool:
    left = urlsplit(current)
    right = urlsplit(candidate)
    if (left.hostname or "").casefold() != (right.hostname or "").casefold():
        return False
    left_port = left.port or (443 if left.scheme == "https" else 80)
    right_port = right.port or (443 if right.scheme == "https" else 80)
    if left.scheme == right.scheme:
        return left_port == right_port
    return left.scheme == "http" and right.scheme == "https" and left_port == 80 and right_port == 443


def _origin_url(value: str) -> str:
    parsed = urlsplit(value)
    netloc = _format_netloc(parsed.hostname or "", parsed.port, parsed.scheme)
    return urlunsplit((parsed.scheme, netloc, "/", "", ""))


def _same_origin(left: str, right: str) -> bool:
    first = urlsplit(left)
    second = urlsplit(right)
    return (
        first.scheme.casefold(),
        (first.hostname or "").casefold(),
        first.port or (443 if first.scheme == "https" else 80),
    ) == (
        second.scheme.casefold(),
        (second.hostname or "").casefold(),
        second.port or (443 if second.scheme == "https" else 80),
    )


def _parse_html(body: bytes, content_type: str) -> _AuditHtmlParser:
    parser = _AuditHtmlParser()
    if not body or ("html" not in content_type.casefold() and not body.lstrip().startswith(b"<")):
        return parser
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
    except (UnicodeError, ValueError):
        return _AuditHtmlParser()
    return parser


def _favicon_url(parser: _AuditHtmlParser, page_url: str) -> str:
    if parser.icon_hrefs:
        return _safe_url(urljoin(page_url, parser.icon_hrefs[0]))
    return urljoin(_origin_url(page_url), "/favicon.ico")


def _login_assets(parser: _AuditHtmlParser, page_url: str) -> list[UrlAuditAsset]:
    assets: list[UrlAuditAsset] = []
    if parser.has_password_input:
        assets.append(
            UrlAuditAsset(
                kind="login_hint",
                url=_safe_url(page_url),
                available=True,
                detail="Password input observed on the fetched page; no value was entered.",
            )
        )
    for href, _ in parser.login_hrefs[:5]:
        assets.append(
            UrlAuditAsset(
                kind="login_hint",
                url=_safe_url(urljoin(page_url, href)),
                available=True,
                detail="Login-labelled link observed; the destination was not requested.",
            )
        )
    return assets


def _technology_hints(
    parser: _AuditHtmlParser,
    body: bytes,
    headers: dict[str, str],
) -> list[str]:
    text = body[:_MAX_ROOT_BYTES].decode("utf-8", errors="ignore").casefold()
    hints: list[str] = []
    server = headers.get("server")
    powered_by = headers.get("x-powered-by")
    if server:
        hints.append(f"Server header: {server[:100]}")
    if powered_by:
        hints.append(f"X-Powered-By: {powered_by[:100]}")
    if parser.generator:
        generator = parser.generator.casefold()
        for known in ("wordpress", "drupal", "joomla", "ghost"):
            if known in generator:
                hints.append(f"Generator: {known}")
                break
    markers = {
        "React": ("data-reactroot", "react-dom"),
        "Next.js": ("__next_data__", "/_next/"),
        "Vue": ("data-v-", "vue.js"),
        "Angular": ("ng-version", "ng-app"),
        "WordPress": ("/wp-content/", "wp-json"),
    }
    sources = " ".join([text, *[item.casefold() for item in parser.script_sources]])
    hints.extend(name for name, values in markers.items() if any(value in sources for value in values))
    return list(dict.fromkeys(hints))[:20]


def _openapi_detail(body: bytes) -> str | None:
    if not body:
        return None
    try:
        document = json.loads(body)
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict) or not (document.get("openapi") or document.get("swagger")):
        return None
    paths = document.get("paths") if isinstance(document.get("paths"), dict) else {}
    version = str(document.get("openapi") or document.get("swagger"))[:40]
    return f"OpenAPI specification {version}; {len(paths)} path(s)"


def _discovery_detail(kind: str, body: bytes) -> str | None:
    text = body.decode("utf-8", errors="ignore")
    if kind == "robots":
        sitemaps = sum(1 for line in text.splitlines() if line.casefold().startswith("sitemap:"))
        return f"{len(text.splitlines())} line(s), {sitemaps} sitemap directive(s)"
    if kind == "sitemap":
        return f"{text.casefold().count('<url')} URL entry hint(s)"
    if kind == "security_txt":
        contacts = sum(1 for line in text.splitlines() if line.casefold().startswith("contact:"))
        return f"{contacts} contact directive(s)"
    return None


def _asset(kind: str, observation: UrlAuditObservation, detail: str | None) -> UrlAuditAsset:
    available = bool(observation.statusCode and 200 <= observation.statusCode < 300 and not observation.error)
    return UrlAuditAsset(
        kind=kind,  # type: ignore[arg-type]
        url=observation.finalUrl or observation.url,
        available=available,
        statusCode=observation.statusCode,
        detail=detail if available else observation.error,
    )


def _add_https_findings(
    findings: list[UrlAuditFinding],
    target: str,
    head: UrlAuditObservation,
    get: UrlAuditObservation,
) -> None:
    final = get.finalUrl or head.finalUrl or target
    if urlsplit(final).scheme == "https":
        detail = "The observed final URL uses HTTPS."
        if urlsplit(target).scheme == "http":
            detail += " The supplied HTTP URL upgraded on the same hostname."
        findings.append(
            _finding(
                "https-enabled",
                "https",
                "PASS",
                "info",
                "HTTPS observed",
                detail,
                ["root-head", "root-get"],
            )
        )
        return
    findings.append(
        _finding(
            "https-not-enabled",
            "https",
            "WARN",
            "high",
            "HTTPS was not observed",
            "The final observed URL remained on plaintext HTTP.",
            ["root-head", "root-get"],
        )
    )


def _add_header_findings(findings: list[UrlAuditFinding], root: UrlAuditObservation) -> None:
    headers = root.responseHeaders
    required = {
        "content-security-policy": "Content-Security-Policy",
        "x-content-type-options": "X-Content-Type-Options",
        "referrer-policy": "Referrer-Policy",
        "permissions-policy": "Permissions-Policy",
    }
    if root.finalUrl and urlsplit(root.finalUrl).scheme == "https":
        required["strict-transport-security"] = "Strict-Transport-Security"
    missing = [label for name, label in required.items() if not headers.get(name)]
    has_frame_defense = (
        bool(headers.get("x-frame-options"))
        or "frame-ancestors" in headers.get("content-security-policy", "").casefold()
    )
    if not has_frame_defense:
        missing.append("X-Frame-Options or CSP frame-ancestors")
    if missing:
        findings.append(
            _finding(
                "security-headers-incomplete",
                "security_headers",
                "WARN",
                "medium",
                "Security headers are incomplete",
                "Not observed: " + ", ".join(missing),
                ["root-get"],
            )
        )
    else:
        findings.append(
            _finding(
                "security-headers-present",
                "security_headers",
                "PASS",
                "info",
                "Baseline security headers observed",
                "The deterministic baseline headers were present on the root response.",
                ["root-get"],
            )
        )


def _add_cors_findings(findings: list[UrlAuditFinding], cors: UrlAuditObservation) -> None:
    if cors.error or cors.statusCode is None:
        findings.append(
            _finding(
                "cors-not-evaluated",
                "cors",
                "WARN",
                "medium",
                "CORS preflight could not be evaluated",
                cors.error or "The safe preflight did not return an HTTP response.",
                ["cors-preflight"],
            )
        )
        return
    allowed = cors.responseHeaders.get("access-control-allow-origin")
    credentials = cors.responseHeaders.get("access-control-allow-credentials", "").casefold()
    if allowed == "*" and credentials == "true":
        findings.append(
            _finding(
                "cors-wildcard-credentials",
                "cors",
                "WARN",
                "high",
                "CORS response combines wildcard origin and credentials",
                "The safe preflight observed a risky or invalid cross-origin policy combination.",
                ["cors-preflight"],
            )
        )
    elif allowed == "*":
        findings.append(
            _finding(
                "cors-wildcard",
                "cors",
                "WARN",
                "medium",
                "CORS allows every origin",
                "The safe preflight observed Access-Control-Allow-Origin: *.",
                ["cors-preflight"],
            )
        )
    else:
        findings.append(
            _finding(
                "cors-observed",
                "cors",
                "INFO",
                "info",
                "CORS preflight observed",
                (
                    f"The response allowed origin {allowed}."
                    if allowed
                    else "No cross-origin allowance was returned for the synthetic audit origin."
                ),
                ["cors-preflight"],
            )
        )


def _add_discovery_findings(
    findings: list[UrlAuditFinding],
    assets: list[UrlAuditAsset],
) -> None:
    observed = sorted({asset.kind for asset in assets if asset.available and asset.kind != "login_hint"})
    findings.append(
        _finding(
            "standard-assets",
            "discovery",
            "INFO",
            "info",
            "Standard assets observed",
            ", ".join(observed) if observed else "No standard discovery asset returned HTTP 2xx.",
            [],
        )
    )


def _add_observation_completeness_findings(
    findings: list[UrlAuditFinding],
    observations: list[UrlAuditObservation],
) -> None:
    incomplete = [item for item in observations if item.error or item.truncated]
    if not incomplete:
        return
    error_count = sum(bool(item.error) for item in incomplete)
    truncated_count = sum(item.truncated for item in incomplete)
    findings.append(
        _finding(
            "audit-incomplete",
            "network",
            "WARN",
            "medium",
            "URL Audit completed with incomplete observations",
            f"{error_count} request error(s) and {truncated_count} truncated response(s) require review.",
            [item.id for item in incomplete],
        )
    )


def _project_seed(
    audit_id: str,
    requested_name: str | None,
    source_url: str,
    findings: list[UrlAuditFinding],
    has_openapi: bool,
    has_login: bool,
) -> UrlAuditProjectSeed:
    host = urlsplit(source_url).hostname or "web-project"
    slug = re.sub(r"[^a-z0-9-]", "-", host.casefold()).strip("-") or "web-project"
    project_id = f"url-{slug[:56]}-{audit_id[:8]}"
    cases = _initial_cases(source_url, has_openapi, has_login)
    required_types = ["security", "api"]
    if has_login:
        required_types.append("e2e")
    quality = check_test_cases(
        TestCaseCheckRequest(
            projectId=project_id,
            cases=cases,
            requiredTestTypes=required_types,
        )
    )
    warning_count = sum(item.status == "WARN" for item in findings)
    next_actions = [
        f"Review {warning_count} audit warning(s) and accept or remediate each observation.",
        "Open Browser Agent with browserAgentStartUrl and record the critical user journey.",
        "Generate complementary cases, run Replay, and preserve the evidence package.",
    ]
    if has_openapi:
        next_actions.insert(1, "Import the discovered OpenAPI contract into authorized API coverage.")
    if has_login:
        next_actions.insert(1, "Record the login flow without storing credentials or one-time codes.")
    return UrlAuditProjectSeed(
        id=project_id,
        name=requested_name or f"QA for {host}",
        auditId=audit_id,
        sourceUrl=_safe_url(source_url),
        browserAgentStartUrl=_safe_url(source_url),
        initialTestCases=cases,
        caseQuality=quality,
        nextActions=next_actions,
    )


def _initial_cases(source_url: str, has_openapi: bool, has_login: bool) -> list[TestCaseDefinition]:
    cases = [
        TestCaseDefinition(
            id="URL-SEC-001",
            title="HTTPS transport and redirect boundary remain protected",
            type="security",
            preconditions=["The target URL is explicitly authorized for observation-only QA"],
            steps=["Request the authorized root URL without credentials and observe the final transport"],
            expectedResults=["The final URL uses HTTPS without leaving the authorized hostname boundary"],
            assertions=[
                "final_url.scheme == https",
                "every redirect hostname equals the authorized hostname",
            ],
            tags=["url-audit", "https", "generated"],
            priority="high",
            criticalFlow=True,
        ),
        TestCaseDefinition(
            id="URL-SEC-002",
            title="Root response exposes the baseline browser security headers",
            type="security",
            steps=["Fetch the authorized root document with a bounded read-only GET request"],
            expectedResults=[
                "The response includes CSP, nosniff, referrer, permissions, and frame protections"
            ],
            assertions=[
                "required_security_headers are present",
                "response body remains within the byte limit",
            ],
            tags=["url-audit", "headers", "generated"],
            priority="high",
        ),
        TestCaseDefinition(
            id="URL-API-001",
            title="CORS preflight does not grant unintended cross-origin access",
            type="api",
            steps=["Send one safe OPTIONS preflight from the synthetic EagleEye audit origin"],
            expectedResults=[
                "The response does not combine wildcard origin access with credential permission"
            ],
            assertions=["not (allow_origin == * and allow_credentials == true)"],
            tags=["url-audit", "cors", "generated"],
            priority="high",
        ),
        TestCaseDefinition(
            id="URL-API-002",
            title="Standard QA discovery resources remain observable and bounded",
            type="api",
            steps=["Request only the fixed robots, sitemap, security.txt, OpenAPI, and favicon locations"],
            expectedResults=[
                "Every observation records status, byte count, and SHA-256 without brute-force discovery"
            ],
            assertions=["request_count is bounded", "successful response hashes match captured bytes"],
            tags=["url-audit", "discovery", "generated"],
        ),
    ]
    if has_openapi:
        cases.append(
            TestCaseDefinition(
                id="URL-API-003",
                title="Discovered OpenAPI contract parses as a bounded API description",
                type="api",
                steps=["Parse the discovered bounded JSON document without invoking any described operation"],
                expectedResults=["The document declares an OpenAPI or Swagger version and a paths object"],
                assertions=["openapi or swagger version is present", "paths is an object"],
                tags=["url-audit", "openapi", "generated"],
                priority="high",
            )
        )
    if has_login:
        cases.append(
            TestCaseDefinition(
                id="URL-E2E-001",
                title="Authorized login journey can be recorded without retaining credentials",
                type="e2e",
                preconditions=["A human operator approves the login-flow recording"],
                steps=["Open the observed login entry and record only redacted input-bearing actions"],
                expectedResults=[
                    "The generated session contains no password, token, cookie, or one-time code value"
                ],
                assertions=["all input events are redacted", "stored credential values are absent"],
                tags=["url-audit", "login", "browser-agent", "generated"],
                priority="high",
                criticalFlow=True,
            )
        )
    for case in cases:
        case.preconditions = [*case.preconditions, f"Authorized target: {_safe_url(source_url)}"]
    return cases


def _finding(
    identifier: str,
    category: str,
    status: str,
    severity: str,
    title: str,
    detail: str,
    evidence: list[str],
) -> UrlAuditFinding:
    return UrlAuditFinding(
        id=identifier,
        category=category,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        title=title,
        detail=detail,
        evidence=evidence,
    )


def _save_report(report: UrlAuditReport) -> UrlAuditReport:
    directory = URL_AUDITS / report.auditId
    directory.mkdir(parents=True, exist_ok=True)
    _atomic_write(directory / "report.json", report.model_dump_json(indent=2))
    _atomic_write(directory / "report.md", _markdown(report))
    return report


def _report_relative(audit_id: str, name: str) -> str:
    return f"artifacts/url-audits/{audit_id}/{name}"


def _markdown(report: UrlAuditReport) -> str:
    finding_rows = "\n".join(
        f"| {item.status} | {_md(item.category)} | {_md(item.title)} | {_md(item.detail)} |"
        for item in report.findings
    )
    observations = "\n".join(
        f"| {item.method} | {_md(item.url)} | {item.statusCode or '-'} | {item.bodyBytes} | "
        f"{item.bodySha256 or '-'} | {_md(item.error or '')} |"
        for item in report.observations
    )
    project = "No project seed was generated because the root observation was blocked."
    if report.project:
        tests = "\n".join(
            f"- `{case.id}` [{case.type}] {_md(case.title)}" for case in report.project.initialTestCases
        )
        actions = "\n".join(f"- {_md(item)}" for item in report.project.nextActions)
        project = (
            f"- Project ID: `{report.project.id}`\n"
            f"- Browser Agent start URL: `{report.project.browserAgentStartUrl}`\n"
            f"- Test-case quality: **{report.project.caseQuality.decision}** "
            f"({report.project.caseQuality.score}/100)\n\n"
            f"### Initial test cases\n\n{tests}\n\n### Next actions\n\n{actions}"
        )
    technology = ", ".join(report.technologies) or "No deterministic hint observed"
    return (
        f"# EagleEye URL Audit — `{report.auditId}`\n\n"
        f"- Decision: **{report.decision}**\n"
        f"- Requested URL: `{report.requestedUrl}`\n"
        f"- Final URL: `{report.finalUrl or '-'}`\n"
        f"- Authorization: explicitly confirmed\n"
        f"- Localhost opt-in: `{str(report.localhostAllowed).lower()}`\n"
        f"- Started: {report.startedAt}\n"
        f"- Completed: {report.completedAt}\n\n"
        "This report contains observation-only HTTP(S) metadata. It does not perform injection, brute-force, "
        "port scanning, directory enumeration, credential submission, or destructive writes.\n\n"
        "## Findings\n\n| Status | Category | Finding | Detail |\n|---|---|---|---|\n"
        f"{finding_rows}\n\n"
        "## HTTP observations\n\n| Method | URL | Status | Bytes | SHA-256 | Error |\n"
        "|---|---|---:|---:|---|---|\n"
        f"{observations}\n\n"
        f"## Technology hints\n\n{_md(technology)}\n\n"
        f"## QA project seed\n\n{project}\n"
    )


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, PermissionError):
        return str(exc)[:500]
    if isinstance(exc, ValueError):
        return str(exc)[:500]
    return f"{exc.__class__.__name__} while observing the authorized target"


def _now() -> str:
    return datetime.now(UTC).isoformat()
