from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from .guided_models import (
    GuidedControlRequest,
    GuidedManualVerdict,
    GuidedObservation,
    GuidedObservationBatch,
    GuidedObservationReceipt,
    GuidedScenarioDefinition,
    GuidedSession,
    GuidedSessionReceipt,
    GuidedSessionStart,
)
from .guided_service import HumanAttestationRequired, InvalidTransition, service
from .guided_storage import GUIDED_ASSETS, RevisionConflict, ScenarioInUse
from .guided_ui import guided_home_html, guided_runner_html

router = APIRouter()

_GUIDED_ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_GUIDED_ASSET_CHARACTERS = frozenset("._-")


def _is_guided_session_id(value: str) -> bool:
    suffix = value.removeprefix("guided-")
    return (
        len(value) == 39
        and len(suffix) == 32
        and all(character in "0123456789abcdef" for character in suffix)
    )


def _is_guided_asset_path(value: str) -> bool:
    if not value or len(value) > 512 or "\\" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    if any(
        not part
        or len(part) > 128
        or not part[0].isascii()
        or not part[0].isalnum()
        or any(
            not character.isascii() or (not character.isalnum() and character not in _GUIDED_ASSET_CHARACTERS)
            for character in part
        )
        for part in parts
    ):
        return False
    return Path(parts[-1]).suffix.lower() in _GUIDED_ASSET_SUFFIXES


def _guided_asset_catalog(root: Path) -> dict[str, Path]:
    """Index only regular, non-symlinked image files already inside the asset root."""

    catalog: dict[str, Path] = {}
    for entry in root.rglob("*"):
        if entry.is_symlink() or not entry.is_file() or entry.suffix.lower() not in _GUIDED_ASSET_SUFFIXES:
            continue
        resolved = entry.resolve()
        if root not in resolved.parents:
            continue
        catalog[resolved.relative_to(root).as_posix()] = resolved
    return catalog


@router.post("/api/v1/guided/scenarios", response_model=GuidedScenarioDefinition)
def register_guided_scenario(scenario: GuidedScenarioDefinition) -> GuidedScenarioDefinition:
    try:
        return service.register_scenario(scenario)
    except ScenarioInUse as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/guided/scenarios", response_model=list[GuidedScenarioDefinition])
def list_guided_scenarios() -> list[GuidedScenarioDefinition]:
    return service.scenarios()


@router.get("/api/v1/guided/scenarios/{scenario_id}", response_model=GuidedScenarioDefinition)
def get_guided_scenario(scenario_id: str) -> GuidedScenarioDefinition:
    try:
        return service.scenario(scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided scenario not found") from exc


@router.post("/api/v1/guided/sessions", response_model=GuidedSessionReceipt)
def start_guided_session(request: GuidedSessionStart) -> GuidedSessionReceipt:
    try:
        return service.start(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided scenario or parent not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/guided/sessions", response_model=list[GuidedSession])
def list_guided_sessions(
    scenario_id: str | None = Query(default=None, max_length=120),
) -> list[GuidedSession]:
    return service.sessions(scenario_id)


@router.get("/api/v1/guided/sessions/{session_id}", response_model=GuidedSession)
def get_guided_session(session_id: str) -> GuidedSession:
    try:
        return service.get(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc


@router.get("/api/v1/guided/sessions/{session_id}/next", response_model=dict[str, Any])
def get_guided_next_instruction(session_id: str) -> dict[str, Any]:
    try:
        return service.next_instruction(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc


@router.post("/api/v1/guided/sessions/{session_id}/control", response_model=GuidedSession)
def control_guided_session(
    session_id: str,
    request: GuidedControlRequest,
    human_attestation: str | None = Header(default=None, alias="X-EagleEye-Human-Attestation"),
) -> GuidedSession:
    try:
        return service.control(session_id, request, human_attestation)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc
    except HumanAttestationRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (InvalidTransition, RevisionConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/v1/guided/sessions/{session_id}/observations", response_model=GuidedSession)
def ingest_guided_observation(session_id: str, observation: GuidedObservation) -> GuidedSession:
    try:
        return service.observe(session_id, observation)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc
    except (InvalidTransition, RevisionConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/api/v1/guided/sessions/{session_id}/observations",
    response_model=list[GuidedObservation],
)
def list_guided_observations(session_id: str) -> list[GuidedObservation]:
    try:
        return service.observations(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc


@router.post(
    "/api/v1/guided/sessions/{session_id}/observations:batch",
    response_model=GuidedObservationReceipt,
)
def ingest_guided_observation_batch(
    session_id: str, batch: GuidedObservationBatch
) -> GuidedObservationReceipt:
    try:
        return service.observe_batch(session_id, batch)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc
    except (InvalidTransition, RevisionConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/v1/guided/sessions/{session_id}/feedback", response_model=GuidedSession)
def submit_guided_feedback(
    session_id: str,
    verdict: GuidedManualVerdict,
    human_attestation: str | None = Header(default=None, alias="X-EagleEye-Human-Attestation"),
) -> GuidedSession:
    try:
        return service.feedback(session_id, verdict, human_attestation)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc
    except HumanAttestationRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (InvalidTransition, RevisionConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/guided/sessions/{session_id}/report", response_class=PlainTextResponse)
def guided_session_report(session_id: str) -> str:
    try:
        return service.report(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc


@router.get("/api/v1/guided/assets/{asset_path:path}", response_class=FileResponse)
def guided_asset(asset_path: str) -> FileResponse:
    root = GUIDED_ASSETS.resolve()
    if not _is_guided_asset_path(asset_path):
        raise HTTPException(status_code=404, detail="Guided asset not found")
    candidate = _guided_asset_catalog(root).get(asset_path)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Guided asset not found")
    return FileResponse(candidate)


@router.get("/guided", response_class=HTMLResponse)
def guided_home() -> str:
    return guided_home_html()


@router.get("/guided/{session_id}", response_class=HTMLResponse)
def guided_runner(session_id: str) -> HTMLResponse:
    if not _is_guided_session_id(session_id):
        raise HTTPException(status_code=404, detail="Guided session not found")
    try:
        service.get(session_id)
        attestation_token = service.runner_attestation_token(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Guided session not found") from exc
    return HTMLResponse(
        content=guided_runner_html(attestation_token),
        headers={
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
        },
    )
