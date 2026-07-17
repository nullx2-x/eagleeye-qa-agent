from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DevelopmentStage(StrEnum):
    PLANNING = "planning"
    POC = "poc"
    DEVELOPMENT = "development"
    INTEGRATION = "integration"
    SYSTEM_TEST = "system_test"
    RELEASE = "release"
    PRODUCTION = "production"
    MAINTENANCE = "maintenance"


class ServiceType(StrEnum):
    WEB = "web"
    ECOMMERCE = "ecommerce"
    BUSINESS = "business"
    API = "api"
    BATCH = "batch"
    AI_AGENT = "ai_agent"
    LEGACY_DESKTOP = "legacy_desktop"
    EMULATOR = "emulator"


class CompatibilityLevel(StrEnum):
    FUNCTIONAL = "functional"
    SYSTEM = "system"
    CYCLE = "cycle"
    PHYSICAL = "physical"


class TestMode(StrEnum):
    QUICK = "quick"
    DEVELOPMENT = "development"
    INTEGRATION = "integration"
    STANDARD = "standard"
    STRICT = "strict"
    RELEASE_GATE = "release_gate"
    PRODUCTION_SAFE = "production_safe"
    MAINTENANCE = "maintenance"
    EXPLORATORY_AI = "exploratory_ai"


RiskLevel = Literal["low", "medium", "high", "critical"]
ResultStatus = Literal[
    "PASSED",
    "FAILED",
    "FLAKY",
    "BLOCKED",
    "SKIPPED",
    "NOT_APPLICABLE",
    "INFRA_ERROR",
]
Severity = Literal["critical", "high", "medium", "low", "info"]


class RiskFactors(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_impact: RiskLevel = "medium"
    data_sensitivity: RiskLevel = "medium"
    change_complexity: RiskLevel = "medium"
    user_impact: RiskLevel = "medium"
    recoverability: RiskLevel = "medium"


class ProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    projectId: str = Field(min_length=1, max_length=100)
    developmentStage: DevelopmentStage
    serviceType: ServiceType
    environment: str = Field(default="local", max_length=100)
    production: bool = False
    changedFiles: list[str] = Field(default_factory=list, max_length=1_000)
    risk: RiskFactors = Field(default_factory=RiskFactors)
    requestedMode: TestMode | None = None
    maxDurationMinutes: int = Field(default=30, ge=1, le=1_440)
    parallelism: int = Field(default=4, ge=1, le=64)
    aiEnabled: bool = True
    compatibilityLevel: CompatibilityLevel | None = None


class TestSelection(BaseModel):
    name: str
    intensity: Literal["smoke", "changed", "critical", "full", "read_only"]
    reason: str
    required: bool = True


class ProfileResponse(BaseModel):
    id: str
    projectId: str
    developmentStage: DevelopmentStage
    serviceType: ServiceType
    compatibilityLevel: CompatibilityLevel | None = None
    recommendedMode: TestMode
    requestedMode: TestMode | None = None
    riskScore: int
    reasons: list[str]
    requiredTests: list[str]
    optionalTests: list[str]
    selections: list[TestSelection]
    restrictions: list[str]
    humanApprovalRequired: bool
    fullRegressionRequired: bool
    configuration: dict


class TestResultInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    testId: str = Field(min_length=1, max_length=200)
    testType: str = Field(min_length=1, max_length=100)
    status: ResultStatus
    severity: Severity = "medium"
    criticalFlow: bool = False
    durationMs: int = Field(default=0, ge=0)
    retryCount: int = Field(default=0, ge=0)
    errorMessage: str | None = Field(default=None, max_length=4_000)
    mismatchCount: int | None = Field(default=None, ge=0)
    coveragePercent: float | None = Field(default=None, ge=0, le=100)
    sampleCount: int | None = Field(default=None, ge=0)
    evidencePath: str | None = Field(default=None, max_length=2_000)
    evidenceSha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    oracle: str | None = Field(default=None, min_length=1, max_length=300)
    deterministic: bool | None = None


class QualityGateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profileId: str = Field(min_length=1, max_length=100)
    mode: TestMode
    results: list[TestResultInput] = Field(min_length=1, max_length=20_000)
    requiredTestTypes: list[str] = Field(default_factory=list, max_length=200)
    compatibilityLevel: CompatibilityLevel | None = None


class QualityGateResponse(BaseModel):
    profileId: str
    decision: Literal["PASS", "PASS_WITH_WARNING", "MANUAL_REVIEW", "FAIL", "BLOCKED"]
    passRatePercent: float
    counts: dict[str, int]
    blockers: list[str]
    warnings: list[str]
    releaseRecommended: bool
    humanApprovalRequired: bool
