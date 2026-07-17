from collections import Counter

from .compatibility import FULL_COVERAGE_TESTS, compatibility_tests
from .strategy_models import QualityGateRequest, QualityGateResponse, TestMode


def evaluate_quality_gate(request: QualityGateRequest) -> QualityGateResponse:
    counts = Counter(result.status for result in request.results)
    eligible = [result for result in request.results if result.status not in {"SKIPPED", "NOT_APPLICABLE"}]
    passed = sum(result.status == "PASSED" for result in eligible)
    pass_rate = round((passed / len(eligible)) * 100, 2) if eligible else 0.0
    blockers: list[str] = []
    warnings: list[str] = []

    result_types = {result.testType for result in request.results}
    compatibility_required = set(compatibility_tests(request.compatibilityLevel))
    required_types = set(request.requiredTestTypes)
    required_types.update(compatibility_required)
    missing_types = sorted(required_types - result_types)
    if missing_types:
        blockers.append(f"必須テスト種別が未提出: {', '.join(missing_types)}")

    critical_failures = [r for r in request.results if r.status == "FAILED" and r.severity == "critical"]
    high_failures = [r for r in request.results if r.status == "FAILED" and r.severity == "high"]
    critical_flow_failures = [r for r in request.results if r.criticalFlow and r.status != "PASSED"]
    if critical_failures:
        blockers.append(f"Critical失敗: {len(critical_failures)}件")
    if high_failures:
        blockers.append(f"High失敗: {len(high_failures)}件")
    if critical_flow_failures:
        blockers.append(f"主要フロー未成功: {len(critical_flow_failures)}件")
    if counts["BLOCKED"] or counts["INFRA_ERROR"]:
        blockers.append("テスト実行を妨げるBLOCKED/INFRA_ERRORが存在")
    if counts["FLAKY"]:
        warnings.append(f"フレークテスト: {counts['FLAKY']}件")

    strict_evidence = request.mode in {TestMode.STRICT, TestMode.RELEASE_GATE}
    compatibility_results = [
        result for result in request.results if result.testType in compatibility_required
    ]
    for result in compatibility_results:
        if result.status != "PASSED":
            continue
        prefix = f"{result.testType}/{result.testId}"
        if result.mismatchCount is None:
            blockers.append(f"{prefix}: mismatchCount証跡がない")
        elif result.mismatchCount != 0:
            blockers.append(f"{prefix}: 差分 {result.mismatchCount}件")
        if result.sampleCount is None or result.sampleCount <= 0:
            blockers.append(f"{prefix}: sampleCount証跡がない")
        if result.testType in FULL_COVERAGE_TESTS:
            if result.coveragePercent is None:
                blockers.append(f"{prefix}: coveragePercent証跡がない")
            elif result.coveragePercent < 100:
                blockers.append(f"{prefix}: カバレッジ {result.coveragePercent}% は100%未満")
        if strict_evidence and (not result.evidencePath or not result.evidenceSha256):
            blockers.append(f"{prefix}: パスとSHA-256を含む証跡がない")
        if result.testType == "differential-oracle" and not result.oracle:
            blockers.append(f"{prefix}: 独立オラクルが指定されていない")
        if result.testType == "deterministic-replay" and result.deterministic is not True:
            blockers.append(f"{prefix}: 決定論的再実行が証明されていない")

    minimum = 98.0 if request.mode in {TestMode.STRICT, TestMode.RELEASE_GATE} else 90.0
    if pass_rate < minimum:
        blockers.append(f"成功率 {pass_rate}% は基準 {minimum}% 未満")

    if blockers:
        decision = "BLOCKED" if counts["BLOCKED"] or counts["INFRA_ERROR"] else "FAIL"
    elif counts["FLAKY"] and request.mode in {TestMode.STRICT, TestMode.RELEASE_GATE}:
        decision = "MANUAL_REVIEW"
    elif warnings:
        decision = "PASS_WITH_WARNING"
    else:
        decision = "PASS"
    manual = decision == "MANUAL_REVIEW" or request.mode is TestMode.RELEASE_GATE
    release_recommended = decision == "PASS" and not manual
    return QualityGateResponse(
        profileId=request.profileId,
        decision=decision,
        passRatePercent=pass_rate,
        counts=dict(counts),
        blockers=blockers,
        warnings=warnings,
        releaseRecommended=release_recommended,
        humanApprovalRequired=manual,
    )
