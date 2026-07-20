import os
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from .analyzer import analyze_failure
from .models import EagleEyeBundle, EvidenceArtifact, RunResult
from .security import is_run_url_allowed
from .storage import RUNS, evidence_from_file, safe_id


def _action_timeout_ms() -> int:
    raw = os.getenv("EAGLEEYE_ACTION_TIMEOUT_MS", "5000")
    try:
        value = int(raw)
    except ValueError:
        return 5_000
    return max(1_000, min(value, 300_000))


def run_bundle(bundle: EagleEyeBundle) -> RunResult:
    if not is_run_url_allowed(str(bundle.session.startUrl)):
        raise PermissionError("Automated execution is restricted to localhost by default.")
    session_id = safe_id(bundle.session.id)
    run_dir = RUNS / session_id
    run_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = run_dir / "final.png"
    video_dir = run_dir / "video"
    started = time.perf_counter()
    page = None
    context = None
    browser = None
    video = None
    screenshot: str | None = None
    video_path: Path | None = None
    failure: Exception | None = None
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
                context_options: dict = {}
                if bundle.session.recording:
                    video_dir.mkdir(parents=True, exist_ok=True)
                    context_options = {
                        "record_video_dir": str(video_dir),
                        "record_video_size": {"width": 1280, "height": 720},
                    }
                context = browser.new_context(**context_options)
                _install_network_guard(context)
                page = context.new_page()
                if bundle.session.recording:
                    video = page.video
                    if video is None:
                        raise ValueError("Video recording was requested but no video handle was created.")
                page.set_default_timeout(_action_timeout_ms())
                for event in bundle.session.events:
                    _apply_event(page, event.model_dump(mode="json"))
                _assert_expected_page(page, bundle)
                page.screenshot(path=str(screenshot_path), full_page=True)
                screenshot = str(screenshot_path)
            except (PlaywrightError, TimeoutError, ValueError) as exc:
                failure = exc
                screenshot = _capture_failure_screenshot(page, screenshot_path)
            finally:
                failure = _close_context(context, page, failure)
                if video is not None:
                    try:
                        video_path = Path(video.path())
                    except (PlaywrightError, TimeoutError, ValueError) as exc:
                        if failure is None:
                            failure = ValueError(f"Video finalization failed: {exc}")
                if browser is not None:
                    try:
                        browser.close()
                    except PlaywrightError as exc:
                        if failure is None:
                            failure = exc
    except (PlaywrightError, TimeoutError, ValueError) as exc:
        if failure is None:
            failure = exc

    evidence, evidence_error = _collect_evidence(screenshot, video_path)
    if evidence_error is not None and failure is None:
        failure = evidence_error
    if failure is not None:
        return _failed_result(session_id, started, failure, screenshot, evidence)
    return RunResult(
        session_id=session_id,
        status="passed",
        duration_ms=_elapsed(started),
        screenshot=screenshot,
        evidence=evidence,
    )


def _install_network_guard(context) -> None:
    """Block HTTP(S) requests that leave the configured replay boundary.

    Playwright follows redirects and loads subresources automatically, so
    validating only the original ``page.goto`` URL is not sufficient.
    """

    def guard(route) -> None:
        if is_run_url_allowed(route.request.url):
            route.continue_()
            return
        route.abort("blockedbyclient")

    context.route("http://**", guard)
    context.route("https://**", guard)


def _failed_result(
    session_id: str,
    started: float,
    exc: Exception,
    screenshot: str | None,
    evidence: list[EvidenceArtifact],
) -> RunResult:
    message = str(exc)
    return RunResult(
        session_id=session_id,
        status="failed",
        duration_ms=_elapsed(started),
        screenshot=screenshot,
        evidence=evidence,
        error=message,
        analysis=analyze_failure(message),
    )


def _apply_event(page, event: dict) -> None:
    action = event["action"]
    if action == "goto":
        url = event["url"]
        if not is_run_url_allowed(url):
            raise PermissionError("A recorded navigation left the allowed local target.")
        page.goto(url, wait_until="domcontentloaded")
        return
    locator = _locator(page, event.get("target") or {})
    if action == "click":
        locator.click()
    elif action == "fill":
        value = _synthetic_value(event.get("valueType")) if event.get("redacted") else event.get("value")
        locator.fill(value or "Test User")
    elif action == "select":
        if event.get("redacted"):
            locator.select_option(index=1)
        else:
            value = event.get("value")
            if value == "[SELECT_OPTION]":
                locator.select_option(index=1)
            else:
                locator.select_option(value)
    elif action == "check":
        locator.check()


def _locator(page, target: dict):
    if target.get("role") and target.get("name"):
        return page.get_by_role(target["role"], name=target["name"], exact=True)
    if target.get("name"):
        return page.get_by_label(target["name"], exact=True)
    if target.get("selector"):
        return page.locator(target["selector"])
    raise ValueError("Recorded event has no stable target.")


def _assert_expected_page(page, bundle: EagleEyeBundle) -> None:
    session = bundle.session
    if session.expectedFinalUrl is not None and page.url != str(session.expectedFinalUrl):
        raise ValueError(f"Final URL mismatch: expected {session.expectedFinalUrl}, observed {page.url}")
    if session.expectedPageTitle is not None:
        observed_title = page.title()
        if observed_title != session.expectedPageTitle:
            raise ValueError(
                f"Page title mismatch: expected {session.expectedPageTitle}, observed {observed_title}"
            )
    for heading in session.expectedHeadings:
        if not page.get_by_role("heading", name=heading, exact=True).is_visible():
            raise ValueError(f"Expected heading is not visible: {heading}")


def _elapsed(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _synthetic_value(value_type: str | None) -> str:
    normalized = (value_type or "").casefold()
    if "email" in normalized:
        return "eagleeye-qa@example.invalid"
    if any(marker in normalized for marker in ("password", "secret", "token", "api_key", "apikey")):
        return "EagleEye-Synthetic-1!"
    if "phone" in normalized or "tel" in normalized:
        return "0000000000"
    if "number" in normalized:
        return "1"
    return "EagleEye Test"


def _capture_failure_screenshot(page, screenshot_path: Path) -> str | None:
    if page is None:
        return None
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        return str(screenshot_path)
    except (PlaywrightError, TimeoutError):
        return None


def _close_context(context, page, failure: Exception | None) -> Exception | None:
    if context is None:
        return failure
    try:
        context.close()
    except PlaywrightError as exc:
        if page is not None:
            try:
                page.close()
            except PlaywrightError:
                pass
        return failure or exc
    return failure


def _collect_evidence(
    screenshot: str | None,
    video_path: Path | None,
) -> tuple[list[EvidenceArtifact], Exception | None]:
    evidence: list[EvidenceArtifact] = []
    candidates = (
        (screenshot, "screenshot", "image/png", "playwright.page.screenshot"),
        (
            str(video_path) if video_path is not None else None,
            "video",
            "video/webm",
            "playwright.context.video",
        ),
    )
    for path, kind, mime_type, capture_source in candidates:
        if path is None:
            continue
        try:
            if kind == "video" and Path(path).suffix.casefold() != ".webm":
                raise ValueError("Recorded video does not have the expected WebM extension.")
            evidence.append(
                evidence_from_file(
                    Path(path),
                    kind=kind,
                    mime_type=mime_type,
                    capture_source=capture_source,
                    artifact_root=RUNS,
                )
            )
        except (OSError, ValueError) as exc:
            return evidence, ValueError(f"Evidence finalization failed: {exc}")
    return evidence, None
