from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .models import QATarget, RunResult
from .strategy_models import QualityGateResponse
from .test_case_models import TestCaseCheckResponse


class BrowserControlSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=240)
    tagName: str = Field(max_length=40)
    selector: str | None = Field(default=None, max_length=500)
    testId: str | None = Field(default=None, max_length=200)
    disabled: bool = False


class BrowserDomSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pageTitle: str = Field(max_length=300)
    headings: list[str] = Field(default_factory=list, max_length=40)
    landmarks: list[str] = Field(default_factory=list, max_length=30)
    controls: list[BrowserControlSnapshot] = Field(default_factory=list, max_length=150)


class BrowserObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    timestamp: int = Field(ge=0)
    action: Literal["goto", "click", "fill", "select", "check", "snapshot"]
    url: HttpUrl
    target: QATarget | None = None
    valueType: str | None = Field(default=None, max_length=80)
    redacted: bool = False
    dom: BrowserDomSnapshot | None = None
    screenshotDataUrl: str | None = Field(default=None, max_length=4_500_000)


class BrowserSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=800)
    startUrl: HttpUrl
    locale: Literal["ja", "en"] = "ja"


class GeneratedBrowserTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=500)
    steps: list[str] = Field(min_length=1, max_length=40)
    expectedResults: list[str] = Field(min_length=1, max_length=40)
    assertions: list[str] = Field(min_length=1, max_length=40)
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    source: Literal["recording", "ai", "deterministic"]
    runnable: bool = False
    criticalFlow: bool = False


class BrowserAIResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(max_length=80)
    model: str = Field(max_length=200)
    available: bool
    fallbackUsed: bool
    message: str = Field(max_length=500)


BrowserSessionStatus = Literal["recording", "generated", "running", "passed", "failed"]


class BrowserAgentSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    name: str
    goal: str
    locale: Literal["ja", "en"]
    startUrl: HttpUrl
    createdAt: str
    updatedAt: str
    status: BrowserSessionStatus
    observations: list[BrowserObservation] = Field(default_factory=list, max_length=500)
    generatedCases: list[GeneratedBrowserTestCase] = Field(default_factory=list, max_length=20)
    ai: BrowserAIResult | None = None
    caseQuality: TestCaseCheckResponse | None = None
    run: RunResult | None = None
    qualityGate: QualityGateResponse | None = None
    fixSuggestions: list[str] = Field(default_factory=list, max_length=20)
    screenshotAvailable: bool = False
    replayCount: int = Field(default=0, ge=0)


class BrowserSessionSummary(BaseModel):
    id: str
    name: str
    goal: str
    startUrl: HttpUrl
    status: BrowserSessionStatus
    updatedAt: str
    caseCount: int
    observationCount: int
    screenshotAvailable: bool
    replayCount: int


class BrowserSessionList(BaseModel):
    sessions: list[BrowserSessionSummary]


class BrowserAgentStatus(BaseModel):
    status: Literal["ready"] = "ready"
    extensionOrigin: str
    selectedProvider: str
    providerConnected: bool
    setupGuidance: str
    demoTarget: str
    demoTargetReachable: bool
    capabilities: list[str]
