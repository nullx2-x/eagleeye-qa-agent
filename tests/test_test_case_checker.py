from app.test_case_checker import check_test_cases
from app.test_case_models import TestCaseCheckRequest as CaseCheckRequest


def test_clean_case_passes() -> None:
    result = check_test_cases(
        CaseCheckRequest.model_validate(
            {
                "projectId": "demo",
                "requiredTestTypes": ["e2e"],
                "cases": [
                    {
                        "id": "TC-001",
                        "title": "有効な利用者が登録を完了できる",
                        "type": "e2e",
                        "steps": ["登録画面を開く", "有効なメールを入力して登録ボタンを押す"],
                        "expectedResults": ["完了画面に Registration completed が表示される"],
                        "assertions": ["getByRole('heading', {name: 'Registration completed'}) is visible"],
                        "priority": "high",
                        "criticalFlow": True,
                    }
                ],
            }
        )
    )
    assert result.decision == "PASS"
    assert result.score == 100


def test_checker_finds_secret_wait_assertion_and_coverage_gaps() -> None:
    result = check_test_cases(
        CaseCheckRequest.model_validate(
            {
                "projectId": "demo",
                "requiredTestTypes": ["e2e", "security"],
                "cases": [
                    {
                        "id": "TC-002",
                        "title": "login",
                        "type": "e2e",
                        "steps": ["password=actualSecret123 を入力", "sleep 5秒"],
                        "expectedResults": ["正常"],
                        "retryCount": 3,
                    }
                ],
            }
        )
    )
    codes = {issue.code for issue in result.issues}
    assert result.decision == "FAIL"
    assert {"POSSIBLE_SECRET", "FIXED_WAIT", "MISSING_ASSERTION", "COVERAGE_GAP"} <= codes


def test_checker_detects_duplicates() -> None:
    request = {
        "projectId": "demo",
        "cases": [
            {
                "id": case_id,
                "title": "同じ確認",
                "steps": ["画面を開く"],
                "expectedResults": ["対象の見出しが1件表示される"],
                "assertions": ["heading count equals 1"],
            }
            for case_id in ("A", "B")
        ],
    }
    result = check_test_cases(CaseCheckRequest.model_validate(request))
    assert any(issue.code == "DUPLICATE_CASE" for issue in result.issues)
