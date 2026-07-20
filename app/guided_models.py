from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .strategy_models import QualityGateResponse, Severity, TestMode

GuidedStepKind = Literal["manual", "hybrid", "telemetry"]
GuidedStepStatus = Literal[
    "PENDING",
    "ACTIVE",
    "PAUSED",
    "AWAITING_FEEDBACK",
    "PASSED",
    "FAILED",
    "BLOCKED",
]
GuidedSessionStatus = Literal[
    "PREPARED",
    "READY",
    "RUNNING",
    "PAUSED",
    "AWAITING_FEEDBACK",
    "STEP_COMPLETE",
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "ABORTED",
]


class GuidedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    text: str = Field(min_length=1, max_length=1_000)


class GuidedMedia(BaseModel):
    """Optional image shown with a step. Local assets stay inside data/guided/assets."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["url", "local_asset"]
    src: str = Field(min_length=1, max_length=2_000)
    alt: str = Field(default="テスト操作の参考画像", max_length=500)

    @model_validator(mode="after")
    def validate_source(self) -> GuidedMedia:
        if self.source == "url":
            parsed = urlparse(self.src)
            loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            if (
                not parsed.netloc
                or parsed.username
                or parsed.password
                or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback))
            ):
                raise ValueError("URL media must use https, or http on loopback without credentials")
        else:
            normalized = self.src.replace("\\", "/")
            path = PurePosixPath(normalized)
            if path.is_absolute() or ".." in path.parts or normalized.startswith("/"):
                raise ValueError("local_asset must be a relative path without '..'")
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                raise ValueError("local_asset must be a supported image file")
            self.src = normalized
        return self


class GuidedVisualMarker(BaseModel):
    """A normalized overlay. Coordinates are fractions of the media/stage surface."""

    model_config = ConfigDict(extra="forbid")

    shape: Literal["rect", "circle", "arrow", "point"]
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float | None = Field(default=None, ge=0, le=1)
    height: float | None = Field(default=None, ge=0, le=1)
    toX: float | None = Field(default=None, ge=0, le=1)
    toY: float | None = Field(default=None, ge=0, le=1)
    label: str = Field(default="", max_length=300)
    color: str = Field(
        default="#38d7c4",
        pattern=r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$",
    )

    @model_validator(mode="after")
    def validate_shape_fields(self) -> GuidedVisualMarker:
        if self.shape in {"rect", "circle"} and (self.width is None or self.height is None):
            raise ValueError(f"{self.shape} marker requires width and height")
        if (
            self.shape in {"rect", "circle"}
            and self.width is not None
            and self.height is not None
            and (self.x + self.width > 1 or self.y + self.height > 1)
        ):
            raise ValueError("rect/circle marker must stay inside the normalized surface")
        if self.shape == "arrow" and (self.toX is None or self.toY is None):
            raise ValueError("arrow marker requires toX and toY")
        return self


class GuidedGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4_000)
    hint: str = Field(default="", max_length=2_000)
    media: GuidedMedia | None = None
    markers: list[GuidedVisualMarker] = Field(default_factory=list, max_length=50)


class GuidedTelemetryPredicate(BaseModel):
    """Generic predicate over an observation document (for example values.ready)."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=300, pattern=r"^[A-Za-z0-9_.-]+$")
    operator: Literal["eq", "ne", "in", "not_in", "gte", "lte", "contains", "exists"] = "eq"
    value: Any = None


