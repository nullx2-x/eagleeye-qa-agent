from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse

from .browser_agent import (
    agent_status,
    append_observation,
    bug_report_markdown,
    create_local_sample,
    create_session,
    delete_session,
    generate_session,
    list_sessions,
    load_session,
    report_html,
    run_session,
    screenshot_bytes,
)
from .browser_agent_models import (
    BrowserAgentSession,
    BrowserAgentStatus,
    BrowserObservation,
    BrowserSessionCreate,
    BrowserSessionList,
)
from .demo_site import demo_site_html

router = APIRouter()
browser_router = APIRouter(prefix="/api/v1/browser-agent", tags=["browser-agent"])


@browser_router.get("/status", response_model=BrowserAgentStatus)
def status() -> BrowserAgentStatus:
    return agent_status()


@browser_router.get("/sessions", response_model=BrowserSessionList)
def sessions() -> BrowserSessionList:
    return list_sessions()


@browser_router.post("/sessions", response_model=BrowserAgentSession)
def start_session(request: BrowserSessionCreate) -> BrowserAgentSession:
    return create_session(request)


@browser_router.get("/sessions/{session_id}", response_model=BrowserAgentSession)
def session(session_id: str) -> BrowserAgentSession:
    try:
        return load_session(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Browser session not found.") from exc


@browser_router.delete("/sessions/{session_id}", status_code=204)
def remove_session(session_id: str) -> Response:
    try:
        delete_session(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Browser session not found.") from exc
    return Response(status_code=204)


@browser_router.post("/sessions/{session_id}/observations", response_model=BrowserAgentSession)
def observe(session_id: str, observation: BrowserObservation) -> BrowserAgentSession:
    try:
        return append_observation(session_id, observation)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Browser session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@browser_router.post("/sessions/{session_id}/generate", response_model=BrowserAgentSession)
def generate(session_id: str) -> BrowserAgentSession:
    try:
        return generate_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Browser session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@browser_router.post("/sessions/{session_id}/run", response_model=BrowserAgentSession)
def run(session_id: str) -> BrowserAgentSession:
    try:
        return run_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Browser session not found.") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@browser_router.post("/sample/local", response_model=BrowserAgentSession)
def local_sample() -> BrowserAgentSession:
    try:
        return create_local_sample()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@browser_router.get("/sessions/{session_id}/report", response_class=HTMLResponse)
def report(session_id: str) -> HTMLResponse:
    try:
        content = report_html(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Browser session not found.") from exc
    policy = (
        "default-src 'self'; img-src 'self'; style-src 'unsafe-inline'; "
        "frame-ancestors 'none'; base-uri 'none'"
    )
    return HTMLResponse(content, headers={"Content-Security-Policy": policy})


@browser_router.get("/sessions/{session_id}/screenshot")
def screenshot(session_id: str) -> Response:
    try:
        content, media_type = screenshot_bytes(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Screenshot not found.") from exc
    return Response(content, media_type=media_type, headers={"Cache-Control": "no-store"})


@browser_router.get("/sessions/{session_id}/bug-report")
def bug_report(session_id: str) -> Response:
    try:
        content = bug_report_markdown(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Browser session not found.") from exc
    return Response(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="eagleeye-{session_id[:8]}-bug-report.md"',
        },
    )


@router.get("/demo-site/sample", response_class=HTMLResponse, include_in_schema=False)
def bundled_sample_page() -> HTMLResponse:
    policy = (
        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    )
    return HTMLResponse(
        demo_site_html(sample_page=True),
        headers={"Content-Security-Policy": policy, "Cache-Control": "no-store"},
    )


router.include_router(browser_router)
