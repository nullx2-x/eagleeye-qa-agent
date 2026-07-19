from types import SimpleNamespace

import pytest

from app import browser_agent, browser_hardening, project_qa


def test_nonce_userinfo_and_fragment_are_removed() -> None:
    value = (
        "https://user:password@example.test:8443/wp-admin/post.php"
        "?post=10&_wpnonce=secret&nonce=also-secret&view=public#editor"
    )
    safe = browser_hardening.sanitize_browser_url(value)

    assert "user" not in safe
    assert "password" not in safe
    assert "_wpnonce" not in safe
    assert "also-secret" not in safe
    assert "view=public" in safe
    assert "#" not in safe


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/wp-admin/",
        "https://example.test/wp-admin/post.php",
        "https://example.test/wp-login.php",
    ],
)
def test_sensitive_admin_paths_are_detected(url: str) -> None:
    assert browser_hardening.is_sensitive_admin_url(url)


def test_admin_ai_generation_is_disabled() -> None:
    session = SimpleNamespace(startUrl="https://example.test/wp-admin/", observations=[])
    cases, result, risks, suggestions = browser_hardening._guarded_ai_cases(session)

    assert cases == []
    assert result.available is False
    assert result.fallbackUsed is True
    assert risks == []
    assert suggestions


def test_admin_replay_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(startUrl="https://example.test/wp-admin/", observations=[])
    monkeypatch.setattr(browser_agent, "load_session", lambda _session_id: session)

    with pytest.raises(PermissionError, match="Replay is disabled"):
        browser_hardening._guarded_run_session("a" * 32)


def test_project_discovery_has_no_cpu_or_web_diagnostic_requirement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'\nversion='0.1.0'\n")
    monkeypatch.setenv("EAGLEEYE_PROJECT_ROOTS", str(tmp_path))

    discovery = project_qa.discover_project(str(tmp_path))
    commands = [" ".join(suite.command).casefold() for suite in discovery.suites]

    assert commands
    assert all("cpu" not in command for command in commands)
    assert all("diagnostic" not in command for command in commands)


def test_generated_submission_history_is_not_tracked() -> None:
    from pathlib import Path

    assert not Path("reports").exists()
    assert not Path("videos/eagleeye-build-week").exists()
    assert not Path("docs/build-week").exists()
