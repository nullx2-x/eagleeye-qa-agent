from app.configuration import load_configuration
from app.quality import evaluate_quality_gate
from app.strategy import calculate_risk, generate_profile
from app.strategy_models import ProfileRequest, QualityGateRequest
from app.strategy_models import TestMode as Mode


def request(**overrides) -> ProfileRequest:
    payload = {
        "projectId": "checkout",
        "developmentStage": "development",
        "serviceType": "ecommerce",
        "changedFiles": [],
        "risk": {
            "business_impact": "medium",
            "data_sensitivity": "medium",
            "change_complexity": "medium",
            "user_impact": "medium",
            "recoverability": "medium",
        },
        "aiEnabled": False,
    }
    payload.update(overrides)
    return ProfileRequest.model_validate(payload)


def test_default_yaml_policy_is_valid() -> None:
    policy = load_configuration()
    assert sum(policy.policy.risk_weights.model_dump().values()) == 1.0
    assert policy.policy.thresholds.release_gate == 85


def test_risk_score_uses_recoverability_as_inverse_risk() -> None:
    recoverable = request(
        risk={
            "business_impact": "medium",
            "data_sensitivity": "medium",
            "change_complexity": "medium",
            "user_impact": "medium",
            "recoverability": "critical",
        }
    )
    hard_to_recover = request(
        risk={
            "business_impact": "medium",
            "data_sensitivity": "medium",
            "change_complexity": "medium",
            "user_impact": "medium",
            "recoverability": "low",
        }
    )
    assert calculate_risk(hard_to_recover) > calculate_risk(recoverable)


def test_auth_change_forces_strict_full_regression() -> None:
    profile = generate_profile(request(changedFiles=["src/auth/session.py"], requestedMode="quick"))
    assert profile.recommendedMode is Mode.STRICT
    assert profile.fullRegressionRequired is True
    assert "regression-full" in profile.requiredTests
    assert any("安全フロア" in reason for reason in profile.reasons)


def test_production_is_forced_to_read_only() -> None:
    profile = generate_profile(
        request(developmentStage="production", production=True, requestedMode="strict")
    )
    assert profile.recommendedMode is Mode.PRODUCTION_SAFE
    assert all(selection.intensity == "read_only" for selection in profile.selections)
    assert "書き込み操作禁止" in profile.restrictions


def test_ai_agent_profile_includes_safety_evals() -> None:
    profile = generate_profile(request(serviceType="ai_agent"))
    assert "prompt-injection" in profile.requiredTests
    assert "human-approval" in profile.requiredTests
    assert "ai-safety-regression" in profile.requiredTests


def test_emulator_cycle_profile_has_cumulative_compatibility_floor() -> None:
    profile = generate_profile(
        request(
            serviceType="emulator",
            compatibilityLevel="cycle",
            changedFiles=["src/vr4300_pipeline.cpp"],
            aiEnabled=True,
        )
    )
    assert profile.compatibilityLevel.value == "cycle"
    assert profile.recommendedMode is Mode.RELEASE_GATE
    assert profile.fullRegressionRequired is True
    assert "instruction-conformance" in profile.requiredTests
    assert "rom-matrix" in profile.requiredTests
    assert "cycle-trace" in profile.requiredTests
    assert "sysad-protocol" in profile.requiredTests
    assert "office-bitness" not in profile.requiredTests
    assert "llm-schema" not in profile.requiredTests
    assert "第三者のROM・PIF・ファームウェアを成果物へ同梱しない" in profile.restrictions


def test_emulator_defaults_to_functional_compatibility() -> None:
    profile = generate_profile(request(serviceType="emulator"))
    assert profile.compatibilityLevel.value == "functional"
    assert "instruction-conformance" in profile.requiredTests
    assert "cycle-trace" not in profile.requiredTests


def test_quality_gate_blocks_critical_failure() -> None:
    gate = evaluate_quality_gate(
        QualityGateRequest.model_validate(
            {
                "profileId": "profile-1",
                "mode": "release_gate",
                "results": [
                    {
                        "testId": "checkout",
                        "testType": "e2e",
                        "status": "FAILED",
                        "severity": "critical",
                        "criticalFlow": True,
                    },
                    {"testId": "unit", "testType": "unit", "status": "PASSED"},
                ],
            }
        )
    )
    assert gate.decision == "FAIL"
    assert gate.releaseRecommended is False
    assert gate.blockers


def test_quality_gate_keeps_flaky_separate() -> None:
    gate = evaluate_quality_gate(
        QualityGateRequest.model_validate(
            {
                "profileId": "profile-2",
                "mode": "strict",
                "results": [
                    {"testId": "unit", "testType": "unit", "status": "PASSED"},
                    {"testId": "timing", "testType": "e2e", "status": "FLAKY"},
                ],
            }
        )
    )
    assert gate.decision in {"FAIL", "MANUAL_REVIEW"}
    assert gate.counts["FLAKY"] == 1


def test_cycle_gate_blocks_missing_compatibility_tests() -> None:
    gate = evaluate_quality_gate(
        QualityGateRequest.model_validate(
            {
                "profileId": "profile-cycle",
                "mode": "release_gate",
                "compatibilityLevel": "cycle",
                "results": [
                    {
                        "testId": "isa",
                        "testType": "instruction-conformance",
                        "status": "PASSED",
                        "mismatchCount": 0,
                        "coveragePercent": 100,
                        "sampleCount": 1,
                        "evidencePath": "artifacts/isa.json",
                        "evidenceSha256": "a" * 64,
                    }
                ],
            }
        )
    )
    assert gate.decision == "FAIL"
    assert any("必須テスト種別が未提出" in blocker for blocker in gate.blockers)


def test_functional_gate_rejects_nonzero_differential_mismatch() -> None:
    results = []
    for test_type in (
        "instruction-conformance",
        "differential-oracle",
        "exception-conformance",
        "cp0-conformance",
        "tlb-conformance",
        "fpu-conformance",
        "cache-coherency",
        "deterministic-replay",
    ):
        result = {
            "testId": test_type,
            "testType": test_type,
            "status": "PASSED",
            "mismatchCount": 1 if test_type == "differential-oracle" else 0,
            "sampleCount": 10,
            "evidencePath": f"artifacts/{test_type}.json",
            "evidenceSha256": "b" * 64,
        }
        if test_type not in {"differential-oracle", "deterministic-replay"}:
            result["coveragePercent"] = 100
        if test_type == "differential-oracle":
            result["oracle"] = "Unicorn MIPS64"
        if test_type == "deterministic-replay":
            result["deterministic"] = True
        results.append(result)
    gate = evaluate_quality_gate(
        QualityGateRequest.model_validate(
            {
                "profileId": "profile-functional",
                "mode": "release_gate",
                "compatibilityLevel": "functional",
                "results": results,
            }
        )
    )
    assert gate.decision == "FAIL"
    assert any("差分 1件" in blocker for blocker in gate.blockers)
