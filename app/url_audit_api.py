from fastapi import APIRouter, HTTPException, Response

from .url_audit import delete_url_audit, load_url_audit, run_url_audit, url_audit_markdown
from .url_audit_models import UrlAuditReport, UrlAuditRequest

router = APIRouter(prefix="/api/v1/url-audits", tags=["url-audit"])


@router.post("", response_model=UrlAuditReport)
def create_url_audit(request: UrlAuditRequest) -> UrlAuditReport:
    try:
        return run_url_audit(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{audit_id}", response_model=UrlAuditReport)
def get_url_audit(audit_id: str) -> UrlAuditReport:
    try:
        return load_url_audit(audit_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="URL audit not found") from exc


@router.get("/{audit_id}/report")
def get_url_audit_report(audit_id: str) -> Response:
    try:
        content = url_audit_markdown(audit_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="URL audit report not found") from exc
    return Response(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="eagleeye-url-audit-{audit_id[:8]}.md"',
        },
    )


@router.delete("/{audit_id}", status_code=204)
def remove_url_audit(audit_id: str) -> Response:
    try:
        delete_url_audit(audit_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="URL audit not found") from exc
    return Response(status_code=204)
