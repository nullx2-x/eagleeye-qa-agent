"""Run the real EagleEye Chrome-extension to WordPress Build Week proof.

This is a headed release check because Chromium does not load unpacked
extensions in the ordinary headless path. It records only the public local
WordPress fixture and writes publication-safe screenshots and a JSON receipt.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API_BASE = "http://127.0.0.1:8766"
WORDPRESS_URL = "http://127.0.0.1:8888/"


def packaged_extension_id() -> str:
    manifest = json.loads((ROOT / "chrome-extension" / "manifest.json").read_text(encoding="utf-8"))
    public_key = base64.b64decode(manifest["key"], validate=True)
    digest = hashlib.sha256(public_key).hexdigest()[:32]
    return "".join(chr(ord("a") + int(character, 16)) for character in digest)


EXTENSION_ID = packaged_extension_id()
EXTENSION_URL = f"chrome-extension://{EXTENSION_ID}/popup.html"
SCREENSHOTS = ROOT / "docs" / "build-week" / "screenshots"
EVIDENCE = ROOT / "docs" / "build-week" / "evidence"


def api_json(path: str) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 - exact loopback URL only
        f"{API_BASE}{path}",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310  # nosec B310
        return json.load(response)


def click_background(page: Page, selector: str) -> None:
    """Click an extension control without changing Chrome's active target tab."""

    page.evaluate(
        "selector => document.querySelector(selector).click()",
        selector,
    )


def assert_no_popup_error(page: Page) -> None:
    panel = page.locator("#error-panel")
    if panel.get_attribute("hidden") is None:
        message = page.locator("#error-message").text_content() or "unknown extension error"
        raise RuntimeError(message)


def screenshot_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publication_safe_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_items: list[dict[str, Any]] = []
    for item in items:
        safe = dict(item)
        path_value = safe.get("path")
        if isinstance(path_value, str):
            path = Path(path_value)
            if path.is_absolute():
                try:
                    safe["path"] = path.resolve().relative_to(ROOT.resolve()).as_posix()
                except ValueError:
                    safe["path"] = "[redacted-local-path]"
            safe["path"] = re.sub(
                r"(artifacts/runs/)[^/]+",
                r"\1[redacted-run-id]",
                str(safe["path"]).replace("\\", "/"),
            )
            safe["path"] = re.sub(
                r"(/video/)[^/]+\.webm$",
                r"\1[redacted-video-name].webm",
                safe["path"],
            )
        safe_items.append(safe)
    return safe_items


