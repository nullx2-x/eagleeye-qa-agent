import time
from types import SimpleNamespace

import pytest

from app.providers import OAuthBroker, PendingFlow


@pytest.fixture(autouse=True)
def no_live_codex_status(monkeypatch) -> None:
    monkeypatch.setattr(OAuthBroker, "_codex_status", staticmethod(lambda: (False, None)))


class MemoryVault:
    def __init__(self) -> None:
        self.values: dict[str, dict] = {}

    def put(self, provider_id: str, payload: dict) -> None:
        self.values[provider_id] = payload

    def get(self, provider_id: str) -> dict | None:
        return self.values.get(provider_id)

    def delete(self, provider_id: str) -> None:
        self.values.pop(provider_id, None)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_openai_does_not_claim_unsupported_user_oauth() -> None:
    broker = OAuthBroker(vault=MemoryVault())
    with pytest.raises(ValueError, match="does not expose"):
        broker.start("openai")


def test_codex_chatgpt_login_is_delegated_to_app_server(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codex_agent.start_codex_login",
        lambda: SimpleNamespace(
            login_id="login-safe-1234",
            auth_url="https://auth.openai.com/oauth/authorize?state=opaque",
        ),
    )
    result = OAuthBroker(vault=MemoryVault()).start("codex-agent")

    assert result.providerId == "codex-agent"
    assert result.flowId == "login-safe-1234"
    assert result.authorizationUrl.startswith("https://auth.openai.com/")
    assert "token" not in result.model_dump_json().casefold()


def test_google_pkce_url_has_state_and_s256(monkeypatch) -> None:
    monkeypatch.setenv("EAGLEEYE_GOOGLE_CLIENT_ID", "google-client")
    broker = OAuthBroker(vault=MemoryVault())
    result = broker.start("google-gemini")
    assert "code_challenge_method=S256" in result.authorizationUrl
    assert f"state={result.flowId}" in result.authorizationUrl
    assert broker.pending[result.flowId].verifier


def test_pkce_callback_stores_token_without_exposing_it(monkeypatch) -> None:
    vault = MemoryVault()
    broker = OAuthBroker(vault=vault)
    broker.pending["safe-state"] = PendingFlow(
        provider_id="google-gemini",
        created_at=time.time(),
        client_id="client",
        token_url="https://oauth2.googleapis.com/token",  # noqa: S106 -- endpoint
        redirect_uri="http://127.0.0.1/callback",
        verifier="verifier",
    )
    monkeypatch.setattr(
        "app.providers.httpx.post",
        lambda *args, **kwargs: FakeResponse(
            {"access_token": "secret-access", "refresh_token": "secret-refresh", "expires_in": 3600}
        ),
    )
    status = broker.complete_pkce("google-gemini", "safe-state", "code", "safe-state")
    assert status.connected is True
    assert "secret" not in status.model_dump_json()
    assert vault.values["google-gemini"]["access_token"] == "secret-access"  # noqa: S105


def test_github_device_flow_does_not_return_device_code(monkeypatch) -> None:
    monkeypatch.setenv("EAGLEEYE_GITHUB_CLIENT_ID", "github-client")
    monkeypatch.setattr(
        "app.providers.httpx.post",
        lambda *args, **kwargs: FakeResponse(
            {
                "device_code": "private-device-code",
                "user_code": "ABCD-EFGH",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            }
        ),
    )
    broker = OAuthBroker(vault=MemoryVault())
    result = broker.start("github-models")
    assert result.userCode == "ABCD-EFGH"
    assert "private-device-code" not in result.model_dump_json()


def test_api_key_is_stored_in_vault_only() -> None:
    vault = MemoryVault()
    broker = OAuthBroker(vault=vault)
    status = broker.store_api_key("openai", "sk-test-value-not-real")
    assert status.connected is True
    assert "sk-test" not in status.model_dump_json()
    assert vault.values["openai"]["kind"] == "api_key"


def test_anthropic_wif_exchanges_oidc_token_without_exposing_it(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_FEDERATION_RULE_ID", "fdrl_test")
    monkeypatch.setenv("ANTHROPIC_ORGANIZATION_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("ANTHROPIC_SERVICE_ACCOUNT_ID", "svac_test")
    monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN", "header.payload.signature")
    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs["json"])
        return FakeResponse({"access_token": "short-lived-secret", "expires_in": 600})

    monkeypatch.setattr("app.providers.httpx.post", fake_post)
    vault = MemoryVault()
    broker = OAuthBroker(vault=vault)
    status = broker.refresh_workload_identity("anthropic")
    assert status.connected is True
    assert status.credentialKind == "workload_identity_federation"
    assert captured["grant_type"].endswith("jwt-bearer")
    assert captured["assertion"] == "header.payload.signature"
    assert "short-lived-secret" not in status.model_dump_json()


def test_anthropic_wif_requires_complete_configuration(monkeypatch) -> None:
    for name in (
        "ANTHROPIC_FEDERATION_RULE_ID",
        "ANTHROPIC_ORGANIZATION_ID",
        "ANTHROPIC_SERVICE_ACCOUNT_ID",
        "ANTHROPIC_IDENTITY_TOKEN",
        "ANTHROPIC_IDENTITY_TOKEN_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="not configured"):
        OAuthBroker(vault=MemoryVault()).refresh_workload_identity("anthropic")
