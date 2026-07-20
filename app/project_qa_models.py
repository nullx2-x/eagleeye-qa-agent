from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .strategy_models import QualityGateResponse, TestMode

SuiteStatus = Literal["PASSED", "FAILED", "BLOCKED", "SKIPPED", "INFRA_ERROR"]


class ProjectSuiteDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=200)
    testType: str = Field(min_length=1, max_length=100)
    command: list[str] = Field(min_length=1, max_length=40)
    source: Literal["detected", "manifest"] = "detected"
    required: bool = True


class ProjectDiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectRoot: str = Field(min_length=1, max_length=2_000)
    authorized: Literal[True]


class ProjectDiscoveryResponse(BaseModel):
    projectId: str
    projectRoot: str
    rootFingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    ecosystems: list[str]
    suites: list[ProjectSuiteDefinition]
    warnings: list[str]


class ProjectRunRequest(ProjectDiscoveryRequest):
    suiteIds: list[str] = Field(default_factory=list, max_length=200)
    mode: TestMode = TestMode.DEVELOPMENT
    failFast: bool = False
    timeoutSeconds: int = Field(default=900, ge=5, le=3_600)


class ProjectSuiteResult(BaseModel):
    id: str
    name: str
    testType: str
    status: SuiteStatus
    exitCode: int | None = None
    durationMs: int = Field(ge=0)
    command: list[str]
    errorMessage: str | None = Field(default=None, max_length=4_000)
    evidencePath: str
    evidenceSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidenceBytes: int = Field(ge=0)


class ProjectRunReport(BaseModel):
    runId: str = Field(pattern=r"^[a-f0-9]{32}$")
    projectId: str
    projectRoot: str
    startedAt: str
    completedAt: str
    status: Literal["PASS", "FAIL", "BLOCKED"]
    results: list[ProjectSuiteResult]
    qualityGate: QualityGateResponse
    reportJson: str
    reportMarkdown: str