class GuidedTelemetryOracle(BaseModel):
    """Optional product adapter contract; it contains no product-specific fields."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="structured-telemetry", min_length=1, max_length=200)
    minObservations: int = Field(default=1, ge=1, le=100_000)
    minObservationMs: int = Field(default=0, ge=0, le=3_600_000)
    predicates: list[GuidedTelemetryPredicate] = Field(default_factory=list, max_length=100)
    minMatchingObservations: int = Field(default=1, ge=0, le=100_000)
    minConsecutiveMatches: int = Field(default=0, ge=0, le=100_000)
    maxMismatches: int = Field(default=100_000, ge=0, le=100_000)
    requiredEvents: dict[str, int] = Field(default_factory=dict)
    exactEventCounts: dict[str, int] = Field(default_factory=dict)
    maxEventCounts: dict[str, int] = Field(default_factory=dict)
    forbiddenEvents: list[str] = Field(default_factory=list, max_length=100)
    settleWindowMs: int = Field(default=0, ge=0, le=600_000)
    maxP95LatencyMs: float | None = Field(default=None, gt=0, le=60_000)
    maxDropDelta: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator("requiredEvents", "exactEventCounts", "maxEventCounts")
    @classmethod
    def validate_event_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if len(value) > 100:
            raise ValueError("At most 100 required events are allowed")
        if any(not name or len(name) > 120 or count < 0 for name, count in value.items()):
            raise ValueError("Event counts require short names and non-negative counts")
        return value

    @model_validator(mode="after")
    def validate_event_contract(self) -> GuidedTelemetryOracle:
        if (self.exactEventCounts or self.maxEventCounts) and self.settleWindowMs <= 0:
            raise ValueError("exactEventCounts/maxEventCounts require a positive settleWindowMs")
        for name, minimum in self.requiredEvents.items():
            exact = self.exactEventCounts.get(name)
            maximum = self.maxEventCounts.get(name)
            if exact is not None and exact < minimum:
                raise ValueError(f"exactEventCounts.{name} cannot be below requiredEvents")
            if maximum is not None and maximum < minimum:
                raise ValueError(f"maxEventCounts.{name} cannot be below requiredEvents")
        for name, exact in self.exactEventCounts.items():
            maximum = self.maxEventCounts.get(name)
            if maximum is not None and exact > maximum:
                raise ValueError(f"exactEventCounts.{name} cannot exceed maxEventCounts")
        positive_events = {
            name
            for counts in (self.requiredEvents, self.exactEventCounts)
            for name, count in counts.items()
            if count > 0
        }
        conflicts = sorted(positive_events.intersection(self.forbiddenEvents))
        if conflicts:
            raise ValueError("forbiddenEvents conflict with positive event counts: " + ", ".join(conflicts))
        return self


class GuidedScenarioStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    kind: GuidedStepKind
    title: str = Field(min_length=1, max_length=300)
    guidance: GuidedGuidance
    preparation: str = Field(default="画面の指示に従い、準備ができたら開始してください。", max_length=2_000)
    expected: str = Field(min_length=1, max_length=2_000)
    requirementIds: list[str] = Field(default_factory=list, max_length=100)
    testType: str = Field(default="guided-user", min_length=1, max_length=100)
    severity: Severity = "high"
    criticalFlow: bool = True
    timeoutMs: int = Field(default=60_000, ge=1_000, le=3_600_000)
    countdownSeconds: int = Field(default=3, ge=0, le=10)
    requiredConditions: list[str] = Field(default_factory=list, max_length=30)
    verdictAuthority: Literal["user", "observer", "either"] = "user"
    feedbackRequired: bool = False
    telemetryOracle: GuidedTelemetryOracle | None = None

    @model_validator(mode="after")
    def validate_kind(self) -> GuidedScenarioStep:
        if self.kind in {"hybrid", "telemetry"} and self.telemetryOracle is None:
            raise ValueError(f"{self.kind} steps require telemetryOracle")
        if self.kind == "manual" and self.feedbackRequired:
            raise ValueError("manual steps already require a manual verdict")
        if (
            self.telemetryOracle is not None
            and self.telemetryOracle.minObservationMs + self.telemetryOracle.settleWindowMs > self.timeoutMs
        ):
            raise ValueError("minObservationMs + settleWindowMs cannot exceed timeoutMs")
        return self


class GuidedScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal["1.0"] = "1.0"
    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    projectId: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4_000)
    version: str = Field(default="1.0.0", min_length=1, max_length=40)
    targetSource: str = Field(min_length=1, max_length=200)
    safetyNotice: str = Field(min_length=1, max_length=2_000)
    privacyNotice: str = Field(min_length=1, max_length=2_000)
    requirements: list[GuidedRequirement] = Field(default_factory=list, max_length=500)
    steps: list[GuidedScenarioStep] = Field(min_length=1, max_length=500)
    gateMode: TestMode = TestMode.STANDARD

    @field_validator("requirements")
    @classmethod
    def unique_requirements(cls, value: list[GuidedRequirement]) -> list[GuidedRequirement]:
        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Requirement ids must be unique")
        return value

    @model_validator(mode="after")
    def validate_steps(self) -> GuidedScenarioDefinition:
        ids = [item.id for item in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step ids must be unique")
        requirement_ids = {item.id for item in self.requirements}
        unknown = sorted({item for step in self.steps for item in step.requirementIds} - requirement_ids)
        if unknown:
            raise ValueError(f"Unknown requirementIds: {', '.join(unknown)}")
        return self


class GuidedSessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenarioId: str = Field(min_length=1, max_length=120)
    operatorAlias: str = Field(default="local-operator", min_length=1, max_length=120)
    observerAlias: str | None = Field(default=None, max_length=120)
    selectedStepIds: list[str] = Field(default_factory=list, max_length=500)
    parentSessionId: str | None = Field(default=None, max_length=120)


class GuidedObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    sequence: int = Field(ge=0)
    timestampMs: int = Field(ge=0)
    source: str = Field(min_length=1, max_length=120)
    kind: Literal["sample", "event", "system", "heartbeat"]
    event: str | None = Field(default=None, max_length=120)
    values: dict[str, Any] = Field(default_factory=dict)
    latencyMs: float | None = Field(default=None, ge=0, le=60_000)
    drops: int = Field(default=0, ge=0)
    dryRun: bool | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def event_has_name(self) -> GuidedObservation:
        if self.kind == "event" and not self.event:
            raise ValueError("event observations require an event name")
        return self


class GuidedObservationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[GuidedObservation] = Field(min_length=1, max_length=500)


class GuidedObservationReceipt(BaseModel):
    sessionId: str
    accepted: int
    duplicates: int
    revision: int
    status: GuidedSessionStatus


class GuidedManualVerdict(BaseModel):
    """Human evidence. A passing user verdict is explicitly self-reported, never telemetry."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["passed", "failed", "blocked"]
    reporterRole: Literal["user", "observer"] = "user"
    difficultyRating: int = Field(default=3, ge=1, le=5)
    confidenceRating: int = Field(default=3, ge=1, le=5)
    notes: str = Field(default="", max_length=4_000)


