from app.dashboard import dashboard_html


def test_dashboard_preserves_javascript_newline_regex() -> None:
    html = dashboard_html()
    assert "split(/\\r?\\n/)" in html
    assert "test-profiles/generate" in html
    assert "test-cases/check" in html
    assert "ケース自動チェック" in html
    assert "model-recommendations" in html
    assert "用途別の推奨モデル" in html
