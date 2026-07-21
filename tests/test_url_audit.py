from __future__ import annotations

import http.client
import socket
import time
from pathlib import Path
from threading import BoundedSemaphore, Thread
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.url_audit import AuditBudget, PinnedHttpTransport, TransportResponse, run_url_audit
from app.url_audit_models import UrlAuditRequest
from demos.hackathon.target_app import app as hackathon_app

client = TestClient(app)


class FixtureTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def request(
        self,
        method: str,
        url: str,
        resolved_ip: str,
        headers: dict[str, str],
        max_bytes: int,
        deadline: float,
    ) -> TransportResponse:
        assert deadline > 0
        self.calls.append((method, url, resolved_ip))
        parsed = urlsplit(url)
        response_headers = {
            "content-type": "text/html; charset=utf-8",
            "content-security-policy": "default-src 'self'; nonce=do-not-persist; frame-ancestors 'none'",
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
            "permissions-policy": "camera=()",
            "server": "uvicorn/0.31 internal-detail",
        }
        body = b""
        status = 200
        if method == "OPTIONS":
            status = 204
        elif parsed.path == "/":
            body = (
                b"<html><head><link rel='icon' href='/favicon.ico'></head>"
                b"<body><a href='/login'>Sign in</a></body></html>"
            )
        elif parsed.path == "/robots.txt":
            response_headers["content-type"] = "text/plain"
            body = b"User-agent: *\nSitemap: http://127.0.0.1/sitemap.xml\n"
        elif parsed.path == "/sitemap.xml":
            response_headers["content-type"] = "application/xml"
            body = b"<urlset><url><loc>http://127.0.0.1/</loc></url></urlset>"
        elif parsed.path == "/.well-known/security.txt":
            response_headers["content-type"] = "text/plain"
            body = b"Contact: mailto:security@example.invalid\n"
        elif parsed.path == "/openapi.json":
            response_headers["content-type"] = "application/json"
            body = b'{"openapi":"3.1.0","info":{"title":"private title"},"paths":{"/health":{}}}'
        elif parsed.path == "/favicon.ico":
            response_headers["content-type"] = "image/x-icon"
            body = b"" if method == "HEAD" else b"icon"
        else:
            status = 404
        bounded = body[:max_bytes]
        return TransportResponse(
            status_code=status,
            headers=response_headers,
            body=bounded,
            truncated=len(body) > max_bytes,
            tls_version=None,
            duration_ms=1,
        )


class FailAfterRootTransport(FixtureTransport):
    def request(
        self,
        method: str,
        url: str,
        resolved_ip: str,
        headers: dict[str, str],
        max_bytes: int,
        deadline: float,
    ) -> TransportResponse:
        if len(self.calls) >= 2:
            self.calls.append((method, url, resolved_ip))
            raise OSError("fixture observation failed")
        response = super().request(method, url, resolved_ip, headers, max_bytes, deadline)
        response.headers["strict-transport-security"] = "max-age=31536000"
        return response


@pytest.fixture
def isolated_audits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("app.url_audit.URL_AUDITS", tmp_path / "url-audits")
    monkeypatch.setenv("EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST", "1")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 8767))
        ],
    )
    return tmp_path / "url-audits"


def test_url_audit_creates_masked_report_and_quality_checked_project(
    isolated_audits: Path,
) -> None:
    transport = FixtureTransport()
    report = run_url_audit(
        UrlAuditRequest(
            targetUrl="http://127.0.0.1:8767/?page=private-value",
            authorized=True,
            allowLocalhost=True,
        ),
        transport=transport,
    )

    assert report.decision == "PASS_WITH_WARNING"
    assert report.requestedUrl.endswith("?page=%5Bredacted%5D")
    assert report.project is not None
    assert report.project.caseQuality.decision == "PASS"
    assert report.project.caseQuality.score == 100
    assert {item.kind for item in report.assets if item.available} >= {
        "robots",
        "sitemap",
        "security_txt",
        "openapi",
        "favicon",
        "login_hint",
    }
    root = next(item for item in report.observations if item.id == "root-get")
    assert root.responseHeaders["content-security-policy"] == "present; frame-ancestors=yes"
    assert root.responseHeaders["server"] == "uvicorn"
    assert "nonce" not in report.model_dump_json()
    assert "private-value" not in report.model_dump_json()
    assert "private title" not in report.model_dump_json()
    assert report.reportJson.startswith("artifacts/url-audits/")
    assert not Path(report.reportJson).is_absolute()
    report_dir = isolated_audits / report.auditId
    assert (report_dir / "report.json").is_file()
    assert (report_dir / "report.md").is_file()
    assert len(transport.calls) <= 10


@pytest.mark.parametrize(
    "address",
    ["192.168.1.10", "169.254.169.254", ".".join(("0", "0", "0", "0"))],
)
def test_url_audit_never_reaches_lan_metadata_or_unspecified_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    address: str,
) -> None:
    monkeypatch.setattr("app.url_audit.URL_AUDITS", tmp_path / "audits")
    monkeypatch.setenv("EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST", "1")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 80))
        ],
    )
    transport = FixtureTransport()

    report = run_url_audit(
        UrlAuditRequest(
            targetUrl="http://internal.example/",
            authorized=True,
            allowLocalhost=True,
        ),
        transport=transport,
    )

    assert report.decision == "BLOCKED"
    assert transport.calls == []
    assert "never audited" in report.findings[0].detail


