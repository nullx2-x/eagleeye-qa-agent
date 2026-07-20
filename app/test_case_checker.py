import re
from collections import Counter, defaultdict
from datetime import UTC, datetime

from .test_case_models import (
    TestCaseCheckRequest,
    TestCaseCheckResponse,
    TestCaseIssue,
    TestCaseScore,
)

PENALTIES = {"critical": 35, "high": 20, "medium": 10, "low": 4, "info": 0}
VAGUE = re.compile(r"(?:works?|correct(?:ly)?|appropriate|正常|適切|問題ない|期待どおり)$", re.I)
FIXED_WAIT = re.compile(r"(?:sleep|waitForTimeout|setTimeout|固定.{0,3}待機|\d+秒待)", re.I)
UNSTABLE_SELECTOR = re.compile(r"(?:nth-child|xpath=|//(?:div|span)|#[a-z0-9_-]*\d{5,})", re.I)
SECRET = re.compile(
    r"(?:bearer\s+[a-z0-9._-]{12,}|sk-[a-z0-9_-]{12,}|password\s*[:=]\s*[^*\s]{6,}|api[_-]?key\s*[:=])",
    re.I,
)


def check_test_cases(request: TestCaseCheckRequest) -> TestCaseCheckResponse:
    issues: list[TestCaseIssue] = []
    by_case: dict[str, list[TestCaseIssue]] = defaultdict(list)

    def add(code: str, severity: str, ids: list[str], message: str, suggestion: str) -> None:
        issue = TestCaseIssue(
            code=code,
            severity=severity,
            testCaseIds=ids,
            message=message,
            suggestion=suggestion,
        )
        issues.append(issue)
        for case_id in ids:
            by_case[case_id].append(issue)

    for case in request.cases:
        combined = "\n".join(
            [case.title, *case.preconditions, *case.steps, *case.expectedResults, *case.assertions]
        )
        if not case.expectedResults:
            add(
                "MISSING_EXPECTED_RESULT",
                "high",
                [case.id],
                "期待結果が定義されていません。",
                "観測可能な画面、API応答、DB状態などを具体的に追加してください。",
            )
        elif any(len(value.strip()) < 8 or VAGUE.search(value.strip()) for value in case.expectedResults):
            add(
                "VAGUE_EXPECTED_RESULT",
                "medium",
                [case.id],
                "期待結果に曖昧または短すぎる表現があります。",
                "値、状態、件数、遷移先など判定可能な条件へ置き換えてください。",
            )
        if not case.assertions:
            add(
                "MISSING_ASSERTION",
                "medium",
                [case.id],
                "自動判定に使用するassertionがありません。",
                "期待結果に対応するlocator、status code、schema等のassertionを追加してください。",
            )
        if len(case.steps) > 20:
            add(
                "TOO_MANY_STEPS",
                "medium",
                [case.id],
                f"1ケースに{len(case.steps)}ステップあり、原因特定が難しくなります。",
                "独立した目的ごとにケースを分割してください。",
            )
        if FIXED_WAIT.search(combined):
            add(
                "FIXED_WAIT",
                "high",
                [case.id],
                "固定時間待機が含まれ、flaky化する可能性があります。",
                "要素、レスポンス、状態変化を条件に待機してください。",
            )
        if UNSTABLE_SELECTOR.search(combined):
            add(
                "UNSTABLE_SELECTOR",
                "medium",
                [case.id],
                "DOM構造や自動採番に依存するselectorが含まれています。",
                "role/name、label、安定したdata-testidを優先してください。",
            )
        if SECRET.search(combined):
            add(
                "POSSIBLE_SECRET",
                "critical",
                [case.id],
                "秘密値らしき文字列がテストケースに直接含まれています。",
                "ダミー値または実行時secret injectionへ置き換えてください。",
            )
        if case.retryCount > 1:
            add(
                "RETRY_DEPENDENCY",
                "medium",
                [case.id],
                f"retryCount={case.retryCount} が不安定性を隠す可能性があります。",
                "再試行を1回以下にし、失敗原因を修正してください。",
            )
        if case.criticalFlow and case.priority not in {"critical", "high"}:
            add(
                "CRITICAL_PRIORITY_MISMATCH",
                "medium",
                [case.id],
                "重要フローですが優先度がmedium以下です。",
                "high以上へ設定し、品質ゲートのブロッカーとして扱ってください。",
            )

    _add_duplicate_issues(request, add)
    present_types = {case.type.lower() for case in request.cases}
    required_types = {value.lower() for value in request.requiredTestTypes}
    missing_types = sorted(required_types - present_types)
    if missing_types:
        add(
            "COVERAGE_GAP",
            "high",
            [],
            "必須テスト種別が不足しています: " + ", ".join(missing_types),
            "不足種別のケースを追加するか、不要な理由をレビュー記録へ残してください。",
        )

    case_scores = []
    for case in request.cases:
        deductions = sum(PENALTIES[issue.severity] for issue in by_case[case.id])
        score = max(0, 100 - deductions)
        status = (
            "FAIL"
            if any(i.severity in {"critical", "high"} for i in by_case[case.id])
            else ("WARNING" if by_case[case.id] else "PASS")
        )
        case_scores.append(
            TestCaseScore(
                id=case.id,
                title=case.title,
                score=score,
                status=status,
                issueCount=len(by_case[case.id]),
            )
        )

    severity_counts = Counter(issue.severity for issue in issues)
    suite_penalty = min(30, len(missing_types) * 10)
    score = max(0, round(sum(item.score for item in case_scores) / len(case_scores)) - suite_penalty)
    decision = (
        "FAIL"
        if severity_counts["critical"] or severity_counts["high"] or score < 70
        else "PASS_WITH_WARNING"
        if issues
        else "PASS"
    )
    return TestCaseCheckResponse(
        projectId=request.projectId,
        decision=decision,
        score=score,
        counts={severity: severity_counts[severity] for severity in PENALTIES},
        issues=sorted(issues, key=lambda item: -PENALTIES[item.severity]),
        cases=case_scores,
        coverage={"presentTypes": sorted(present_types), "missingTypes": missing_types},
        checkedAt=datetime.now(UTC).isoformat(),
    )


def _add_duplicate_issues(request: TestCaseCheckRequest, add) -> None:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for case in request.cases:
        title = re.sub(r"\W+", "", case.title).lower()
        steps = re.sub(r"\W+", "", " ".join(case.steps)).lower()
        groups[(title, steps)].append(case.id)
    for ids in groups.values():
        if len(ids) > 1:
            add(
                "DUPLICATE_CASE",
                "medium",
                ids,
                "タイトルと手順が同一のテストケースがあります。",
                "重複を統合するか、異なる検証目的をタイトルとassertionへ明記してください。",
            )
