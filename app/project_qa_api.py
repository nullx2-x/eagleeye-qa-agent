from fastapi import APIRouter, HTTPException

from .project_qa import discover_project, load_project_run, run_project
from .project_qa_models import (
    ProjectDiscoveryRequest,
    ProjectDiscoveryResponse,
    ProjectRunReport,
    ProjectRunRequest,
)

router = APIRouter(prefix="/api/v1/project-qa", tags=["project-qa"])


@router.post("/discover", response_model=ProjectDiscoveryResponse)
def discover(request: ProjectDiscoveryRequest) -> ProjectDiscoveryResponse:
    try:
        return discover_project(request.projectRoot)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/runs", response_model=ProjectRunReport)
def run(request: ProjectRunRequest) -> ProjectRunReport:
    try:
        return run_project(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=ProjectRunReport)
def get_run(run_id: str) -> ProjectRunReport:
    try:
        return load_project_run(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project QA run not found") from exc
