from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.url_audit import run_url_audit
from app.url_audit_models import UrlAuditRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run EagleEye's authorized, observation-only URL Audit.",
    )
    parser.add_argument("url", help="Authorized HTTP(S) target URL")
    parser.add_argument("--project-name", help="Optional QA project display name")
    parser.add_argument(
        "--allow-localhost",
        action="store_true",
        help=(
            "Allow loopback resolution. Also requires EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST=1; "
            "LAN, link-local, metadata, and reserved targets stay blocked."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = UrlAuditRequest.model_validate(
        {
            "targetUrl": args.url,
            "authorized": True,
            "allowLocalhost": args.allow_localhost,
            "projectName": args.project_name,
        }
    )
    report = run_url_audit(request)
    summary = {
        "auditId": report.auditId,
        "decision": report.decision,
        "projectId": report.project.id if report.project else None,
        "testCaseQuality": report.project.caseQuality.decision if report.project else None,
        "reportJson": _relative(report.reportJson),
        "reportMarkdown": _relative(report.reportMarkdown),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if report.decision == "BLOCKED" else 0


def _relative(value: str) -> str:
    path = Path(value).resolve()
    root = Path(__file__).resolve().parents[1]
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "[outside-project-root]"


if __name__ == "__main__":
    raise SystemExit(main())
