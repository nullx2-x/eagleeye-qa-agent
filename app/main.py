import hashlib
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .ai_advisor import advisor
from .browser_agent_api import router as browser_agent_router
from .configuration import configuration
from .dashboard import dashboard_html
from .demo_site import demo_site_html
from .desktop_adapter import (
    DesktopTargetValidationError,
    UnknownDesktopTargetError,
    load_desktop_registry,
    run_desktop_target,
)
from .desktop_models import DesktopRunRequest, DesktopRunResult
from .guided_api import router as guided_router
from .live_ui import live_css, live_html, live_js
from .model_recommendations import ModelRecommendationCatalog, Workload, catalog
from .models import CodexHandoff, EagleEyeBundle, RunResult, SessionReceipt
from .providers import ApiKeyInput, OAuthStartResponse, ProviderStatus, broker
from .quality import evaluate_quality_gate
from .repair_models import RepairRequest, RepairResponse
from .repair_service import (
    FailedSessionRepairRequest,
    FailedSessionRepairResponse,
    RepairEvaluationResponse,
    RepairServiceStatus,
    repair_service,
)
from .runner import run_bundle
from .security import allowed_browser_origins, is_run_url_allowed, validate_privacy
from .storage import RUNS, load_bundle, load_run, safe_id, save_bundle, save_run
from .strategy import generate_profile, load_profile, save_profile
from .strategy_models import ProfileRequest, ProfileResponse, QualityGateRequest, QualityGateResponse
from .test_case_checker import check_test_cases
from .test_case_models import TestCaseCheckRequest, TestCaseCheckResponse

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "data" / "profiles"

api_docs_enabled = os.getenv("EAGLEEYE_ENABLE_API_DOCS", "0") == "1"
app = FastAPI(
    title="EagleEye AI QA Agent",
    version="1.0.0",
    docs_url="/docs" if api_docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if api_docs_enabled else None,
)
browser_origins = allowed_browser_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=browser_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost", "testserver"],
)
app.include_router(guided_router)
app.include_router(browser_agent_router)


