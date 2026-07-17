import base64
import hashlib
import json
import os
import secrets
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, urlparse
from uuid import uuid4

import httpx
import keyring
from pydantic import BaseModel, Field, SecretStr

AuthMode = Literal[
    "none",
    "api_key",
    "oauth_pkce",
    "oauth_device",
    "workload_identity_federation",
    "default_azure_credential",
    "external_session",
    "managed_oauth",
]


class ProviderDefinition(BaseModel):
    id: str
    name: str
    protocol: str
    authModes: list[AuthMode]
    oauthSupported: bool
    oauthKind: str | None = None
    notes: str


class ProviderStatus(BaseModel):
    provider: ProviderDefinition
    connected: bool
    configured: bool
    credentialKind: str | None = None
    expiresAt: int | None = None


class OAuthStartResponse(BaseModel):
    providerId: str
    flowId: str
    authorizationUrl: str | None = None
    verificationUri: str | None = None
    userCode: str | None = None
    expiresIn: int = 600


class ApiKeyInput(BaseModel):
    apiKey: SecretStr = Field(min_length=8, max_length=20_000)


PROVIDERS = {
    "openai": ProviderDefinition(
        id="openai",
        name="OpenAI API",
        protocol="openai-responses",
        authModes=["api_key"],
        oauthSupported=False,
        notes="OpenAI APIは公式APIキー認証。MCP利用者OAuthとは別の認証境界です。",
    ),
    "codex-agent": ProviderDefinition(
        id="codex-agent",
        name="Codex App Server (ChatGPT)",
        protocol="codex-app-server",
        authModes=["managed_oauth", "external_session"],
        oauthSupported=True,
        oauthKind="chatgpt_managed",
        notes=(
            "Codex App ServerがChatGPT OAuthを管理します。EagleEyeはtokenを受領・保存せず、"
            "非秘密の接続状態だけを参照します。"
        ),
    ),
    "anthropic": ProviderDefinition(
        id="anthropic",
        name="Anthropic Claude API",
        protocol="anthropic-messages",
        authModes=["api_key", "workload_identity_federation"],
        oauthSupported=True,
        oauthKind="workload_identity_federation",
        notes="APIキーまたは短期Bearer tokenを発行するWorkload Identity Federationに対応します。",
    ),
    "google-gemini": ProviderDefinition(
        id="google-gemini",
        name="Google Gemini",
        protocol="gemini",
        authModes=["oauth_pkce", "api_key"],
        oauthSupported=True,
        oauthKind="authorization_code_pkce",
        notes="Google OAuthデスクトップクライアントとPKCEを使用します。",
    ),
    "azure-openai": ProviderDefinition(
        id="azure-openai",
        name="Azure OpenAI",
        protocol="openai-compatible",
        authModes=["oauth_pkce", "default_azure_credential", "api_key"],
        oauthSupported=True,
        oauthKind="microsoft_entra",
        notes="Microsoft Entra IDとAzure Identityによるキーレス認証を優先します。",
    ),
    "github-models": ProviderDefinition(
        id="github-models",
        name="GitHub Models",
        protocol="openai-compatible",
        authModes=["oauth_device", "api_key"],
        oauthSupported=True,
        oauthKind="device_authorization",
        notes="ヘッドレス環境向けGitHub OAuth Device Flowに対応します。",
    ),
    "ollama": ProviderDefinition(
        id="ollama",
        name="Ollama",
        protocol="ollama-chat",
        authModes=["none"],
        oauthSupported=False,
        notes="ローカル接続。既定では認証を必要としません。",
    ),
    "lm-studio": ProviderDefinition(
        id="lm-studio",
        name="LM Studio",
        protocol="openai-compatible",
        authModes=["none", "api_key"],
        oauthSupported=False,
        notes="ローカルOpenAI互換接続。サーバー設定に応じてAPIキーを使用します。",
    ),
}


@dataclass
class PendingFlow:
    provider_id: str
    created_at: float
    client_id: str
    token_url: str
    redirect_uri: str
    verifier: str | None = None
    device_code: str | None = None
    interval: int = 5


