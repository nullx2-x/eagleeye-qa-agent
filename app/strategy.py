import json
from pathlib import Path
from uuid import uuid4

from .compatibility import compatibility_tests
from .configuration import configuration
from .strategy_models import (
    CompatibilityLevel,
    DevelopmentStage,
    ProfileRequest,
    ProfileResponse,
    ServiceType,
    TestMode,
    TestSelection,
)

LEVEL_SCORE = {"low": 0, "medium": 35, "high": 70, "critical": 100}
RECOVERABILITY_RISK = {"low": 100, "medium": 65, "high": 30, "critical": 0}
MODE_RANK = {
    TestMode.QUICK: 0,
    TestMode.DEVELOPMENT: 1,
    TestMode.INTEGRATION: 2,
    TestMode.STANDARD: 3,
    TestMode.MAINTENANCE: 3,
    TestMode.STRICT: 4,
    TestMode.RELEASE_GATE: 5,
    TestMode.PRODUCTION_SAFE: 5,
    TestMode.EXPLORATORY_AI: 2,
}
STAGE_MODE = {
    DevelopmentStage.PLANNING: TestMode.QUICK,
    DevelopmentStage.POC: TestMode.QUICK,
    DevelopmentStage.DEVELOPMENT: TestMode.DEVELOPMENT,
    DevelopmentStage.INTEGRATION: TestMode.INTEGRATION,
    DevelopmentStage.SYSTEM_TEST: TestMode.STANDARD,
    DevelopmentStage.RELEASE: TestMode.RELEASE_GATE,
    DevelopmentStage.PRODUCTION: TestMode.PRODUCTION_SAFE,
    DevelopmentStage.MAINTENANCE: TestMode.MAINTENANCE,
}
MODE_TESTS = {
    TestMode.QUICK: ["smoke", "unit-changed", "api-critical", "e2e-critical", "security-basic"],
    TestMode.DEVELOPMENT: ["lint", "type-check", "unit", "component", "api", "dependency-scan"],
    TestMode.INTEGRATION: ["unit", "integration", "contract", "api", "database", "e2e-critical"],
    TestMode.STANDARD: [
        "unit",
        "integration",
        "api",
        "contract",
        "e2e",
        "accessibility",
        "visual",
        "performance-smoke",
        "security-standard",
    ],
    TestMode.STRICT: [
        "unit-full",
        "integration-full",
        "e2e-full",
        "security-strict",
        "performance",
        "resilience",
        "compatibility",
        "backup-restore",
        "rollback",
    ],
    TestMode.RELEASE_GATE: [
        "acceptance",
        "regression-full",
        "security-gate",
        "performance-gate",
        "migration-rehearsal",
        "deployment",
        "rollback",
        "monitoring",
    ],
    TestMode.PRODUCTION_SAFE: [
        "healthcheck",
        "read-only-smoke",
        "synthetic-monitoring",
        "certificate-expiry",
    ],
    TestMode.MAINTENANCE: ["changed", "impact-analysis", "regression", "incident-replay", "compatibility"],
    TestMode.EXPLORATORY_AI: ["ai-exploration", "boundary-generation", "human-review"],
}
SERVICE_TESTS = {
    ServiceType.WEB: ["browser-compatibility", "responsive", "accessibility", "form-validation"],
    ServiceType.ECOMMERCE: ["pricing", "inventory", "idempotency", "payment-sandbox", "booking-conflict"],
    ServiceType.BUSINESS: ["authorization-matrix", "audit-log", "data-integrity", "csv-excel"],
    ServiceType.API: ["openapi", "contract", "authentication", "rate-limit", "idempotency"],
    ServiceType.BATCH: ["replay", "duplicate-prevention", "resume", "locking", "partial-failure"],
    ServiceType.AI_AGENT: [
        "tool-calling",
        "prompt-injection",
        "secret-leakage",
        "loop-limit",
        "approval-gate",
        "human-approval",
        "ai-safety-regression",
        "eval-regression",
    ],
    ServiceType.LEGACY_DESKTOP: ["file-lock", "encoding", "path-length", "office-bitness", "crash-recovery"],
    ServiceType.EMULATOR: [],
}
FULL_REGRESSION_PATTERNS = (
    "auth",
    "permission",
    "role",
    "schema",
    "migration",
    "package-lock",
    "requirements",
    "payment",
    "checkout",
    "shared",
)
EMULATOR_FOUNDATION_PATTERNS = (
    "cpu",
    "pipeline",
    "cache",
    "tlb",
    "cp0",
    "isa",
    "sysad",
    "bus",
    "rtl",
    "rom",
)


