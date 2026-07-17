from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class QATarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str | None = None
    name: str | None = None
    selector: str | None = None
    tagName: str | None = None


class QAEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    timestamp: int
    action: Literal["goto", "click", "fill", "select", "check"]
    url: HttpUrl
    target: QATarget | None = None
    value: str | None = Field(default=None, max_length=500)
    valueType: str | None = None
    redacted: bool


class QASession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str = Field(max_length=200)
    startedAt: str
    endedAt: str | None = None
    startUrl: HttpUrl
    recording: bool
    events: list[QAEvent] = Field(max_length=500)
    expectedFinalUrl: HttpUrl | None = None
    expectedPageTitle: str | None = Field(default=None, max_length=300)
    expectedHeadings: list[str] = Field(default_factory=list, max_length=20)


class GeneratedArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    playwright: str = Field(max_length=200_000)
    yaml: str = Field(max_length=200_000)


class EagleEyeBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schemaVersion: Literal["1.0"]
    source: Literal["orbit-assist", "eagleeye-extension"]
    createdAt: str
    session: QASession
    generated: GeneratedArtifacts


class SessionReceipt(BaseModel):
    session_id: str
    event_count: int
    stored: bool
    run_allowed: bool
    profile_id: str | None = None
    recommended_mode: str | None = None
    risk_score: int | None = None


class FailureAnalysis(BaseModel):
    category: str
    summary: str
    probable_cause: str
    recommended_action: str


class EvidenceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["screenshot", "video", "log", "trace"]
    path: str
    mime_type: str = Field(max_length=100)
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: str
    capture_source: str = Field(max_length=200)


class RunResult(BaseModel):
    session_id: str
    status: Literal["passed", "failed"]
    duration_ms: int
    screenshot: str | None = None
    evidence: list[EvidenceArtifact] = Field(default_factory=list)
    error: str | None = None
    analysis: FailureAnalysis | None = None


class CodexHandoff(BaseModel):
    session_id: str
    requires_approval: Literal[True] = True
    failure: FailureAnalysis
    evidence: list[str]
    instructions: list[str]
