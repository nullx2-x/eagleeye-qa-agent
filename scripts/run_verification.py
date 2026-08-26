from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.verification_models import VerificationRequest
from app.verification_service import run_verification

EXIT_CODES = {
    "PASS": 0,
    "BLOCKED": 10,
    "FAIL": 20,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an evidence-backed EagleEye verification.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--base", dest="base_ref")
    parser.add_argument("--head", dest="head_ref", default="HEAD")
    parser.add_argument("--service-type", default="web")
    parser.add_argument("--mode")
    parser.add_argument("--suite", dest="suite_ids", action="append", default=[])
    parser.add_argument("--browser-session", dest="browser_session_ids", action="append", default=[])
    parser.add_argument("--previous-verification")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--ai-exploration", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        request = VerificationRequest.model_validate(
            {
                "projectRoot": str(Path(args.project_root).resolve()),
                "authorized": True,
                "baseRef": args.base_ref,
                "headRef": args.head_ref,
                "serviceType": args.service_type,
                "mode": args.mode,
                "suiteIds": args.suite_ids,
                "browserSessionIds": args.browser_session_ids,
                "previousVerificationId": args.previous_verification,
                "allowDirty": args.allow_dirty,
                "aiExploration": args.ai_exploration,
                "failFast": args.fail_fast,
                "timeoutSeconds": args.timeout_seconds,
            }
        )
        report = run_verification(request)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"EagleEye verification could not run: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 30

    print("EagleEye Verification")
    print("-" * 40)
    print(f"Verdict     {report.status}")
    print(f"Base        {report.gitContext.baseCommit}")
    print(f"Head        {report.gitContext.headCommit}")
    print(f"Changed     {len(report.gitContext.changedFiles)} files")
    print(f"Risk        {report.plan.riskScore}/100")
    print(f"Mode        {report.plan.recommendedMode.value}")
    print(f"Manifest    {report.manifestPath}")
    print(f"ManifestSHA {report.manifestSha256}")
    if report.qualityGate.blockers:
        print("Blockers")
        for blocker in report.qualityGate.blockers:
            print(f"  - {blocker}")
    return EXIT_CODES[report.status]


if __name__ == "__main__":
    raise SystemExit(main())