# Backward-compatible import name for the existing /feedback endpoint.
GuidedFeedback = GuidedManualVerdict


class GuidedControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "activate", "next", "retry", "pause", "resume", "block", "abort"]
    confirmedConditions: list[str] = Field(default_factory=list, max_length=30)
    reason: str | None = Field(default=None, max_length=2_000)
    expectedRevision: int | None = Field(default=None, ge=0)


class GuidedStepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stepId: str
    kind: GuidedStepKind
    status: GuidedStepStatus = "PENDING"
    attempt: int = 1
    startedAtMs: int | None = None
    endedAtMs: int | None = None
    pausedAtMs: int | None = None
    accumulatedPauseMs: int = 0
    durationMs: int = 0
    observationCount: int = 0
    matchingObservations: int = 0
    mismatches: int = 0
    consecutiveMatches: int = 0
    peakConsecutiveMatches: int = 0
    eventCounts: dict[str, int] = Field(default_factory=dict)
    latencySamplesMs: list[float] = Field(default_factory=list, max_length=20_000)
    p95LatencyMs: float | None = None
    initialDrops: int | None = None
    dropDelta: int = 0
    observationIds: list[str] = Field(default_factory=list, max_length=100_000)
    confirmedConditions: list[str] = Field(default_factory=list)
    manualVerdict: GuidedManualVerdict | None = None
    telemetrySatisfied: bool = False
    settleStartedAtMs: int | None = None
    settleDeadlineMs: int | None = None
    evidenceClass: Literal["UNKNOWN", "SELF_REPORTED", "OBSERVER_REPORTED", "TELEMETRY", "HYBRID"] = "UNKNOWN"
    failureCodes: list[str] = Field(default_factory=list)
    verdictReasons: list[str] = Field(default_factory=list)
    correctionSuggestions: list[str] = Field(default_factory=list)
    evidencePath: str | None = None
    evidenceSha256: str | None = None


class GuidedSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    scenarioId: str
    projectId: str
    operatorAlias: str
    observerAlias: str | None = None
    selectedStepIds: list[str]
    parentSessionId: str | None = None
    attempt: int = 1
    status: GuidedSessionStatus = "PREPARED"
    scenarioSha256: str
    approvedAtMs: int | None = None
    currentStepIndex: int = 0
    createdAtMs: int
    updatedAtMs: int
    lastObservationAtMs: int | None = None
    revision: int = 0
    results: list[GuidedStepResult]
    gate: QualityGateResponse | None = None
    retestSessionId: str | None = None
    reportPath: str | None = None
    reportSha256: str | None = None
    sessionEvidencePath: str | None = None
    sessionEvidenceSha256: str | None = None


class GuidedSessionReceipt(BaseModel):
    session: GuidedSession
    runnerUrl: str
    telemetryEndpoint: str
