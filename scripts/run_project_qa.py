from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.project_qa import discover_project, run_project  # noqa: E402
from app.project_qa_models import ProjectRunRequest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EagleEye against an authorized local project")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--suite", action="append", default=[])
    parser.add_argument("--mode", default="development")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    if args.discover:
        result = discover_project(str(args.project_root))
    else:
        result = run_project(
            ProjectRunRequest.model_validate(
                {
                    "projectRoot": str(args.project_root),
                    "authorized": True,
                    "suiteIds": args.suite,
                    "mode": args.mode,
                    "timeoutSeconds": args.timeout,
                    "failFast": args.fail_fast,
                }
            )
        )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
