import re

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.analyzer import analyze_failure
from app.main import app
from app.security import allowed_browser_origins, is_run_url_allowed

client = TestClient(app)


def bundle(start_url: str = "http://127.0.0.1:8767/") -> dict:
    return {
        "schemaVersion": "1.0",
        "source": "orbit-assist",
        "createdAt": "2026-07-14T00:00:00Z",
        "session": {
            "id": "demo-session",
            "name": "Registration",
            "startedAt": "2026-07-14T00:00:00Z",
            "startUrl": start_url,
            "recording": False,
            "events": [
                {"id": "1", "timestamp": 1, "action": "goto", "url": start_url, "redacted": False},
                {
                    "id": "2",
                    "timestamp": 2,
                    "action": "fill",
                    "url": start_url,
                    "target": {
                        "role": "textbox",
                        "name": "Email",
                        "selector": "#email",
                        "tagName": "input",
                    },
                    "value": "test@example.com",
                    "valueType": "email",
                    "redacted": True,
                },
                {
                    "id": "3",
                    "timestamp": 3,
                    "action": "click",
                    "url": start_url,
                    "target": {
                        "role": "button",
                        "name": "Register",
                        "selector": "button[type=submit]",
                        "tagName": "button",
                    },
                    "redacted": False,
                },
            ],
        },
        "generated": {
            "playwright": "import { test } from '@playwright/test';",
            "yaml": "name: Registration\nsteps: []\n",
        },
    }


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "1.1.0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_browser_origin_allowlist_requires_exact_configured_extension() -> None:
    extension = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef"
    origins = allowed_browser_origins(f"{extension},{extension}")
    assert origins[:2] == ["http://127.0.0.1:8766", "http://localhost:8766"]
    assert re.fullmatch(r"chrome-extension://[a-p]{32}", origins[2])
    assert origins[3:] == [extension]
    with pytest.raises(RuntimeError, match="exact chrome-extension"):
        allowed_browser_origins("chrome-extension://*")


def test_cross_origin_browser_mutation_is_rejected_before_side_effects() -> None:
    response = client.post(
        "/api/v1/auth/providers/codex-agent/start",
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Browser origin is not allowed"}


def test_ingests_orbit_bundle_and_writes_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EAGLEEYE_AUTO_PROFILE_AI", "0")
    monkeypatch.setattr(storage, "SESSIONS", tmp_path / "sessions")
    monkeypatch.setattr(storage, "GENERATED", tmp_path / "generated")
    monkeypatch.setattr("app.main.PROFILES", tmp_path / "profiles")
    response = client.post("/api/v1/sessions", json=bundle())
    assert response.status_code == 200
    assert response.json() == {
        "session_id": "demo-session",
        "event_count": 3,
        "stored": True,
        "run_allowed": True,
        "profile_id": response.json()["profile_id"],
        "recommended_mode": "development",
        "risk_score": 34,
    }
    assert response.json()["profile_id"].startswith("profile-")
    assert (tmp_path / "sessions" / "demo-session.json").exists()
    assert (tmp_path / "generated" / "demo-session.spec.ts").exists()
    stored = (tmp_path / "sessions" / "demo-session.json").read_text(encoding="utf-8")
    assert "test@example.com" not in stored
    assert '"value": null' in stored


def test_rejects_unredacted_input(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "SESSIONS", tmp_path / "sessions")
    monkeypatch.setattr(storage, "GENERATED", tmp_path / "generated")
    payload = bundle()
    payload["session"]["events"][1]["redacted"] = False
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 422
    assert "redacted" in response.json()["detail"]


def test_remote_execution_is_denied_by_default() -> None:
    assert is_run_url_allowed("http://127.0.0.1:8767/") is True
    assert is_run_url_allowed("https://example.com/") is False


def test_api_docs_are_disabled_by_default_and_security_headers_are_present() -> None:
    assert client.get("/docs").status_code == 404
    response = client.get("/health")
    assert response.headers["cache-control"] == "no-store"
    assert "object-src 'none'" in response.headers["content-security-policy"]


def test_failure_analyzer_classifies_selector_errors() -> None:
    result = analyze_failure("Locator button[name=Register] not found")
    assert result.category == "SELECTOR_CHANGED"
    assert "accessible role" in result.recommended_action


def test_profile_api_generates_and_stores_strategy(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.PROFILES", tmp_path / "profiles")
    response = client.post(
        "/api/v1/test-profiles/generate",
        json={
            "projectId": "agent",
            "developmentStage": "development",
            "serviceType": "ai_agent",
            "changedFiles": ["src/auth.py"],
            "aiEnabled": False,
            "risk": {
                "business_impact": "high",
                "data_sensitivity": "high",
                "change_complexity": "medium",
                "user_impact": "high",
                "recoverability": "low",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommendedMode"] == "strict"
    assert body["fullRegressionRequired"] is True
    assert (tmp_path / "profiles" / f"{body['id']}.json").exists()


def test_emulator_cycle_profile_api(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.PROFILES", tmp_path / "profiles")
    response = client.post(
        "/api/v1/test-profiles/generate",
        json={
            "projectId": "vr4300",
            "developmentStage": "integration",
            "serviceType": "emulator",
            "compatibilityLevel": "cycle",
            "changedFiles": ["src/vr4300_cache.cpp"],
            "aiEnabled": False,
            "risk": {
                "business_impact": "critical",
                "data_sensitivity": "low",
                "change_complexity": "critical",
                "user_impact": "high",
                "recoverability": "low",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["compatibilityLevel"] == "cycle"
    assert body["recommendedMode"] == "release_gate"
    assert "cache-timing" in body["requiredTests"]
    assert "llm-schema" not in body["requiredTests"]


def test_profile_api_rejects_emulator_compatibility_for_web(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.PROFILES", tmp_path / "profiles")
    response = client.post(
        "/api/v1/test-profiles/generate",
        json={
            "projectId": "web-client",
            "developmentStage": "development",
            "serviceType": "web",
            "compatibilityLevel": "functional",
            "aiEnabled": False,
        },
    )
    assert response.status_code == 422
    assert "serviceType=emulator" in response.text


def test_quality_gate_api() -> None:
    response = client.post(
        "/api/v1/quality-gates/evaluate",
        json={
            "profileId": "profile-test",
            "mode": "standard",
            "serviceType": "web",
            "results": [
                {"testId": "one", "testType": "unit", "status": "PASSED"},
                {"testId": "two", "testType": "api", "status": "PASSED"},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "PASS"


def test_anthropic_refresh_reports_configuration_gate(monkeypatch) -> None:
    for name in (
        "ANTHROPIC_FEDERATION_RULE_ID",
        "ANTHROPIC_ORGANIZATION_ID",
        "ANTHROPIC_SERVICE_ACCOUNT_ID",
        "ANTHROPIC_IDENTITY_TOKEN",
        "ANTHROPIC_IDENTITY_TOKEN_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    response = client.post("/api/v1/auth/providers/anthropic/refresh")
    assert response.status_code == 409
    assert "not configured" in response.json()["detail"]


def test_test_case_check_api() -> None:
    response = client.post(
        "/api/v1/test-cases/check",
        json={
            "projectId": "api-test",
            "cases": [
                {
                    "id": "TC-1",
                    "title": "API healthを確認する",
                    "type": "api",
                    "steps": ["GET /health を送信する"],
                    "expectedResults": ["HTTP 200とstatus=okが返る"],
                    "assertions": ["status_code == 200", "body.status == ok"],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "PASS"
