from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError

from app import runner
from app.models import EagleEyeBundle
from app.storage import evidence_from_file


class FakeVideo:
    def __init__(self, path: Path) -> None:
        self._path = path
        self.finalized = False

    def finalize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(b"deterministic-webm-evidence")
        self.finalized = True

    def path(self) -> str:
        if not self.finalized:
            raise PlaywrightError("video requested before context close")
        return str(self._path)


class FakeLocator:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    def click(self) -> None:
        self.page.operations.append(("click", None))
        if self.page.fail_click:
            raise PlaywrightError("deterministic action failure")

    def fill(self, value: str) -> None:
        self.page.operations.append(("fill", value))

    def select_option(self, value=None, *, index=None) -> None:
        self.page.operations.append(("select", {"value": value, "index": index}))

    def check(self) -> None:
        self.page.operations.append(("check", None))

    def is_visible(self) -> bool:
        self.page.operations.append(("visible", None))
        return True


class FakePage:
    def __init__(self, video: FakeVideo | None, *, fail_click: bool) -> None:
        self.video = video
        self.fail_click = fail_click
        self.operations: list[tuple[str, object]] = []
        self.closed = False
        self.url = "about:blank"

    def set_default_timeout(self, timeout: int) -> None:
        self.operations.append(("timeout", timeout))

    def goto(self, url: str, *, wait_until: str) -> None:
        self.operations.append(("goto", (url, wait_until)))
        self.url = url

    def title(self) -> str:
        return "Observed page"

    def get_by_role(self, role: str, *, name: str, exact: bool):
        self.operations.append(("role", (role, name, exact)))
        return FakeLocator(self)

    def get_by_label(self, name: str, *, exact: bool):
        self.operations.append(("label", (name, exact)))
        return FakeLocator(self)

    def locator(self, selector: str):
        self.operations.append(("locator", selector))
        return FakeLocator(self)

    def screenshot(self, *, path: str, full_page: bool) -> None:
        self.operations.append(("screenshot", full_page))
        Path(path).write_bytes(b"deterministic-png-evidence")

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, options: dict, *, fail_click: bool) -> None:
        self.options = options
        video = None
        if "record_video_dir" in options:
            video = FakeVideo(Path(options["record_video_dir"]) / "recording.webm")
        self.page = FakePage(video, fail_click=fail_click)
        self.closed = False
        self.routes: list[tuple[str, object]] = []

    def route(self, pattern: str, handler) -> None:
        self.routes.append((pattern, handler))

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True
        self.page.closed = True
        if self.page.video is not None:
            self.page.video.finalize()


class FakeRoute:
    def __init__(self, url: str) -> None:
        self.request = type("Request", (), {"url": url})()
        self.continued = False
        self.aborted_with: str | None = None

    def continue_(self) -> None:
        self.continued = True

    def abort(self, reason: str) -> None:
        self.aborted_with = reason


class FakeBrowser:
    def __init__(self, *, fail_click: bool) -> None:
        self.fail_click = fail_click
        self.context: FakeContext | None = None
        self.closed = False

    def new_context(self, **options) -> FakeContext:
        self.context = FakeContext(options, fail_click=self.fail_click)
        return self.context

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser

    def launch(self, *, headless: bool) -> FakeBrowser:
        assert headless is True
        return self.browser


class FakePlaywright:
    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)


class FakePlaywrightManager:
    def __init__(self, browser: FakeBrowser) -> None:
        self.playwright = FakePlaywright(browser)

    def __enter__(self) -> FakePlaywright:
        return self.playwright

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def _bundle(*, fail_click: bool = False, recording: bool = True) -> EagleEyeBundle:
    action = "click" if fail_click else "fill"
    events = [
        {
            "id": "event-1",
            "timestamp": 1,
            "action": action,
            "url": "http://127.0.0.1:3000/",
            "target": {"role": "textbox" if action == "fill" else "button", "name": "Target"},
            "value": "private-user@example.com" if action == "fill" else None,
            "valueType": "email" if action == "fill" else None,
            "redacted": action == "fill",
        }
    ]
    if not fail_click:
        events.append(
            {
                "id": "event-2",
                "timestamp": 2,
                "action": "select",
                "url": "http://127.0.0.1:3000/",
                "target": {"name": "Private option"},
                "value": "private-option-id",
                "valueType": "account",
                "redacted": True,
            }
        )
    return EagleEyeBundle.model_validate(
        {
            "schemaVersion": "1.0",
            "source": "orbit-assist",
            "createdAt": "2026-07-16T00:00:00Z",
            "session": {
                "id": "video-evidence-test",
                "name": "Video evidence test",
                "startedAt": "2026-07-16T00:00:00Z",
                "endedAt": "2026-07-16T00:00:01Z",
                "startUrl": "http://127.0.0.1:3000/",
                "recording": recording,
                "events": events,
            },
            "generated": {"playwright": "// generated", "yaml": "name: generated"},
        }
    )


