from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IssueSeverity = Literal["critical", "high", "medium", "low", "info"]
CaseStatus = Literal["PASS", "WARNING", "FAIL"]


class TestCaseDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    type: str = Field(default="functional", min_length=1, max_length=80)
    preconditions: list[str] = Field(default_factory=list, max_length=100)
    steps: list[str] = Field(min_length=1, max_length=200)
    expectedResults: list[str] = Field(default_factory=list, max_length=200)
    assertions: list[str] = Field(default_factory=list, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=100)
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    criticalFlow: bool = False
    timeoutMs: int = Field(default=30_000, ge=100, le=3_600_000)
    retryCount: int = Field(default=0, ge=0, le=10)


class TestCaseCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    projectId: str = Field(min_length=1, max_length=100)
    cases: list[TestCaseDefinition] = Field(min_length=1, max_length=500)
    requiredTestTypes: list[str] = Field(default_factory=list, max_length=100)


class TestCaseIssue(BaseModel):
    code: str
    severity: IssueSeverity
    testCaseIds: list[str]
    message: str
    suggestion: str


class TestCaseScore(BaseModel):
    id: str
    title: str
    score: int
    status: CaseStatus
    issueCount: int


class TestCaseCheckResponse(BaseModel):
    projectId: str
    decision: Literal["PASS", "PASS_WITH_WARNING", "FAIL"]
    score: int
    counts: dict[str, int]
    issues: list[TestCaseIssue]
    cases: list[TestCaseScore]
    coverage: dict[str, list[str]]
    checkedAt: str