@app.middleware("http")
async def enforce_browser_boundary(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Reject cross-origin browser mutations and attach local dashboard hardening headers."""

    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in browser_origins:
        return JSONResponse(status_code=403, content={"detail": "Browser origin is not allowed"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if "Content-Security-Policy" not in response.headers:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
    if "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "eagleeye-qa-agent",
        "version": "1.0.0",
        "mcp": "http://127.0.0.1:8768/mcp",
        "aiFirst": True,
    }


@app.get("/demo-site/", response_class=HTMLResponse)
def bundled_demo_site() -> HTMLResponse:
    policy = (
        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    )
    return HTMLResponse(
        demo_site_html(sample_page=False),
        headers={"Content-Security-Policy": policy, "Cache-Control": "no-store"},
    )


@app.get("/api/v1/configuration")
def get_configuration() -> dict:
    return configuration.model_dump(mode="json")


@app.post("/api/v1/test-profiles/generate", response_model=ProfileResponse)
def create_test_profile(request: ProfileRequest) -> ProfileResponse:
    profile = advisor.augment(request, generate_profile(request))
    save_profile(profile, PROFILES)
    return profile


@app.get("/api/v1/test-profiles/{profile_id}", response_model=ProfileResponse)
def get_test_profile(profile_id: str) -> ProfileResponse:
    try:
        return load_profile(profile_id, PROFILES)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Profile not found") from exc


@app.post("/api/v1/quality-gates/evaluate", response_model=QualityGateResponse)
def quality_gate(request: QualityGateRequest) -> QualityGateResponse:
    return evaluate_quality_gate(request)


@app.post("/api/v1/test-cases/check", response_model=TestCaseCheckResponse)
def test_case_check(request: TestCaseCheckRequest) -> TestCaseCheckResponse:
    return check_test_cases(request)


@app.get("/api/v1/ai/providers", response_model=list[ProviderStatus])
def ai_providers() -> list[ProviderStatus]:
    return broker.list_statuses()


@app.get(
    "/api/v1/ai/model-recommendations",
    response_model=ModelRecommendationCatalog,
)
def ai_model_recommendations(
    workload: Workload | None = None,
    provider_id: str | None = Query(default=None, max_length=64),
) -> ModelRecommendationCatalog:
    return catalog(workload, provider_id)


@app.post("/api/v1/auth/providers/{provider_id}/start", response_model=OAuthStartResponse)
def start_provider_oauth(provider_id: str) -> OAuthStartResponse:
    try:
        return broker.start(provider_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/auth/callback/{provider_id}", response_model=ProviderStatus)
def provider_oauth_callback(
    provider_id: str,
    code: str = Query(min_length=1, max_length=4_000),
    state: str = Query(min_length=16, max_length=200),
) -> ProviderStatus:
    try:
        return broker.complete_pkce(provider_id, state, code, state)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/auth/providers/{provider_id}/device/{flow_id}", response_model=ProviderStatus)
def complete_provider_device(provider_id: str, flow_id: str) -> ProviderStatus:
    try:
        return broker.complete_device(provider_id, flow_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=202, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/auth/providers/{provider_id}/cancel/{flow_id}")
def cancel_provider_login(provider_id: str, flow_id: str) -> dict:
    try:
        broker.cancel(provider_id, flow_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"cancelled": True, "providerId": provider_id, "flowId": flow_id}


@app.post("/api/v1/auth/providers/{provider_id}/refresh", response_model=ProviderStatus)
def refresh_provider_workload_identity(provider_id: str) -> ProviderStatus:
    try:
        return broker.refresh_workload_identity(provider_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Provider token exchange failed.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/auth/providers/{provider_id}/api-key", response_model=ProviderStatus)
def save_provider_api_key(provider_id: str, value: ApiKeyInput) -> ProviderStatus:
    try:
        return broker.store_api_key(provider_id, value.apiKey.get_secret_value())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/v1/auth/providers/{provider_id}")
def disconnect_provider(provider_id: str) -> dict:
    try:
        broker.disconnect(provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"disconnected": True, "providerId": provider_id}


@app.get("/api/v1/desktop-targets")
def desktop_targets() -> dict:
    try:
        registry = load_desktop_registry()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Desktop target registry is unavailable.") from exc
    return {"version": registry.version, "targets": sorted(registry.targets)}


@app.post("/api/v1/desktop-runs", response_model=DesktopRunResult)
def run_desktop(request: DesktopRunRequest) -> DesktopRunResult:
    try:
        return run_desktop_target(request)
    except UnknownDesktopTargetError as exc:
        raise HTTPException(status_code=404, detail="Desktop target not found.") from exc
    except DesktopTargetValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/self-repair/status", response_model=RepairServiceStatus)
def self_repair_status() -> RepairServiceStatus:
    return repair_service.status()


@app.post("/api/v1/self-repair/evaluate", response_model=RepairEvaluationResponse)
def evaluate_self_repair(request: RepairRequest) -> RepairEvaluationResponse:
    return repair_service.evaluate(request)


@app.post("/api/v1/self-repair/execute", response_model=RepairResponse)
def execute_self_repair(request: RepairRequest) -> RepairResponse:
    return repair_service.execute(request)


@app.post("/api/v1/sessions", response_model=SessionReceipt)
def ingest_session(bundle: EagleEyeBundle) -> SessionReceipt:
    try:
        validate_privacy(bundle)
        save_bundle(bundle)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    profile_request = ProfileRequest.model_validate(
        {
            "projectId": f"orbit-{safe_id(bundle.session.id)}",
            "developmentStage": "development",
            "serviceType": "web",
            "environment": "local" if is_run_url_allowed(str(bundle.session.startUrl)) else "remote",
            "changedFiles": [],
            "aiEnabled": os.getenv("EAGLEEYE_AUTO_PROFILE_AI", "1") == "1",
            "risk": {
                "business_impact": "medium",
                "data_sensitivity": "medium",
                "change_complexity": "high" if len(bundle.session.events) > 20 else "medium",
                "user_impact": "medium",
                "recoverability": "high",
            },
        }
    )
    profile = advisor.augment(profile_request, generate_profile(profile_request))
    save_profile(profile, PROFILES)
    return SessionReceipt(
        session_id=bundle.session.id,
        event_count=len(bundle.session.events),
        stored=True,
        run_allowed=is_run_url_allowed(str(bundle.session.startUrl)),
        profile_id=profile.id,
        recommended_mode=profile.recommendedMode.value,
        risk_score=profile.riskScore,
    )


@app.get("/api/v1/sessions/{session_id}", response_model=EagleEyeBundle)
def get_session(session_id: str) -> EagleEyeBundle:
    try:
        return load_bundle(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.post("/api/v1/sessions/{session_id}/run", response_model=RunResult)
def run_session(session_id: str) -> RunResult:
    try:
        bundle = load_bundle(session_id)
        result = run_bundle(bundle)
        save_run(result)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post(
    "/api/v1/sessions/{session_id}/self-repair",
    response_model=FailedSessionRepairResponse,
)
def self_repair_failed_session(
    session_id: str,
    request: FailedSessionRepairRequest,
) -> FailedSessionRepairResponse:
    try:
        result = load_run(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Run result not found") from exc
    if result.status != "failed" or not result.error:
        raise HTTPException(status_code=409, detail="Self-repair starts only from a failed run")
    fingerprint_document = {
        "sessionId": result.session_id,
        "error": result.error,
        "evidence": [item.sha256 for item in result.evidence],
    }

    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    repair_request = RepairRequest(
        projectId=request.projectId,
        environment="local",
        production=False,
        provider=request.provider,
        model=request.model,
        requestedMode="apply" if request.autoApply else "proposal_only",
        explicitApplyRequested=request.autoApply,
        failureFingerprint=fingerprint,
        failureSummary=result.error,
        evidencePaths=[item.path for item in result.evidence],
    )
    evaluation = repair_service.evaluate(repair_request)
    if request.autoApply and evaluation.eligible and evaluation.attestation is not None:
        repair_request = repair_request.model_copy(update={"attestation": evaluation.attestation})
        repair = repair_service.execute(repair_request)
    else:
        repair = None
    return FailedSessionRepairResponse(evaluation=evaluation, repair=repair)


@app.get("/api/v1/sessions/{session_id}/codex-handoff", response_model=CodexHandoff)
def codex_handoff(session_id: str) -> CodexHandoff:
    try:
        result = load_run(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Run result not found") from exc
    if result.status != "failed" or not result.analysis:
        raise HTTPException(status_code=409, detail="Codex handoff is available only for a failed run")
    run_dir = RUNS / safe_id(session_id)
    evidence = [value for value in [result.error, result.screenshot, str(run_dir / "result.json")] if value]
    return CodexHandoff(
        session_id=session_id,
        failure=result.analysis,
        evidence=evidence,
        instructions=[
            "Inspect only the repository path explicitly approved by the user.",
            "Propose a patch and added regression test; do not apply it without approval.",
            "Re-run the generated test after approval and report before/after evidence.",
        ],
    )


@app.get("/", response_class=HTMLResponse)
def live_dashboard() -> HTMLResponse:
    policy = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return HTMLResponse(live_html(), headers={"Content-Security-Policy": policy})


@app.get("/assets/live.css", response_class=Response)
def live_styles() -> Response:
    return Response(
        live_css(),
        media_type="text/css; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/assets/live.js", response_class=Response)
def live_script() -> Response:
    return Response(
        live_js(),
        media_type="text/javascript; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/workspace", response_class=HTMLResponse)
def workspace_dashboard() -> str:
    """Retain the full engineering workspace under a stable secondary route."""

    return dashboard_html()
