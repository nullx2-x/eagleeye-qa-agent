from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_advisor import _safe_test_names  # noqa: E402 - project root is added for direct CLI use
from app.ai_safety_eval import (  # noqa: E402 - project root is added for direct CLI use
    inspect_untrusted_advice,
)


def run(dataset: Path) -> dict:
    cases = json.loads(dataset.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        findings = inspect_untrusted_advice(case["payload"])
        tests = _safe_test_names(case["payload"].get("additionalTests"))
        passed = findings == case["expectedFindings"] and tests == case["expectedTests"]
        results.append(
            {
                "id": case["id"],
                "status": "PASS" if passed else "FAIL",
                "findings": findings,
                "tests": tests,
            }
        )
    passed_count = sum(item["status"] == "PASS" for item in results)
    return {
        "schemaVersion": 1,
        "finishedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "PASS" if passed_count == len(results) else "FAIL",
        "caseCount": len(results),
        "passed": passed_count,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic AI safety regression evals")
    parser.add_argument("--dataset", type=Path, default=Path("evals/ai-safety-cases.json"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/evals/ai-safety-latest.json"))
    args = parser.parse_args()
    report = run(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
