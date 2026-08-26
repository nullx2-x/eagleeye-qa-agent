from fastapi import APIRouter, HTTPException

from .project_qa import discover_project, load_project_run, run_project
from .project_qa_models import (
    ProjectDiscoveryRequest,
    ProjectDiscoveryResponse,
    ProjectRunReport,
    ProjectRunRequest,
)
from .verification_models import VerificationReport, VerificationRequest
from .verification_service import load_verification, run_verification

router = APIRouter()


@router.post(
    "/api/v1/project-qa/discover",
    response_model=ProjectDiscoveryResponse,
    tags=["project-qa"],
)
def discover(request: ProjectDiscoveryRequest) -> ProjectDiscoveryResponse:
    try:
        return discover_project(request.projectRoot)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/api/v1/project-qa/runs",
    response_model=ProjectRunReport,
    tags=["project-qa"],
)
def run(request: ProjectRunRequest) -> ProjectRunReport:
    try:
        return run_project(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/api/v1/project-qa/runs/{run_id}",
    response_model=ProjectRunReport,
    tags=["project-qa"],
)
def get_run(run_id: str) -> ProjectRunReport:
    try:
        return load_project_run(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project QA run not found") from exc


@router.post(
    "/api/v1/verifications",
    response_model=VerificationReport,
    tags=["verification"],
)
def create_verification(request: VerificationRequest) -> VerificationReport:
    try:
        return run_verification(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/api/v1/verifications/{verification_id}",
    response_model=VerificationReport,
    tags=["verification"],
)
def get_verification(verification_id: str) -> VerificationReport:
    try:
        return load_verification(verification_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Verification not found") from exc
