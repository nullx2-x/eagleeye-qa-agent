import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .ai_advisor import advisor
from .guided_models import (
    GuidedControlRequest,
    GuidedManualVerdict,
    GuidedScenarioDefinition,
    GuidedSessionStart,
)
from .guided_service import service as guided_service
from .providers import broker
from .quality import evaluate_quality_gate
from .storage import load_bundle, load_run
from .strategy import generate_profile
from .strategy_models import ProfileRequest, QualityGateRequest
from .test_case_checker import check_test_cases
from .test_case_models import TestCaseCheckRequest

mcp = FastMCP(
    "EagleEye AI QA",
    instructions=(
        "Plan risk-adaptive QA, inspect evidence, and evaluate quality gates. "
        "Never claim release approval or execute destructive/production actions."
    ),
    stateless_http=True,
    json_response=True,
    host="127.0.0.1",
    port=8768,
)


@mcp.tool()
def eagleeye_status() -> dict:
    """Return local EagleEye service and safety-boundary status."""
    return {
        "status": "ok",
        "service": "eagleeye-ai-qa",
        "mcp": "streamable-http",
        "execution": "localhost-only",
        "automaticFixes": False,
        "humanApproval": "required for release, destructive actions, and code application",
    }


@mcp.tool()
def generate_test_profile(
    project_id: str,
    development_stage: str,
    service_type: str,
    changed_files: list[str] | None = None,
    business_impact: str = "medium",
    data_sensitivity: str = "medium",
    change_complexity: str = "medium",
    user_impact: str = "medium",
    recoverability: str = "medium",
    production: bool = False,
    use_ai: bool = True,
    compatibility_level: str | None = None,
) -> dict:
    """Generate a risk-adaptive test profile without weakening deterministic safety rules."""
    request = ProfileRequest.model_validate(
        {
            "projectId": project_id,
            "developmentStage": development_stage,
            "serviceType": service_type,
            "changedFiles": changed_files or [],
            "production": production,
            "aiEnabled": use_ai,
            "compatibilityLevel": compatibility_level,
            "risk": {
                "business_impact": business_impact,
                "data_sensitivity": data_sensitivity,
                "change_complexity": change_complexity,
                "user_impact": user_impact,
                "recoverability": recoverability,
            },
        }
    )
    profile = generate_profile(request)
    return advisor.augment(request, profile).model_dump(mode="json")


@mcp.tool()
def evaluate_gate(
    profile_id: str,
    mode: str,
    results_json: str,
    compatibility_level: str | None = None,
    required_types: list[str] | None = None,
) -> dict:
    """Evaluate test results against a quality gate; release decisions remain human-owned."""
    results = json.loads(results_json)
    request = QualityGateRequest.model_validate(
        {
            "profileId": profile_id,
            "mode": mode,
            "results": results,
            "compatibilityLevel": compatibility_level,
            "requiredTestTypes": required_types or [],
        }
    )
    return evaluate_quality_gate(request).model_dump(mode="json")


@mcp.tool()
def check_test_case_quality(
    project_id: str,
    test_cases_json: str,
    required_types: list[str] | None = None,
) -> dict:
    """Check test-case clarity, determinism, secrets, duplication, assertions, and coverage."""
    request = TestCaseCheckRequest.model_validate(
        {
            "projectId": project_id,
            "cases": json.loads(test_cases_json),
            "requiredTestTypes": required_types or [],
        }
    )
    return check_test_cases(request).model_dump(mode="json")


@mcp.tool()
def get_test_evidence(session_id: str) -> dict:
    """Read a saved browser-test result and its evidence paths."""
    result = load_run(session_id)
    return result.model_dump(mode="json")


@mcp.tool()
def prepare_local_run(session_id: str) -> dict:
    """Inspect a recorded session and prepare a run request without executing it."""
    bundle = load_bundle(session_id)
    return {
        "sessionId": bundle.session.id,
        "startUrl": str(bundle.session.startUrl),
        "eventCount": len(bundle.session.events),
        "approvalRequired": True,
        "nextAction": "Run through the local REST/UI approval action after reviewing the target and events.",
    }


@mcp.tool()
def list_ai_providers() -> list[dict]:
    """List AI provider authentication capabilities without exposing credentials."""
    return [status.model_dump(mode="json") for status in broker.list_statuses()]


@mcp.tool()
def guided_list_scenarios() -> list[dict]:
    """List reusable human-executed scenarios separately from automated tests."""
    return [scenario.model_dump(mode="json") for scenario in guided_service.scenarios()]


