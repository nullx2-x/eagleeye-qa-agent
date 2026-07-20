from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "profiles" / "default.yaml"


class RiskWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_impact: float = Field(ge=0, le=1)
    data_sensitivity: float = Field(ge=0, le=1)
    change_complexity: float = Field(ge=0, le=1)
    user_impact: float = Field(ge=0, le=1)
    recovery_difficulty: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_total(self) -> "RiskWeights":
        if abs(sum(self.model_dump().values()) - 1.0) > 0.0001:
            raise ValueError("Risk weights must total 1.0.")
        return self


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    development: int = Field(ge=0, le=100)
    standard: int = Field(ge=0, le=100)
    strict: int = Field(ge=0, le=100)
    release_gate: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_order(self) -> "Thresholds":
        values = [self.development, self.standard, self.strict, self.release_gate]
        if values != sorted(values):
            raise ValueError("Risk thresholds must be ordered.")
        return self


class Policy(BaseModel):
    model_config = ConfigDict(extra="allow")
    risk_weights: RiskWeights
    thresholds: Thresholds
    production: dict
    ai: dict
    quality_gate: dict


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    policy: Policy


def load_configuration(path: Path = DEFAULT_POLICY_PATH) -> Configuration:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Configuration.model_validate(payload)


configuration = load_configuration()
