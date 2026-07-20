from fastapi.testclient import TestClient

from app.live_ui import live_css, live_html, live_js
from app.main import app

client = TestClient(app)


def test_live_html_has_review_ready_content_and_external_assets() -> None:
    html = live_html()

    assert "普段どおり操作するだけ。" in html
    assert "AIがテストに変える" in html
    for stage in ("Observe", "Generate", "Replay", "Explain", "Share"):
        assert stage in html
    for tab in ("Dashboard", "Test一覧", "実行中", "レポート"):
        assert tab in html
    assert "ローカルサンプルを作成" in html
    assert "拡張導入ガイド" in html
    assert "Codex / provider" in html
    assert 'href="/assets/live.css"' in html
    assert 'src="/assets/live.js"' in html
    assert "<style" not in html
    assert "<script>" not in html


def test_live_css_supports_themes_mobile_and_accessibility() -> None:
    css = live_css()

    assert ':root[data-theme="light"]' in css
    assert "@media (max-width: 640px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
    assert "[hidden]" in css


def test_live_js_uses_browser_agent_api_without_unsafe_dom_execution() -> None:
    script = live_js()

    for path in (
        "/api/v1/browser-agent/status",
        "/api/v1/browser-agent/sessions",
        "/api/v1/browser-agent/sample/local",
        "/api/v1/browser-agent/sessions/${encodeURIComponent(sessionId)}/run",
        "/api/v1/browser-agent/sessions/${encodeURIComponent(sessionId)}/report",
    ):
        assert path in script
    assert "textContent" in script
    assert "createElement" in script
    assert "replaceChildren" in script
    assert "innerHTML" not in script
    assert "eval(" not in script
    assert "document.write" not in script


def test_live_js_has_stable_operational_states() -> None:
    script = live_js()

    for state_name in ("loading", "empty", "error", "success", "disabled"):
        assert state_name in script
    assert "AbortController" in script
    assert "aria-selected" in script
    assert "nodes.demo.disabled" in script


def test_bundled_demo_is_login_free_and_has_a_replay_destination() -> None:
    home = client.get("/demo-site/")
    sample = client.get("/demo-site/?page_id=2")

    assert home.status_code == 200
    assert "BUNDLED · LOGIN-FREE · LOCAL" in home.text
    assert 'href="/demo-site/?page_id=2"' in home.text
    assert "Sample Page" in sample.text
    assert "script-src" not in home.headers["content-security-policy"]
