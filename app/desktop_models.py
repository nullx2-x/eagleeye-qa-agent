from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import EvidenceArtifact

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$"


class DesktopRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    targetId: str = Field(pattern=IDENTIFIER_PATTERN)
    runId: str = Field(pattern=IDENTIFIER_PATTERN)

    @property
    def target_id(self) -> str:
        return self.targetId

    @property
    def run_id(self) -> str:
        return self.runId


class DesktopTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    root: Path
    working_directory: Path = Field(alias="workingDirectory")
    command: list[str] = Field(min_length=1, max_length=16)
    timeout_seconds: float = Field(default=180, alias="timeoutSeconds", ge=0.1, le=900)
    max_output_bytes: int = Field(default=262_144, alias="maxOutputBytes", ge=1024, le=1_048_576)
    max_artifacts: int = Field(default=12, alias="maxArtifacts", ge=1, le=20)
    max_artifact_bytes: int = Field(
        default=268_435_456,
        alias="maxArtifactBytes",
        ge=1,
        le=1_073_741_824,
    )

    @model_validator(mode="after")
    def validate_command_strings(self) -> DesktopTarget:
        for argument in self.command:
            invalid = (
                not argument
                or len(argument) > 1000
                or "\0" in argument
                or "\n" in argument
                or "\r" in argument
            )
            if invalid:
                raise ValueError("Desktop command contains an invalid argument.")
        return self


class DesktopTargetRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["1.0"]
    targets: dict[str, DesktopTarget]

    @model_validator(mode="after")
    def validate_target_ids(self) -> DesktopTargetRegistry:
        for target_id in self.targets:
            if re.fullmatch(IDENTIFIER_PATTERN, target_id) is None:
                raise ValueError("Desktop registry contains an invalid target id.")
        return self


class DesktopArtifactDeclaration(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: Literal["screenshot", "video", "log", "trace"]
    path: str = Field(min_length=1, max_length=2000)


class DesktopCommandPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["passed", "failed"] | None = None
    ok: bool | None = None
    summary: str | None = Field(default=None, max_length=2000)
    artifacts: list[DesktopArtifactDeclaration] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def require_outcome(self) -> DesktopCommandPayload:
        if self.status is None and self.ok is None:
            raise ValueError("Desktop command payload must contain status or ok.")
        return self

    @property
    def passed(self) -> bool:
        if self.status is not None:
            return self.status == "passed"
        return self.ok is True


class DesktopRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    target_id: str = Field(alias="targetId")
    run_id: str = Field(alias="runId")
    status: Literal["passed", "failed"]
    evidence: list[EvidenceArtifact] = Field(default_factory=list)
    exit_code: int | None = Field(default=None, alias="exitCode")
    duration_ms: int = Field(alias="durationMs", ge=0)
    stdout: str = ""
    stderr: str = ""
    summary: str | None = None
    error: str | None = None
    timed_out: bool = Field(default=False, alias="timedOut")