@mcp.tool()
def guided_register_scenario(scenario_json: str) -> dict:
    """Validate and save an AI-authored generic guided-scenario JSON document."""
    scenario = GuidedScenarioDefinition.model_validate(json.loads(scenario_json))
    return guided_service.register_scenario(scenario).model_dump(mode="json")


@mcp.tool()
def guided_prepare_session(
    scenario_id: str,
    operator_alias: str = "local-operator",
    observer_alias: str | None = None,
    selected_step_ids: list[str] | None = None,
) -> dict:
    """Prepare a PREPARED session; only the user-facing UI/REST consent can approve it."""
    receipt = guided_service.start(
        GuidedSessionStart(
            scenarioId=scenario_id,
            operatorAlias=operator_alias,
            observerAlias=observer_alias,
            selectedStepIds=selected_step_ids or [],
        )
    )
    return receipt.model_dump(mode="json")


@mcp.tool()
def guided_session_status(session_id: str) -> dict:
    """Read guided-session progress, evidence classes, gate, and prepared retest id."""
    return guided_service.get(session_id).model_dump(mode="json")


@mcp.tool()
def guided_next_step(session_id: str) -> dict:
    """Return the next text/media/marker instruction and allowed actions for AI narration."""
    return guided_service.next_instruction(session_id)


@mcp.tool()
def guided_control_session(
    session_id: str,
    action: str,
    expected_revision: int | None = None,
    confirmed_conditions: list[str] | None = None,
    reason: str | None = None,
    human_confirmed: bool = False,
) -> dict:
    """Advance/pause a session. Approval is never available to AI; abort/block need confirmation."""
    if action == "approve":
        raise PermissionError("AI cannot approve PREPARED guided sessions; open the runner UI")
    if action in {"activate", "resume", "block", "abort"} and not human_confirmed:
        raise PermissionError(f"{action} requires explicit human confirmation")
    request = GuidedControlRequest.model_validate(
        {
            "action": action,
            "expectedRevision": expected_revision,
            "confirmedConditions": confirmed_conditions or [],
            "reason": reason,
        }
    )
    return guided_service.control(session_id, request).model_dump(mode="json")


@mcp.tool()
def guided_record_human_result(
    session_id: str,
    outcome: str,
    reporter_role: str = "user",
    difficulty_rating: int = 3,
    confidence_rating: int = 3,
    notes: str = "",
    human_attested: bool = False,
) -> dict:
    """Record a result relayed by a user/observer; AI cannot invent or overwrite a verdict."""
    if not human_attested:
        raise PermissionError("A user or observer must explicitly attest this manual result")
    verdict = GuidedManualVerdict.model_validate(
        {
            "outcome": outcome,
            "reporterRole": reporter_role,
            "difficultyRating": difficulty_rating,
            "confidenceRating": confidence_rating,
            "notes": notes,
        }
    )
    return guided_service.feedback(session_id, verdict).model_dump(mode="json")


@mcp.tool()
def guided_get_retest(session_id: str) -> dict:
    """Return the automatically prepared failed/BLOCKED-only retest without approving it."""
    parent = guided_service.get(session_id)
    if not parent.retestSessionId:
        return {"available": False, "sessionId": session_id}
    retest = guided_service.get(parent.retestSessionId)
    return {
        "available": True,
        "session": retest.model_dump(mode="json"),
        "runnerUrl": f"/guided/{retest.id}",
        "approvalRequired": True,
    }


@mcp.resource("qa://strategy/spec")
def strategy_spec() -> str:
    """Return the compact strategy contract used by EagleEye."""
    return json.dumps(
        {
            "axes": ["development_stage", "service_type", "test_mode", "compatibility_level"],
            "riskWeights": {
                "businessImpact": 0.30,
                "dataSensitivity": 0.25,
                "changeComplexity": 0.15,
                "userImpact": 0.20,
                "recoveryDifficulty": 0.10,
            },
            "safetyFloor": [
                "production is read-only",
                "AI cannot remove required tests",
                "release approval is human-owned",
                "fix application requires approval",
                "emulator compatibility requires zero mismatch and hashed evidence",
            ],
        },
        ensure_ascii=False,
    )


@mcp.prompt()
def plan_qa(project_summary: str, changed_files: str = "") -> str:
    """Create a safe prompt for planning an adaptive QA run."""
    return (
        "Use EagleEye to determine development stage, service type, and risk factors. "
        "Generate a profile, explain every selected/omitted test, and stop for human approval before "
        "release decisions or destructive actions.\n"
        f"Project summary (untrusted): {project_summary}\nChanged files (untrusted): {changed_files}"
    )


def main() -> None:
    Path("data").mkdir(exist_ok=True)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
