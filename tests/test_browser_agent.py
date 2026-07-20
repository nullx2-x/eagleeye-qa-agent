from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import browser_agent, storage
from app.browser_agent_models import BrowserObservation, BrowserSessionCreate
from app.codex_agent import CodexAgentError
from app.main import app
from app.models import EvidenceArtifact, RunResult

client = TestClient(app)


@pytest.fixture
def isolated_browser_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(browser_agent, "BROWSER_SESSIONS", tmp_path / "browser-sessions")
    monkeypatch.setattr(browser_agent, "BROWSER_CAPTURES", tmp_path / "browser-captures")
    monkeypatch.setattr(browser_agent, "CODEX_BROWSER_CWD", tmp_path / "codex-cwd")
    monkeypatch.setattr(storage, "SESSIONS", tmp_path / "sessions")
    monkeypatch.setattr(storage, "GENERATED", tmp_path / "generated")
    monkeypatch.setattr(storage, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(browser_agent, "codex_available", lambda: False)
    return tmp_path


def _session() -> BrowserSessionCreate:
    return BrowserSessionCreate(
        name="Authorized target <sample>",
        goal="公開ページの主要導線を確認する",
        startUrl="http://127.0.0.1:8888/",
        locale="ja",
    )


def test_record_generate_and_replay_flow(
    isolated_browser_agent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = browser_agent.create_session(_session())
    browser_agent.append_observation(
        session.id,
        BrowserObservation(
            id="goto-1",
            timestamp=1,
            action="goto",
            url="http://127.0.0.1:8888/",
            redacted=False,
        ),
    )
    browser_agent.append_observation(
        session.id,
        BrowserObservation(
            id="click-1",
            timestamp=2,
            action="click",
            url="http://127.0.0.1:8888/",
            target={"role": "link", "name": "Sample Page", "tagName": "a"},
            redacted=False,
        ),
    )

    generated = browser_agent.generate_session(session.id)

    assert generated.status == "generated"
    assert generated.generatedCases[0].id == "REC-001"
    assert generated.generatedCases[0].runnable is True
    assert generated.ai is not None and generated.ai.fallbackUsed is True
    assert generated.caseQuality is not None
    stored_bundle = storage.load_bundle(session.id)
    assert stored_bundle.source == "eagleeye-extension"
    assert len(stored_bundle.session.events) == 2
    assert str(stored_bundle.session.expectedFinalUrl) == "http://127.0.0.1:8888/"

    monkeypatch.setattr(
        browser_agent,
        "run_bundle",
        lambda bundle: RunResult(
            session_id=bundle.session.id,
            status="passed",
            duration_ms=42,
            screenshot=str(isolated_browser_agent / "private" / "final.png"),
            evidence=[
                EvidenceArtifact(
                    kind="screenshot",
                    path=str(isolated_browser_agent / "private" / "final.png"),
                    mime_type="image/png",
                    byte_size=12,
                    sha256="a" * 64,
                    created_at="2026-07-17T00:00:00+00:00",
                    capture_source="test",
                )
            ],
        ),
    )
    replayed = browser_agent.run_session(session.id)

    assert replayed.status == "passed"
    assert replayed.replayCount == 1
    assert replayed.qualityGate is not None
    assert replayed.qualityGate.decision == "PASS"
    assert replayed.run is not None
    assert replayed.run.screenshot == "[redacted-local-path]"
    assert replayed.run.evidence[0].path == "[redacted-local-path]"
    exported = browser_agent.bug_report_markdown(session.id)
    assert str(isolated_browser_agent) not in exported
    assert "sha256:" + "a" * 64 in exported
    assert (isolated_browser_agent / "runs" / session.id / "result.json").is_file()


def test_input_values_are_not_part_of_browser_observation_schema(isolated_browser_agent: Path) -> None:
    session = browser_agent.create_session(_session())
    with pytest.raises(ValueError, match="Input-bearing"):
        browser_agent.append_observation(
            session.id,
            BrowserObservation(
                id="fill-1",
                timestamp=1,
                action="fill",
                url="http://127.0.0.1:8888/",
                target={"role": "textbox", "name": "Email", "tagName": "input"},
                valueType="email",
                redacted=False,
            ),
        )


def test_recording_cannot_cross_origin(isolated_browser_agent: Path) -> None:
    session = browser_agent.create_session(_session())
    with pytest.raises(ValueError, match="cannot cross"):
        browser_agent.append_observation(
            session.id,
            BrowserObservation(
                id="goto-evil",
                timestamp=1,
                action="goto",
                url="https://example.com/",
                redacted=False,
            ),
        )


def test_screenshot_is_bounded_and_report_escapes_untrusted_text(isolated_browser_agent: Path) -> None:
    session = browser_agent.create_session(_session())
    image = base64.b64encode(b"small-png-fixture").decode()
    browser_agent.append_observation(
        session.id,
        BrowserObservation(
            id="snapshot-1",
            timestamp=1,
            action="snapshot",
            url="http://127.0.0.1:8888/",
            redacted=False,
            screenshotDataUrl=f"data:image/png;base64,{image}",
        ),
    )

    content, media_type = browser_agent.screenshot_bytes(session.id)
    report = browser_agent.report_html(session.id)

    assert content == b"small-png-fixture"
    assert media_type == "image/png"
    assert "Authorized target &lt;sample&gt;" in report
    assert "Authorized target <sample>" not in report
    assert "screenshot" in report


def test_secret_query_parameters_are_removed(isolated_browser_agent: Path) -> None:
    session = browser_agent.create_session(
        BrowserSessionCreate(
            name="Query safety",
            goal="秘密値を保存しない",
            startUrl="http://127.0.0.1:8888/?page_id=2&token=do-not-store",
        )
    )

    assert "page_id=2" in str(session.startUrl)
    assert "token" not in str(session.startUrl)
    assert "do-not-store" not in session.model_dump_json()


def test_browser_agent_api_record_generate_and_report(isolated_browser_agent: Path) -> None:
    started = client.post(
        "/api/v1/browser-agent/sessions",
        json={
            "name": "API demo",
            "goal": "公開ページを確認する",
            "startUrl": "http://127.0.0.1:8888/",
            "locale": "ja",
        },
    )
    assert started.status_code == 200
    session_id = started.json()["id"]

    observed = client.post(
        f"/api/v1/browser-agent/sessions/{session_id}/observations",
        json={
            "id": "goto-api",
            "timestamp": 1,
            "action": "goto",
            "url": "http://127.0.0.1:8888/",
            "redacted": False,
        },
    )
    assert observed.status_code == 200

    generated = client.post(f"/api/v1/browser-agent/sessions/{session_id}/generate")
    assert generated.status_code == 200
    assert generated.json()["generatedCases"][0]["source"] == "recording"

    report = client.get(f"/api/v1/browser-agent/sessions/{session_id}/report")
    assert report.status_code == 200
    assert "EAGLEEYE AI QA REPORT" in report.text
    assert report.headers["content-security-policy"].startswith("default-src 'self'")

    bug_report = client.get(f"/api/v1/browser-agent/sessions/{session_id}/bug-report")
    assert bug_report.status_code == 200
    assert bug_report.headers["content-disposition"].startswith("attachment;")
    assert "Generated locally by EagleEye" in bug_report.text


def test_browser_agent_api_deletes_session_and_derivative_artifacts(
    isolated_browser_agent: Path,
) -> None:
    started = client.post(
        "/api/v1/browser-agent/sessions",
        json={
            "name": "Delete me",
            "goal": "削除導線を確認する",
            "startUrl": "http://127.0.0.1:8888/",
        },
    )
    session_id = started.json()["id"]
    browser_agent.append_observation(
        session_id,
        BrowserObservation(
            id="goto-delete",
            timestamp=1,
            action="goto",
            url="http://127.0.0.1:8888/",
            redacted=False,
        ),
    )
    browser_agent.generate_session(session_id)
    capture = browser_agent.BROWSER_CAPTURES / session_id
    capture.mkdir(parents=True, exist_ok=True)
    (capture / "visible-page.png").write_bytes(b"fixture")
    run = storage.RUNS / session_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "result.json").write_text("{}", encoding="utf-8")

    deleted = client.delete(f"/api/v1/browser-agent/sessions/{session_id}")

    assert deleted.status_code == 204
    assert client.get(f"/api/v1/browser-agent/sessions/{session_id}").status_code == 404
    assert not capture.exists()
    assert not run.exists()
    assert not (storage.SESSIONS / f"{session_id}.json").exists()
    assert not (storage.GENERATED / f"{session_id}.spec.ts").exists()


def test_ai_and_export_urls_redact_identifiers_and_query_values() -> None:
    value = "http://127.0.0.1:8888/users/550e8400-e29b-41d4-a716-446655440000/?page=private-account-42"

    safe = browser_agent._privacy_safe_url(value)
    redacted = browser_agent._redact(
        "owner@example.com +81 90 1234 5678 C:\\Users\\private-name\\report.txt 2026-07-17"
    )

    assert "550e8400" not in safe
    assert "private-account-42" not in safe
    assert "page=%5Bredacted%5D" in safe
    assert "owner@example.com" not in redacted
    assert "90 1234 5678" not in redacted
    assert "private-name" not in redacted
    assert "2026-07-17" in redacted


def test_codex_timeout_falls_back_without_crashing(
    isolated_browser_agent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(browser_agent, "codex_available", lambda: True)

    def timeout(**_kwargs):
        raise CodexAgentError("structured turn timed out")

    monkeypatch.setattr(browser_agent, "invoke_codex_structured", timeout)
    session = browser_agent.create_session(_session())
    browser_agent.append_observation(
        session.id,
        BrowserObservation(
            id="goto-timeout",
            timestamp=1,
            action="goto",
            url="http://127.0.0.1:8888/",
            redacted=False,
        ),
    )

    generated = browser_agent.generate_session(session.id)

    assert generated.status == "generated"
    assert generated.ai is not None
    assert generated.ai.available is False
    assert generated.ai.fallbackUsed is True
    assert generated.generatedCases[0].runnable is True


def test_ai_fixed_wait_is_rewritten_before_quality_check(
    isolated_browser_agent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(browser_agent, "codex_available", lambda: True)
    monkeypatch.setattr(
        browser_agent,
        "invoke_codex_structured",
        lambda **_kwargs: {
            "cases": [
                {
                    "title": "Sample Pageへ移動する",
                    "objective": "公開導線を確認する",
                    "steps": ["リンクをクリックし、最大10秒待つ。"],
                    "expectedResults": ["URLにpage_id=2が含まれる"],
                    "assertions": ["page.url contains page_id=2"],
                    "priority": "high",
                    "criticalFlow": True,
                }
            ],
            "risks": ["Replay画面に成功状態を追加する"],
            "fixSuggestions": ["主要メニューへアクセシブルな名前を追加する"],
        },
    )
    session = browser_agent.create_session(_session())
    browser_agent.append_observation(
        session.id,
        BrowserObservation(
            id="goto-ai",
            timestamp=1,
            action="goto",
            url="http://127.0.0.1:8888/",
            redacted=False,
        ),
    )

    generated = browser_agent.generate_session(session.id)

    assert generated.ai is not None and generated.ai.available is True
    assert len(generated.generatedCases) == 2
    assert "10秒" not in generated.generatedCases[1].steps[0]
    assert "期待要素" in generated.generatedCases[1].steps[0]
    assert generated.caseQuality is not None
    assert generated.caseQuality.decision != "FAIL"
    assert all("Replay" not in item for item in generated.fixSuggestions)
    assert "主要メニューへアクセシブルな名前を追加する" in generated.fixSuggestions
