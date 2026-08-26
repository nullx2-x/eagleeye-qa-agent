from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import RunResult
from .project_qa_models import ProjectRunReport
from .strategy_models import QualityGateResponse, ServiceType, TestMode

VerificationStatus = Literal["PASS", "BLOCKED", "FAIL"]


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectRoot: str = Field(min_length=1, max_length=2_000)
    authorized: Literal[True]
    baseRef: str | None = Field(default=None, max_length=200)
    headRef: str = Field(default="HEAD", min_length=1, max_length=200)
    serviceType: ServiceType = ServiceType.WEB
    mode: TestMode | None = None
    suiteIds: list[str] = Field(default_factory=list, max_length=200)
    browserSessionIds: list[str] = Field(default_factory=list, max_length=100)
    aiExploration: bool = False
    allowDirty: bool = False
    timeoutSeconds: int = Field(default=900, ge=5, le=3_600)
    failFast: bool = False
    previousVerificationId: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{32}$",
    )


class GitVerificationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repositoryRoot: str
    repositoryId: str
    rootFingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    branch: str | None = None
    baseCommit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    headCommit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    mergeBase: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    changedFiles: list[str]
    diffSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workingTreeSha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    dirty: bool
    untrackedPresent: bool


class VerificationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verificationId: str = Field(pattern=r"^[a-f0-9]{32}$")
    recommendedMode: TestMode
    riskScore: int = Field(ge=0, le=100)
    requiredSuites: list[str]
    optionalSuites: list[str]
    browserReplayRequired: bool
    urlAuditRequired: bool = False
    aiExplorationAllowed: bool
    humanApprovalRequired: bool
    reasons: list[str]


class VerificationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=160)
    kind: str = Field(min_length=1, max_length=80)
    path: str = Field(min_length=1, max_length=2_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)
    createdAt: str
    source: str = Field(min_length=1, max_length=200)
    relatedTestId: str | None = Field(default=None, max_length=200)


class ReverificationLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previousVerificationId: str = Field(pattern=r"^[a-f0-9]{32}$")
    previousVerdict: VerificationStatus
    failureFingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    repairSource: str | None = Field(default=None, max_length=200)


class ManifestRepository(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rootFingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    branch: str | None = None
    baseCommit: str
    headCommit: str
    mergeBase: str
    diffSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workingTreeSha256: str | None = None
    dirty: bool


class ManifestPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TestMode
    riskScore: int = Field(ge=0, le=100)
    policySha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ManifestExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    startedAt: str
    completedAt: str
    environmentFingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    cleanRoom: bool = False
    cleanRoomReason: str


class ManifestAI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    used: bool
    provider: str | None = None
    model: str | None = None
    authoritative: Literal[False] = False


class ManifestVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: VerificationStatus
    blockers: list[str]
    warnings: list[str]


class VerificationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal["1"] = "1"
    verificationId: str = Field(pattern=r"^[a-f0-9]{32}$")
    repository: ManifestRepository
    policy: ManifestPolicy
    execution: ManifestExecution
    tests: list[dict]
    browser: list[dict]
    ai: ManifestAI
    evidence: list[VerificationEvidence]
    verdict: ManifestVerdict
    reverification: ReverificationLink | None = None
    manifestSha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verificationId: str = Field(pattern=r"^[a-f0-9]{32}$")
    status: VerificationStatus
    gitContext: GitVerificationContext
    plan: VerificationPlan
    projectQa: ProjectRunReport
    browserRuns: list[RunResult]
    qualityGate: QualityGateResponse
    evidence: list[VerificationEvidence]
    reverification: ReverificationLink | None = None
    manifestPath: str
    manifestSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reportJson: str
    reportMarkdown: str
