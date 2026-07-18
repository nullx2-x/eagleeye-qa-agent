from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.repair_models import RepairLimits, RepairPlannerInput, RepairRequest
from app.repair_service import RepairPlanningDecision, RepairService, _evidence_documents


def _request() -> RepairRequest:
    return RepairRequest(
        projectId="eagleeye-qa-agent",
        environment="local",
        production=False,
        provider="codex-agent",
        model="gpt-5.6-sol",
        requestedMode="proposal_only",
        explicitApplyRequested=False,
        failureFingerprint="a" * 64,
        failureSummary="A deterministic local source failure",
        evidencePaths=[],
    )


def _planner_input(root: Path) -> RepairPlannerInput:
    return RepairPlannerInput(
        request=_request(),
        projectRoot=root,
        attempt=1,
        limits=RepairLimits(),
        previousFailures=[],
    )


def test_planner_can_explicitly_decline_unsafe_repair(tmp_path: Path) -> None:
    def runner(**_: object) -> dict:
        return {
            "action": "no_safe_repair",
            "reason": "Evidence is insufficient for a deterministic correction.",
            "plan": None,
        }

    service = RepairService(structured_runner=runner)
    with pytest.raises(ValueError, match="No safe automatic repair"):
        service._plan(_planner_input(tmp_path))


def test_low_confidence_plan_is_not_eligible_for_application(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()

    def runner(**_: object) -> dict:
        return {
            "action": "repair",
            "reason": "Possible source correction, but confidence is low.",
            "plan": {
                "summary": "Change the sample value.",
                "confidence": 0.50,
                "files": [
                    {
                        "operation": "replace",
                        "path": "sample.py",
                        "expectedSha256": digest,
                        "replacements": [{"old": "VALUE = 1", "new": "VALUE = 2"}],
                    }
                ],
            },
        }

    service = RepairService(structured_runner=runner)
    with pytest.raises(ValueError, match="below 0.85"):
        service._plan(_planner_input(tmp_path))


def test_evidence_documents_include_redacted_content_and_reject_escape(tmp_path: Path) -> None:
    evidence = tmp_path / "failure.log"
    evidence.write_text(
        "selector button was not found\npassword=supersecret\n",
        encoding="utf-8",
    )
    outside = tmp_path.parent / "outside.log"
    outside.write_text("must not be exposed", encoding="utf-8")

    documents = _evidence_documents(tmp_path, [str(evidence), str(outside)])

    assert documents[0]["contentSha256"] == hashlib.sha256(evidence.read_bytes()).hexdigest()
    assert "selector button was not found" in documents[0]["excerpt"]
    assert "supersecret" not in documents[0]["excerpt"]
    assert "[REDACTED]" in documents[0]["excerpt"]
    assert documents[1]["status"] == "unavailable_or_outside_root"


def test_project_lock_is_stable_per_project() -> None:
    service = RepairService(structured_runner=lambda **_: {})

    assert service._project_lock("one") is service._project_lock("one")
    assert service._project_lock("one") is not service._project_lock("two")


def test_planning_decision_rejects_inconsistent_payload() -> None:
    with pytest.raises(ValueError, match="cannot include a plan"):
        RepairPlanningDecision.model_validate(
            {
                "action": "no_safe_repair",
                "reason": "No safe repair.",
                "plan": {
                    "summary": "Unexpected plan",
                    "confidence": 1.0,
                    "files": [
                        {
                            "operation": "replace",
                            "path": "sample.py",
                            "expectedSha256": "b" * 64,
                            "replacements": [{"old": "x", "new": "y"}],
                        }
                    ],
                },
            }
        )