def calculate_risk(request: ProfileRequest) -> int:
    risk = request.risk
    weights = configuration.policy.risk_weights
    value = (
        LEVEL_SCORE[risk.business_impact] * weights.business_impact
        + LEVEL_SCORE[risk.data_sensitivity] * weights.data_sensitivity
        + LEVEL_SCORE[risk.change_complexity] * weights.change_complexity
        + LEVEL_SCORE[risk.user_impact] * weights.user_impact
        + RECOVERABILITY_RISK[risk.recoverability] * weights.recovery_difficulty
    )
    return round(value)


def risk_mode(score: int) -> TestMode:
    thresholds = configuration.policy.thresholds
    if score >= thresholds.release_gate:
        return TestMode.RELEASE_GATE
    if score >= thresholds.strict:
        return TestMode.STRICT
    if score >= thresholds.standard:
        return TestMode.STANDARD
    if score >= thresholds.development:
        return TestMode.DEVELOPMENT
    return TestMode.QUICK


def generate_profile(request: ProfileRequest) -> ProfileResponse:
    score = calculate_risk(request)
    stage_mode = STAGE_MODE[request.developmentStage]
    score_mode = risk_mode(score)
    recommended = _stronger(stage_mode, score_mode)
    reasons = [
        f"開発段階 {request.developmentStage.value} の基準は {stage_mode.value}",
        f"リスクスコア {score}/100 の基準は {score_mode.value}",
    ]
    compatibility_level = request.compatibilityLevel
    if request.serviceType is ServiceType.EMULATOR and compatibility_level is None:
        compatibility_level = CompatibilityLevel.FUNCTIONAL
        reasons.append("エミュレータの互換性レベル未指定のため functional を安全フロアに採用")
    changed_lower = [path.lower().replace("\\", "/") for path in request.changedFiles]
    foundation_patterns = FULL_REGRESSION_PATTERNS
    if request.serviceType is ServiceType.EMULATOR:
        foundation_patterns += EMULATOR_FOUNDATION_PATTERNS
    full_regression = any(pattern in path for path in changed_lower for pattern in foundation_patterns)
    if full_regression:
        recommended = _stronger(recommended, TestMode.STRICT)
        reasons.append("共通基盤・認証・権限・決済・スキーマ系変更を検出したため全回帰を要求")
    compatibility_floor = {
        CompatibilityLevel.FUNCTIONAL: TestMode.STANDARD,
        CompatibilityLevel.SYSTEM: TestMode.STRICT,
        CompatibilityLevel.CYCLE: TestMode.RELEASE_GATE,
        CompatibilityLevel.PHYSICAL: TestMode.RELEASE_GATE,
    }.get(compatibility_level)
    if request.serviceType is ServiceType.EMULATOR and compatibility_floor is not None:
        recommended = _stronger(recommended, compatibility_floor)
        reasons.append(f"{compatibility_level.value} 互換性の安全フロアは {compatibility_floor.value}")
    if request.production or request.developmentStage is DevelopmentStage.PRODUCTION:
        recommended = TestMode.PRODUCTION_SAFE
        reasons.append("本番環境では読み取り専用テストへ強制")
    requested = request.requestedMode
    if requested and MODE_RANK[requested] < MODE_RANK[recommended]:
        reasons.append(f"要求モード {requested.value} は安全フロアより弱いため採用しない")
    elif requested and not request.production:
        recommended = requested
        reasons.append(f"利用者指定モード {requested.value} を採用")

    service_tests = SERVICE_TESTS[request.serviceType]
    if request.serviceType is ServiceType.EMULATOR:
        service_tests = compatibility_tests(compatibility_level)
    required = list(dict.fromkeys(MODE_TESTS[recommended] + service_tests))
    if full_regression and "regression-full" not in required:
        required.append("regression-full")
    if request.aiEnabled and request.serviceType is ServiceType.AI_AGENT:
        required.extend(
            test
            for test in ["llm-schema", "model-fallback", "human-approval", "ai-safety-regression"]
            if test not in required
        )
    optional = _optional_tests(recommended, request.serviceType)
    restrictions = _restrictions(request, recommended)
    approval = score >= 85 or recommended is TestMode.RELEASE_GATE or request.production
    selections = [
        TestSelection(
            name=name,
            intensity=_intensity(recommended, full_regression),
            reason=_test_reason(name, request.serviceType, full_regression),
        )
        for name in required
    ]
    profile_id = f"profile-{uuid4().hex[:12]}"
    return ProfileResponse(
        id=profile_id,
        projectId=request.projectId,
        developmentStage=request.developmentStage,
        serviceType=request.serviceType,
        compatibilityLevel=compatibility_level,
        recommendedMode=recommended,
        requestedMode=requested,
        riskScore=score,
        reasons=reasons,
        requiredTests=required,
        optionalTests=optional,
        selections=selections,
        restrictions=restrictions,
        humanApprovalRequired=approval,
        fullRegressionRequired=full_regression,
        configuration={
            "environment": request.environment,
            "production": request.production,
            "maxDurationMinutes": request.maxDurationMinutes,
            "parallelism": min(request.parallelism, 4) if request.production else request.parallelism,
            "retryCount": 0 if recommended in {TestMode.STRICT, TestMode.RELEASE_GATE} else 1,
            "aiEnabled": request.aiEnabled,
            "compatibilityLevel": (compatibility_level.value if compatibility_level is not None else None),
        },
    )