class CredentialVault:
    service = "eagleeye-qa-agent"

    def put(self, provider_id: str, payload: dict) -> None:
        keyring.set_password(self.service, provider_id, json.dumps(payload))

    def get(self, provider_id: str) -> dict | None:
        value = keyring.get_password(self.service, provider_id)
        return json.loads(value) if value else None

    def delete(self, provider_id: str) -> None:
        try:
            keyring.delete_password(self.service, provider_id)
        except keyring.errors.PasswordDeleteError:
            return


class OAuthBroker:
    def __init__(self, vault: CredentialVault | None = None) -> None:
        self.vault = vault or CredentialVault()
        self.pending: dict[str, PendingFlow] = {}

    def list_statuses(self) -> list[ProviderStatus]:
        statuses = []
        for definition in PROVIDERS.values():
            if definition.id == "codex-agent":
                connected, auth_mode = self._codex_status()
                statuses.append(
                    ProviderStatus(
                        provider=definition,
                        connected=connected,
                        configured=shutil.which(os.getenv("EAGLEEYE_CODEX_COMMAND", "codex")) is not None,
                        credentialKind=f"app_server_{auth_mode}" if connected and auth_mode else None,
                    )
                )
                continue
            credential = self.vault.get(definition.id)
            local_available = self._local_available(definition.id)
            configured = credential is not None or local_available or self._is_configured(definition.id)
            expired = bool(credential and credential.get("expires_at", 2**63) <= int(time.time()))
            statuses.append(
                ProviderStatus(
                    provider=definition,
                    connected=(credential is not None and not expired) or local_available,
                    configured=configured,
                    credentialKind=credential.get("kind") if credential else None,
                    expiresAt=credential.get("expires_at") if credential else None,
                )
            )
        return statuses

    def store_api_key(self, provider_id: str, api_key: str) -> ProviderStatus:
        definition = _provider(provider_id)
        if "api_key" not in definition.authModes:
            raise ValueError("This provider does not accept API-key credentials.")
        self.vault.put(provider_id, {"kind": "api_key", "api_key": api_key, "stored_at": int(time.time())})
        return next(status for status in self.list_statuses() if status.provider.id == provider_id)

    def start(self, provider_id: str) -> OAuthStartResponse:
        definition = _provider(provider_id)
        if not definition.oauthSupported:
            raise ValueError(f"{definition.name} does not expose an end-user OAuth flow for this API.")
        if provider_id == "github-models":
            return self._start_github_device()
        if provider_id == "codex-agent":
            from .codex_agent import start_codex_login

            login = start_codex_login()
            return OAuthStartResponse(
                providerId=provider_id,
                flowId=login.login_id,
                authorizationUrl=login.auth_url,
                expiresIn=600,
            )
        if provider_id == "anthropic":
            raise ValueError(
                "Anthropic WIF is a workload exchange, not an end-user login. "
                "Configure the trust rule and call the provider refresh endpoint."
            )
        return self._start_pkce(provider_id)

    def refresh_workload_identity(self, provider_id: str) -> ProviderStatus:
        """Exchange a platform-issued OIDC JWT for a short-lived provider token."""
        if provider_id != "anthropic":
            raise ValueError("Workload identity refresh is only supported for Anthropic.")
        required = {
            "federation_rule_id": os.getenv("ANTHROPIC_FEDERATION_RULE_ID", ""),
            "organization_id": os.getenv("ANTHROPIC_ORGANIZATION_ID", ""),
            "service_account_id": os.getenv("ANTHROPIC_SERVICE_ACCOUNT_ID", ""),
        }
        missing = [name for name, value in required.items() if not value]
        assertion = os.getenv("ANTHROPIC_IDENTITY_TOKEN", "")
        token_file = os.getenv("ANTHROPIC_IDENTITY_TOKEN_FILE", "")
        if not assertion and token_file:
            path = Path(token_file).expanduser().resolve()
            if not path.is_file() or path.stat().st_size > 16_384:
                raise ValueError("Anthropic identity token file is missing or exceeds 16 KiB.")
            assertion = path.read_text(encoding="utf-8").strip()
        if not assertion:
            missing.append("identity_token")
        if missing:
            raise ValueError("Anthropic WIF is not configured: " + ", ".join(missing))
        if len(assertion.encode()) > 16_384:
            raise ValueError("Anthropic identity token exceeds 16 KiB.")
        payload = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
            **required,
        }
        workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID", "")
        if workspace_id:
            payload["workspace_id"] = workspace_id
        response = httpx.post(
            "https://api.anthropic.com/v1/oauth/token",
            json=payload,
            headers={"Accept": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        self._store_token(provider_id, response.json(), "workload_identity_federation")
        return next(status for status in self.list_statuses() if status.provider.id == provider_id)

    def complete_pkce(self, provider_id: str, flow_id: str, code: str, state: str) -> ProviderStatus:
        if flow_id != state:
            raise ValueError("OAuth state mismatch.")
        flow = self._take_flow(flow_id, provider_id)
        if not flow.verifier:
            raise ValueError("The OAuth flow is not a PKCE flow.")
        response = httpx.post(
            flow.token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": flow.client_id,
                "code": code,
                "redirect_uri": flow.redirect_uri,
                "code_verifier": flow.verifier,
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        self._store_token(provider_id, response.json(), "oauth_pkce")
        return next(status for status in self.list_statuses() if status.provider.id == provider_id)

    def complete_device(self, provider_id: str, flow_id: str) -> ProviderStatus:
        flow = self._get_flow(flow_id, provider_id)
        if provider_id != "github-models" or not flow.device_code:
            raise ValueError("The OAuth flow is not a GitHub device flow.")
        response = httpx.post(
            flow.token_url,
            data={
                "client_id": flow.client_id,
                "device_code": flow.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        self.pending.pop(flow_id, None)
        self._store_token(provider_id, payload, "oauth_device")
        return next(status for status in self.list_statuses() if status.provider.id == provider_id)

    def disconnect(self, provider_id: str) -> None:
        _provider(provider_id)
        if provider_id == "codex-agent":
            from .codex_agent import logout_codex

            logout_codex()
            return
        self.vault.delete(provider_id)

    def cancel(self, provider_id: str, flow_id: str) -> None:
        _provider(provider_id)
        if provider_id != "codex-agent":
            raise ValueError("Login cancellation is available only for Codex App Server.")
        from .codex_agent import cancel_codex_login

        cancel_codex_login(flow_id)

    def _start_pkce(self, provider_id: str) -> OAuthStartResponse:
        if provider_id == "google-gemini":
            client_id = os.getenv("EAGLEEYE_GOOGLE_CLIENT_ID", "")
            authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
            token_url = "https://oauth2.googleapis.com/token"  # noqa: S105 -- endpoint, not a token
            scopes = "openid email https://www.googleapis.com/auth/generative-language.retriever"
        elif provider_id == "azure-openai":
            client_id = os.getenv("EAGLEEYE_ENTRA_CLIENT_ID", "")
            tenant = os.getenv("EAGLEEYE_ENTRA_TENANT", "common")
            authorize_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
            token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
            scopes = "openid profile offline_access https://cognitiveservices.azure.com/.default"
        else:
            raise ValueError("Unsupported PKCE provider.")
        if not client_id:
            raise ValueError(f"OAuth client ID is not configured for {provider_id}.")
        _require_https(authorize_url)
        _require_https(token_url)
        flow_id = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        redirect_uri = f"http://127.0.0.1:8766/api/v1/auth/callback/{provider_id}"
        self.pending[flow_id] = PendingFlow(
            provider_id=provider_id,
            created_at=time.time(),
            client_id=client_id,
            token_url=token_url,
            redirect_uri=redirect_uri,
            verifier=verifier,
        )
        query = urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": scopes,
                "state": flow_id,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "access_type": "offline",
                "prompt": "consent",
            }
        )
        return OAuthStartResponse(
            providerId=provider_id,
            flowId=flow_id,
            authorizationUrl=f"{authorize_url}?{query}",
        )

    def _start_github_device(self) -> OAuthStartResponse:
        client_id = os.getenv("EAGLEEYE_GITHUB_CLIENT_ID", "")
        if not client_id:
            raise ValueError("OAuth client ID is not configured for github-models.")
        response = httpx.post(
            "https://github.com/login/device/code",
            data={"client_id": client_id, "scope": "read:user models:read"},
            headers={"Accept": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        flow_id = uuid4().hex
        self.pending[flow_id] = PendingFlow(
            provider_id="github-models",
            created_at=time.time(),
            client_id=client_id,
            token_url="https://github.com/login/oauth/access_token",  # noqa: S106 -- endpoint
            redirect_uri="",
            device_code=payload["device_code"],
            interval=int(payload.get("interval", 5)),
        )
        return OAuthStartResponse(
            providerId="github-models",
            flowId=flow_id,
            verificationUri=payload["verification_uri"],
            userCode=payload["user_code"],
            expiresIn=int(payload.get("expires_in", 900)),
        )

    def _store_token(self, provider_id: str, payload: dict, kind: str) -> None:
        expires_in = int(payload.get("expires_in", 3_600))
        self.vault.put(
            provider_id,
            {
                "kind": kind,
                "access_token": payload["access_token"],
                "refresh_token": payload.get("refresh_token"),
                "token_type": payload.get("token_type", "Bearer"),
                "scope": payload.get("scope"),
                "expires_at": int(time.time()) + expires_in,
            },
        )

    def _get_flow(self, flow_id: str, provider_id: str) -> PendingFlow:
        flow = self.pending.get(flow_id)
        if not flow or flow.provider_id != provider_id:
            raise ValueError("Unknown OAuth flow.")
        if time.time() - flow.created_at > 900:
            self.pending.pop(flow_id, None)
            raise ValueError("OAuth flow expired.")
        return flow

    def _take_flow(self, flow_id: str, provider_id: str) -> PendingFlow:
        flow = self._get_flow(flow_id, provider_id)
        self.pending.pop(flow_id, None)
        return flow

    @staticmethod
    def _is_configured(provider_id: str) -> bool:
        env_by_provider = {
            "google-gemini": "EAGLEEYE_GOOGLE_CLIENT_ID",
            "azure-openai": "EAGLEEYE_ENTRA_CLIENT_ID",
            "github-models": "EAGLEEYE_GITHUB_CLIENT_ID",
        }
        if provider_id == "anthropic":
            required = (
                "ANTHROPIC_FEDERATION_RULE_ID",
                "ANTHROPIC_ORGANIZATION_ID",
                "ANTHROPIC_SERVICE_ACCOUNT_ID",
            )
            has_identity = bool(
                os.getenv("ANTHROPIC_IDENTITY_TOKEN") or os.getenv("ANTHROPIC_IDENTITY_TOKEN_FILE")
            )
            return all(os.getenv(name) for name in required) and has_identity
        return bool(os.getenv(env_by_provider.get(provider_id, "")))

    @staticmethod
    def _local_available(provider_id: str) -> bool:
        if provider_id == "codex-agent":
            from .codex_agent import codex_available

            return codex_available()
        endpoints = {
            "ollama": os.getenv("EAGLEEYE_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/tags",
            "lm-studio": os.getenv("EAGLEEYE_LM_STUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
            + "/models",
        }
        endpoint = endpoints.get(provider_id)
        if not endpoint:
            return False
        try:
            return httpx.get(endpoint, timeout=0.5).is_success
        except httpx.HTTPError:
            return False

    @staticmethod
    def _codex_status() -> tuple[bool, str | None]:
        try:
            from .codex_agent import codex_account

            account = codex_account()
            return account.connected, account.auth_mode
        except RuntimeError:
            return False, None


def _provider(provider_id: str) -> ProviderDefinition:
    try:
        return PROVIDERS[provider_id]
    except KeyError as exc:
        raise ValueError("Unknown AI provider.") from exc


def _require_https(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("OAuth endpoints must use HTTPS.")


broker = OAuthBroker()