def _install_fake(monkeypatch, tmp_path: Path, *, fail_click: bool) -> FakeBrowser:
    browser = FakeBrowser(fail_click=fail_click)
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "sync_playwright", lambda: FakePlaywrightManager(browser))
    return browser


def test_recording_pass_creates_hashed_video_and_uses_synthetic_redactions(monkeypatch, tmp_path) -> None:
    browser = _install_fake(monkeypatch, tmp_path, fail_click=False)

    result = runner.run_bundle(_bundle())

    assert result.status == "passed"
    assert result.screenshot is not None
    assert browser.closed is True
    assert browser.context is not None and browser.context.closed is True
    assert browser.context.options["record_video_size"] == {"width": 1280, "height": 720}
    assert [pattern for pattern, _handler in browser.context.routes] == ["http://**", "https://**"]
    evidence = {artifact.kind: artifact for artifact in result.evidence}
    assert set(evidence) == {"screenshot", "video"}
    assert evidence["video"].mime_type == "video/webm"
    assert evidence["video"].byte_size == len(b"deterministic-webm-evidence")
    assert evidence["video"].sha256 == sha256(b"deterministic-webm-evidence").hexdigest()
    assert Path(evidence["video"].path).is_relative_to((tmp_path / "runs").resolve())
    assert ("fill", "eagleeye-qa@example.invalid") in browser.context.page.operations
    assert ("select", {"value": None, "index": 1}) in browser.context.page.operations
    assert "private-user@example.com" not in repr(browser.context.page.operations)
    assert "private-option-id" not in repr(browser.context.page.operations)


def test_recording_failure_preserves_screenshot_and_video_evidence(monkeypatch, tmp_path) -> None:
    browser = _install_fake(monkeypatch, tmp_path, fail_click=True)

    result = runner.run_bundle(_bundle(fail_click=True))

    assert result.status == "failed"
    assert result.error == "deterministic action failure"
    assert result.analysis is not None
    assert {artifact.kind for artifact in result.evidence} == {"screenshot", "video"}
    assert browser.closed is True
    assert browser.context is not None and browser.context.closed is True


def test_recording_disabled_does_not_create_video_context(monkeypatch, tmp_path) -> None:
    browser = _install_fake(monkeypatch, tmp_path, fail_click=False)

    result = runner.run_bundle(_bundle(recording=False))

    assert result.status == "passed"
    assert {artifact.kind for artifact in result.evidence} == {"screenshot"}
    assert browser.context is not None
    assert browser.context.options == {}
    assert browser.context.page.video is None


def test_evidence_metadata_rejects_file_outside_artifact_root(tmp_path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    outside = tmp_path / "outside.webm"
    outside.write_bytes(b"outside")

    with pytest.raises(ValueError, match="outside"):
        evidence_from_file(
            outside,
            kind="video",
            mime_type="video/webm",
            capture_source="test",
            artifact_root=root,
        )


def test_expected_page_mismatch_fails_instead_of_false_pass(monkeypatch, tmp_path) -> None:
    _install_fake(monkeypatch, tmp_path, fail_click=False)
    bundle = _bundle(recording=False)
    bundle.session.expectedPageTitle = "Expected page"

    result = runner.run_bundle(bundle)

    assert result.status == "failed"
    assert result.error is not None and "Page title mismatch" in result.error


def test_network_guard_blocks_redirects_and_subresources_outside_loopback(monkeypatch) -> None:
    monkeypatch.delenv("EAGLEEYE_ALLOW_REMOTE", raising=False)
    context = FakeContext({}, fail_click=False)

    runner._install_network_guard(context)
    handlers = {pattern: handler for pattern, handler in context.routes}
    local = FakeRoute("http://127.0.0.1:8888/wp-content/app.css")
    remote = FakeRoute("https://example.com/redirected")
    handlers["http://**"](local)
    handlers["https://**"](remote)

    assert local.continued is True
    assert local.aborted_with is None
    assert remote.continued is False
    assert remote.aborted_with == "blockedbyclient"
