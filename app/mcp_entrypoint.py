from __future__ import annotations

from . import mcp_server
from .verification_models import VerificationRequest
from .verification_service import load_verification, run_verification


@mcp_server.mcp.tool()
def verify_project_change(
    project_root: str,
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    service_type: str = "web",
    mode: str | None = None,
    suite_ids: list[str] | None = None,
    browser_session_ids: list[str] | None = None,
    previous_verification_id: str | None = None,
    allow_dirty: bool = False,
    authorized: bool = False,
) -> dict:
    """Verify an authorized repository change; deterministic execution owns the verdict."""
    if not authorized:
        raise PermissionError("Explicit verification authorization is required")
    request = VerificationRequest.model_validate(
        {
            "projectRoot": project_root,
            "authorized": True,
            "baseRef": base_ref,
            "headRef": head_ref,
            "serviceType": service_type,
            "mode": mode,
            "suiteIds": suite_ids or [],
            "browserSessionIds": browser_session_ids or [],
            "previousVerificationId": previous_verification_id,
            "allowDirty": allow_dirty,
        }
    )
    return run_verification(request).model_dump(mode="json")


@mcp_server.mcp.tool()
def verification_status(verification_id: str) -> dict:
    """Read an evidence-backed verification and its manifest hash."""
    return load_verification(verification_id).model_dump(mode="json")


@mcp_server.mcp.tool()
def prepare_reverification(
    previous_verification_id: str,
    project_root: str,
    authorized: bool = False,
) -> dict:
    """Prepare, but do not execute, an independent verification after a repair."""
    if not authorized:
        raise PermissionError("Explicit verification authorization is required")
    previous = load_verification(previous_verification_id)
    return {
        "projectRoot": project_root,
        "authorized": True,
        "baseRef": previous.gitContext.headCommit,
        "headRef": "HEAD",
        "previousVerificationId": previous.verificationId,
        "approvalRequired": True,
        "note": "Run verify_project_change only after reviewing the repaired working tree.",
    }


def main() -> None:
    mcp_server.main()


if __name__ == "__main__":
    main()