def save_profile(profile: ProfileResponse, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{profile.id}.json"
    temporary = path.with_suffix(".json.tmp")
    content = json.dumps(profile.model_dump(mode="json"), ensure_ascii=False, indent=2)
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    return path


def load_profile(profile_id: str, directory: Path) -> ProfileResponse:
    safe = "".join(character for character in profile_id if character.isalnum() or character in {"-", "_"})[
        :100
    ]
    if not safe or safe != profile_id:
        raise ValueError("Invalid profile id.")
    path = directory / f"{safe}.json"
    if not path.exists():
        raise FileNotFoundError(profile_id)
    return ProfileResponse.model_validate_json(path.read_text(encoding="utf-8"))


def _stronger(left: TestMode, right: TestMode) -> TestMode:
    return left if MODE_RANK[left] >= MODE_RANK[right] else right


def _intensity(mode: TestMode, full_regression: bool) -> str:
    if mode is TestMode.PRODUCTION_SAFE:
        return "read_only"
    if full_regression or mode in {TestMode.STRICT, TestMode.RELEASE_GATE}:
        return "full"
    if mode in {TestMode.QUICK, TestMode.DEVELOPMENT}:
        return "changed"
    return "critical"


def _test_reason(name: str, service: ServiceType, full_regression: bool) -> str:
    if full_regression and name == "regression-full":
        return "高波及変更に対する安全フロア"
    if name in SERVICE_TESTS[service]:
        return f"{service.value} サービス固有リスク"
    return "開発段階・リスクスコア・テストモードから選択"


def _optional_tests(mode: TestMode, service: ServiceType) -> list[str]:
    optional = ["visual-regression", "performance-soak", "cross-browser-extended"]
    if service is ServiceType.AI_AGENT:
        optional.extend(["multi-model-consistency", "red-team-evaluation"])
    if service is ServiceType.EMULATOR:
        optional.extend(["opcode-fuzzing", "cross-core-triangulation", "save-state-replay"])
    if mode is TestMode.PRODUCTION_SAFE:
        return ["visual-snapshot"]
    return optional


def _restrictions(request: ProfileRequest, mode: TestMode) -> list[str]:
    restrictions = ["実決済・実送金・本番データ削除・未承認通知を禁止", "AI修正の自動適用を禁止"]
    if request.production or mode is TestMode.PRODUCTION_SAFE:
        restrictions.extend(["書き込み操作禁止", "毎分10リクエスト以下", "高負荷試験禁止"])
    if request.serviceType is ServiceType.EMULATOR:
        restrictions.extend(
            [
                "第三者のROM・PIF・ファームウェアを成果物へ同梱しない",
                "生成ROM・homebrew・利用者が権利を持つイメージだけを実行する",
                "未知のROMはネットワーク無効・サンドボックス内で実行する",
                "ROM・trace・waveform・結果のSHA-256を証跡へ保存する",
            ]
        )
    return restrictions
