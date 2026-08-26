from __future__ import annotations

from .project_qa_models import ProjectDiscoveryResponse
from .strategy import generate_profile
from .strategy_models import DevelopmentStage, ProfileRequest, ProfileResponse
from .verification_models import GitVerificationContext, VerificationPlan, VerificationRequest


def build_verification_plan(
    request: VerificationRequest,
    context: GitVerificationContext,
    discovery: ProjectDiscoveryResponse,
    verification_id: str,
) -> tuple[VerificationPlan, ProfileResponse]:
    profile_request = ProfileRequest(
        projectId=discovery.projectId,
        developmentStage=DevelopmentStage.DEVELOPMENT,
        serviceType=request.serviceType,
        environment="local",
        production=False,
        changedFiles=context.changedFiles,
        requestedMode=request.mode,
        aiEnabled=False,
    )
    profile = generate_profile(profile_request)
    selected = discovery.suites
    if request.suiteIds:
        wanted = set(request.suiteIds)
        selected = [suite for suite in discovery.suites if suite.id in wanted]
        missing = sorted(wanted - {suite.id for suite in selected})
        if missing:
            raise ValueError(f"Unknown suiteIds: {', '.join(missing)}")
    if not selected:
        raise ValueError("No executable QA suites were selected")

    reasons = list(profile.reasons)
    if context.dirty:
        reasons.append("Uncommitted working-tree state is included in the verification fingerprint")
    if request.browserSessionIds:
        reasons.append("Recorded browser evidence is included as a critical-flow verification input")
    if request.aiExploration:
        reasons.append("AI exploration is permitted only as non-authoritative additional coverage")

    return (
        VerificationPlan(
            verificationId=verification_id,
            recommendedMode=profile.recommendedMode,
            riskScore=profile.riskScore,
            requiredSuites=[suite.id for suite in selected if suite.required],
            optionalSuites=[suite.id for suite in selected if not suite.required],
            browserReplayRequired=bool(request.browserSessionIds),
            urlAuditRequired=False,
            aiExplorationAllowed=request.aiExploration,
            humanApprovalRequired=profile.humanApprovalRequired,
            reasons=reasons,
        ),
        profile,
    )