def main() -> None:
    extension = ROOT / "chrome-extension"
    profile = ROOT / ".runtime" / f"build-week-extension-{uuid4().hex}"
    profile.mkdir(parents=True, exist_ok=False)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    before_count = len(api_json("/api/v1/browser-agent/sessions")["sessions"])
    started = time.perf_counter()

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            args=[
                f"--disable-extensions-except={extension}",
                f"--load-extension={extension}",
                "--window-size=1440,1000",
            ],
            viewport={"width": 1400, "height": 900},
            color_scheme="dark",
            reduced_motion="reduce",
        )
        worker = (
            context.service_workers[0]
            if context.service_workers
            else context.wait_for_event("serviceworker", timeout=15_000)
        )
        if worker.url != f"chrome-extension://{EXTENSION_ID}/background.js":
            raise RuntimeError(f"Unexpected extension worker: {worker.url}")

        wordpress = context.pages[0]
        wordpress.goto(WORDPRESS_URL, wait_until="domcontentloaded", timeout=60_000)
        expect(wordpress).to_have_title(re.compile("EagleEye WP Lab"), timeout=20_000)

        # OFF proof: a real navigation must not create a browser-agent session.
        wordpress.get_by_role("link", name="Sample Page", exact=True).first.click()
        wordpress.wait_for_load_state("domcontentloaded", timeout=60_000)
        wordpress.wait_for_timeout(800)
        off_count = len(api_json("/api/v1/browser-agent/sessions")["sessions"])
        if off_count != before_count:
            raise RuntimeError("Extension OFF created a session unexpectedly.")
        wordpress.goto(WORDPRESS_URL, wait_until="domcontentloaded", timeout=60_000)

        popup = context.new_page()
        popup.goto(EXTENSION_URL, wait_until="domcontentloaded", timeout=20_000)
        expect(popup).to_have_title("EagleEye Browser QA")
        expect(popup.locator("#start-button")).to_be_disabled(timeout=10_000)
        popup.locator("#privacy-consent").check()
        expect(popup.locator("#start-button")).to_be_enabled(timeout=10_000)
        assert_no_popup_error(popup)
        popup.locator("#session-name").fill("Build Week WordPress Journey")
        popup.locator("#session-goal").fill(
            "通常操作から主要導線を記録し、AIテスト生成、Replay、証跡レポートまで確認する"
        )
        popup.locator("#capture-screenshot").check()

        wordpress.bring_to_front()
        print("EAGLEEYE_WAITING_FOR_EXTENSION_SHORTCUT", flush=True)
        grant_deadline = time.monotonic() + 180
        while time.monotonic() < grant_deadline:
            active_tabs = popup.evaluate("chrome.tabs.query({active:true,currentWindow:true})")
            if active_tabs and active_tabs[0].get("url", "").startswith(WORDPRESS_URL):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(
                "Chrome activeTab permission was not granted. Invoke the EagleEye action once."
            )

        click_background(popup, "#start-button")
        expect(popup.locator("#status-badge")).to_have_text("記録中", timeout=30_000)
        assert_no_popup_error(popup)

        popup.bring_to_front()
        popup.locator("body").screenshot(path=SCREENSHOTS / "02-extension-recording.png")
        wordpress.bring_to_front()
        wordpress.get_by_role("link", name="Sample Page", exact=True).first.click()
        wordpress.wait_for_load_state("domcontentloaded", timeout=60_000)
        wordpress.wait_for_timeout(2_500)
        wordpress.screenshot(path=SCREENSHOTS / "03-wordpress-observed.png", full_page=True)

        wordpress.bring_to_front()
        click_background(popup, "#stop-button")
        expect(popup.locator("#status-badge")).to_have_text("記録停止", timeout=30_000)
        assert_no_popup_error(popup)

        click_background(popup, "#generate-button")
        expect(popup.locator("#status-badge")).to_have_text("生成済み", timeout=180_000)
        assert_no_popup_error(popup)

        click_background(popup, "#replay-button")
        expect(popup.locator("#status-badge")).to_have_text(
            re.compile(r"^(PASS|FAIL)$"),
            timeout=180_000,
        )
        assert_no_popup_error(popup)
        popup.locator("body").screenshot(path=SCREENSHOTS / "04-replay-result.png")

        state = popup.evaluate("chrome.runtime.sendMessage({type:'GET_STATE'})")
        if not state or not state.get("ok") or not state.get("state"):
            raise RuntimeError("Extension state was unavailable after Replay.")
        session_id = state["state"]["sessionId"]
        session = api_json(f"/api/v1/browser-agent/sessions/{session_id}")

        dashboard = context.new_page()
        dashboard.goto(f"{API_BASE}/", wait_until="networkidle", timeout=30_000)
        dashboard.screenshot(path=SCREENSHOTS / "01-dashboard.png", full_page=True)
        dashboard.locator("#tab-tests").click()
        dashboard.screenshot(path=SCREENSHOTS / "05-test-list.png", full_page=True)

        report = context.new_page()
        report.goto(
            f"{API_BASE}/api/v1/browser-agent/sessions/{session_id}/report",
            wait_until="networkidle",
            timeout=30_000,
        )
        expect(report).to_have_title(re.compile("EagleEye"))
        report.screenshot(path=SCREENSHOTS / "06-report.png", full_page=True)
        context.close()

    screenshots = sorted(SCREENSHOTS.glob("*.png"))
    run = session.get("run") or {}
    quality = session.get("caseQuality") or {}
    gate = session.get("qualityGate") or {}
    receipt = {
        "result": "PASS" if session["status"] == "passed" else "FAIL",
        "sessionId": "[redacted-session-id]",
        "extensionIdentity": "fixed public manifest identity; value omitted from report",
        "extensionOffSessionDelta": off_count - before_count,
        "target": WORDPRESS_URL,
        "observations": len(session["observations"]),
        "generatedCases": len(session["generatedCases"]),
        "ai": session.get("ai"),
        "caseQuality": {
            "decision": quality.get("decision"),
            "score": quality.get("score"),
        },
        "replay": {
            "status": run.get("status"),
            "durationMs": run.get("duration_ms"),
            "evidence": publication_safe_evidence(run.get("evidence", [])),
            "qualityGate": gate.get("decision"),
        },
        "screenshotAvailable": session["screenshotAvailable"],
        "screenshots": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": screenshot_hash(path),
                "bytes": path.stat().st_size,
            }
            for path in screenshots
        ],
        "elapsedSeconds": round(time.perf_counter() - started, 1),
    }
    evidence_path = EVIDENCE / "extension-wordpress-e2e.json"
    evidence_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt["result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
