from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class FreshEvalAttestation(BaseModel):
    """Short-lived evaluator approval required before any automatic write."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["fresh-eval"] = "fresh-eval"
    issuer: Literal["eagleeye-evaluator"] = "eagleeye-evaluator"
    id: str = Field(min_length=16, max_length=200)
    projectId: str = Field(min_length=1, max_length=120)
    failureFingerprint: str = Field(pattern=SHA256_PATTERN)
    evidenceSha256: str = Field(pattern=SHA256_PATTERN)
    decision: Literal["eligible_for_repair"]
    issuedAt: datetime
    expiresAt: datetime

    @model_validator(mode="after")
    def validate_window(self) -> FreshEvalAttestation:
        if self.issuedAt.tzinfo is None or self.expiresAt.tzinfo is None:
            raise ValueError("Fresh evaluation timestamps must include a timezone")
        if self.expiresAt <= self.issuedAt:
            raise ValueError("Fresh evaluation expiry must follow issuance")
        return self


class RepairRequest(BaseModel):
    """API-safe request. The project root is resolved from the trusted registry."""

    model_config = ConfigDict(extra="forbid")

    projectId: str = Field(min_length=1, max_length=120)
    environment: Literal["local", "development", "staging", "production"] = "local"
    production: bool = False
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    requestedMode: Literal["proposal_only", "apply"] = "proposal_only"
    explicitApplyRequested: bool = False
    failureFingerprint: str = Field(pattern=SHA256_PATTERN)
    failureSummary: str = Field(min_length=1, max_length=4_000)
    evidencePaths: list[str] = Field(default_factory=list, max_length=50)
    attestation: FreshEvalAttestation | None = None

    @field_validator("evidencePaths")
    @classmethod
    def validate_evidence_paths(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or len(value) > 2_000 or "\x00" in value:
                raise ValueError("Evidence paths must be non-empty bounded strings")
        return values


class ExactReplacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old: str = Field(min_length=1, max_length=262_144)
    new: str = Field(max_length=262_144)

    @model_validator(mode="after")
    def require_change(self) -> ExactReplacement:
        if self.old == self.new:
            raise ValueError("Exact replacement must change text")
        return self


class FileRepair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["replace"] = "replace"
    path: str = Field(min_length=1, max_length=500)
    expectedSha256: str = Field(pattern=SHA256_PATTERN)
    replacements: list[ExactReplacement] = Field(min_length=1, max_length=100)


class RepairPlan(BaseModel):
    """Planner output. Delete, rename and free-form patches are unrepresentable."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(ge=0, le=1)
    files: list[FileRepair] = Field(min_length=1, max_length=5)

    @field_validator("files")
    @classmethod
    def unique_paths(cls, values: list[FileRepair]) -> list[FileRepair]:
        paths = [value.path.replace("\\", "/").casefold() for value in values]
        if len(paths) != len(set(paths)):
            raise ValueError("A repair plan may edit each file only once")
        return values


class RepairLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maxAttempts: int = Field(default=2, ge=1, le=2)
    maxFiles: int = Field(default=5, ge=1, le=5)
    maxChangedLines: int = Field(default=200, ge=1, le=200)
    maxTotalBytes: int = Field(default=262_144, ge=1, le=262_144)


class RepairPlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    request: RepairRequest
    projectRoot: Path
    attempt: int = Field(ge=1, le=2)
    limits: RepairLimits
    previousFailures: list[str] = Field(default_factory=list, max_length=2)


class VerificationCommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    argv: list[str]
    returnCode: int | None = None
    timedOut: bool = False
    durationMs: int = Field(ge=0)
    stdout: str = ""
    stderr: str = ""


class RepairAttemptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int
    status: Literal[
        "PLAN_REJECTED",
        "PROPOSED",
        "VERIFICATION_FAILED",
        "ROLLED_BACK",
        "APPLIED",
        "FAILED",
    ]
    reason: str = ""
    changedFiles: list[str] = Field(default_factory=list)
    changedLines: int = 0
    totalBytes: int = 0
    preimageSha256: dict[str, str] = Field(default_factory=dict)
    postimageSha256: dict[str, str] = Field(default_factory=dict)
    checkpointPath: str | None = None
    rollbackVerified: bool | None = None
    verification: list[VerificationCommandResult] = Field(default_factory=list)


class RepairResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: str
    projectId: str
    requestedMode: Literal["proposal_only", "apply"]
    effectiveMode: Literal["proposal_only", "apply", "denied"]
    status: Literal["DENIED", "PROPOSED", "APPLIED", "FAILED", "ROLLED_BACK"]
    reasons: list[str] = Field(default_factory=list)
    plan: RepairPlan | None = None
    attempts: list[RepairAttemptRecord] = Field(default_factory=list)
    auditPath: str
    auditSha256: str


class RepairCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    models: list[str] = Field(min_length=1)
    proposalAllowed: bool = True
    automaticApplyAllowed: bool = False
    requiresFreshEvalAttestation: bool = True
    maxAttestationAgeSeconds: int = Field(default=300, ge=1, le=900)

    @model_validator(mode="after")
    def automatic_apply_requires_attestation(self) -> RepairCapability:
        if self.automaticApplyAllowed and not self.requiresFreshEvalAttestation:
            raise ValueError("Automatic repair requires fresh evaluation attestation")
        return self


class RepairCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    featureFlag: Literal["EAGLEEYE_SELF_REPAIR_ENABLED"]
    allowedEnvironments: list[Literal["local"]] = Field(default_factory=lambda: ["local"])
    productionAllowed: Literal[False] = False
    limits: RepairLimits = Field(default_factory=RepairLimits)
    capabilities: list[RepairCapability] = Field(min_length=1)

    @field_validator("capabilities")
    @classmethod
    def unique_provider_models(cls, values: list[RepairCapability]) -> list[RepairCapability]:
        pairs = [(capability.provider, model) for capability in values for model in capability.models]
        if len(pairs) != len(set(pairs)):
            raise ValueError("Repair provider/model allowlist entries must be unique")
        return values


class VerificationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    argv: list[str] = Field(min_length=1, max_length=50)
    timeoutSeconds: int = Field(default=300, ge=1, le=1_800)

    @field_validator("argv")
    @classmethod
    def bounded_argv(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 4_000 or "\x00" in value for value in values):
            raise ValueError("Verification argv entries must be non-empty bounded strings")
        return values


class RepairProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    root: Path
    enabled: bool = True
    allowedEnvironments: list[Literal["local"]] = Field(default_factory=lambda: ["local"])
    verification: list[VerificationCommand] = Field(min_length=1, max_length=20)


class RepairProjects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    projects: list[RepairProject]

    @field_validator("projects")
    @classmethod
    def unique_projects(cls, values: list[RepairProject]) -> list[RepairProject]:
        ids = [value.id for value in values]
        roots = [str(value.root).casefold() for value in values]
        if len(ids) != len(set(ids)) or len(roots) != len(set(roots)):
            raise ValueError("Repair project ids and roots must be unique")
        return values