def test_localhost_requires_request_and_environment_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.url_audit.URL_AUDITS", tmp_path / "audits")
    monkeypatch.delenv("EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST", raising=False)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 8767))
        ],
    )
    report = run_url_audit(
        UrlAuditRequest(
            targetUrl="http://127.0.0.1:8767/",
            authorized=True,
            allowLocalhost=True,
        ),
        transport=FixtureTransport(),
    )

    assert report.decision == "BLOCKED"
    assert "EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST=1" in report.findings[0].detail


def test_dns_derived_loopback_is_blocked_even_with_localhost_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.url_audit.URL_AUDITS", tmp_path / "audits")
    monkeypatch.setenv("EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST", "1")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 80)),
        ],
    )
    transport = FixtureTransport()

    report = run_url_audit(
        UrlAuditRequest(
            targetUrl="http://rebind.example/",
            authorized=True,
            allowLocalhost=True,
        ),
        transport=transport,
    )

    assert report.decision == "BLOCKED"
    assert transport.calls == []
    assert "DNS-derived loopback" in report.findings[0].detail


def test_url_audit_rejects_secret_query_and_missing_authorization() -> None:
    missing_auth = client.post(
        "/api/v1/url-audits",
        json={"targetUrl": "https://example.com/", "authorized": False},
    )
    secret_query = client.post(
        "/api/v1/url-audits",
        json={"targetUrl": "https://example.com/?token=do-not-store", "authorized": True},
    )

    assert missing_auth.status_code == 422
    assert secret_query.status_code == 422
    assert "do-not-store" not in secret_query.text


def test_shared_budget_caps_requests_and_response_bytes() -> None:
    budget = AuditBudget(request_limit=2, body_limit=4)
    assert budget.before_request("GET") == 4
    budget.record_body(4)
    with pytest.raises(ValueError, match="response-byte budget"):
        budget.before_request("GET")


def test_pinned_transport_enforces_absolute_deadline_against_slow_response() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def serve_slowly() -> None:
        try:
            connection, _ = listener.accept()
            with connection:
                connection.recv(4_096)
                connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n")
                for _ in range(100):
                    try:
                        connection.sendall(b"x")
                    except OSError:
                        break
                    time.sleep(0.05)
        finally:
            listener.close()

    server = Thread(target=serve_slowly, daemon=True)
    server.start()
    started = time.monotonic()
    with pytest.raises((OSError, http.client.HTTPException)):
        PinnedHttpTransport(timeout_seconds=2).request(
            "GET",
            f"http://127.0.0.1:{port}/",
            "127.0.0.1",
            {},
            1_024,
            deadline=started + 0.25,
        )
    elapsed = time.monotonic() - started
    server.join(timeout=1)

    assert elapsed < 0.75


def test_incomplete_observations_cannot_receive_pass(
    isolated_audits: Path,
) -> None:
    report = run_url_audit(
        UrlAuditRequest(
            targetUrl="https://127.0.0.1:8767/",
            authorized=True,
            allowLocalhost=True,
        ),
        transport=FailAfterRootTransport(),
    )

    assert report.decision == "PASS_WITH_WARNING"
    assert any(item.id == "audit-incomplete" for item in report.findings)
    assert any(item.id == "cors-not-evaluated" for item in report.findings)


def test_api_rejects_a_third_concurrent_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    slots = BoundedSemaphore(2)
    assert slots.acquire(blocking=False)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr("app.url_audit._AUDIT_SLOTS", slots)
    try:
        response = client.post(
            "/api/v1/url-audits",
            json={"targetUrl": "https://example.com/", "authorized": True},
        )
    finally:
        slots.release()
        slots.release()

    assert response.status_code == 429
    assert response.json()["detail"] == "URL audit concurrency limit reached"


def test_hackathon_fixture_is_separate_from_production_routes() -> None:
    production = TestClient(app)
    fixture = TestClient(hackathon_app)

    assert production.get("/demo-site/").status_code == 404
    assert production.post("/api/v1/browser-agent/sample/local").status_code == 404
    assert fixture.get("/").status_code == 200
    assert "HACKATHON · ISOLATED · LOCAL" in fixture.get("/").text
    assert fixture.get("/openapi.json").json()["openapi"] == "3.1.0"
    assert fixture.head("/favicon.ico").status_code == 200


def test_url_audit_report_can_be_deleted(
    isolated_audits: Path,
) -> None:
    report = run_url_audit(
        UrlAuditRequest(
            targetUrl="http://127.0.0.1:8767/",
            authorized=True,
            allowLocalhost=True,
        ),
        transport=FixtureTransport(),
    )

    deleted = client.delete(f"/api/v1/url-audits/{report.auditId}")

    assert deleted.status_code == 204
    assert client.get(f"/api/v1/url-audits/{report.auditId}").status_code == 404
    assert not (isolated_audits / report.auditId).exists()
