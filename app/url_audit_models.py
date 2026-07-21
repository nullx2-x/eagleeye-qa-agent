from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from .test_case_models import TestCaseCheckResponse, TestCaseDefinition

AuditDecision = Literal["PASS", "PASS_WITH_WARNING", "BLOCKED"]
FindingSeverity = Literal["info", "low", "medium", "high"]
FindingStatus = Literal["PASS", "WARN", "INFO", "BLOCKED"]


class UrlAuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targetUrl: HttpUrl
    authorized: Literal[True]
    allowLocalhost: bool = False
    projectName: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def reject_credential_bearing_urls(self) -> "UrlAuditRequest":
        if self.targetUrl.username or self.targetUrl.password:
            raise ValueError("URL credentials are not accepted")
        if self.targetUrl.fragment:
            raise ValueError("URL fragments are not accepted")
        return self


class UrlAuditObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    method: Literal["GET", "HEAD", "OPTIONS"]
    url: str = Field(min_length=1, max_length=2_000)
    finalUrl: str | None = Field(default=None, max_length=2_000)
    statusCode: int | None = Field(default=None, ge=100, le=599)
    durationMs: int = Field(ge=0)
    responseHeaders: dict[str, str] = Field(default_factory=dict)
    redirectChain: list[str] = Field(default_factory=list, max_length=5)
    bodySha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    bodyBytes: int = Field(default=0, ge=0)
    truncated: bool = False
    tlsVersion: str | None = Field(default=None, max_length=40)
    error: str | None = Field(default=None, max_length=500)


class UrlAuditFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    category: Literal[
        "https",
        "security_headers",
        "cors",
        "discovery",
        "openapi",
        "login",
        "technology",
        "network",
    ]
    status: FindingStatus
    severity: FindingSeverity
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=1_000)
    evidence: list[str] = Field(default_factory=list, max_length=20)


class UrlAuditAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["robots", "sitemap", "security_txt", "openapi", "favicon", "login_hint"]
    url: str = Field(min_length=1, max_length=2_000)
    available: bool
    statusCode: int | None = Field(default=None, ge=100, le=599)
    detail: str | None = Field(default=None, max_length=500)


class UrlAuditProjectSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)
    auditId: str = Field(pattern=r"^[a-f0-9]{32}$")
    sourceUrl: str = Field(min_length=1, max_length=2_000)
    browserAgentStartUrl: str = Field(min_length=1, max_length=2_000)
    initialTestCases: list[TestCaseDefinition] = Field(min_length=1, max_length=30)
    caseQuality: TestCaseCheckResponse
    nextActions: list[str] = Field(min_length=1, max_length=20)


class UrlAuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auditId: str = Field(pattern=r"^[a-f0-9]{32}$")
    requestedUrl: str = Field(min_length=1, max_length=2_000)
    finalUrl: str | None = Field(default=None, max_length=2_000)
    authorized: Literal[True]
    localhostAllowed: bool
    startedAt: str
    completedAt: str
    decision: AuditDecision
    findings: list[UrlAuditFinding]
    observations: list[UrlAuditObservation]
    assets: list[UrlAuditAsset]
    technologies: list[str]
    project: UrlAuditProjectSeed | None = None
    reportJson: str
    reportMarkdown: str
