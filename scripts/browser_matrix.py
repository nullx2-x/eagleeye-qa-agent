from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import async_playwright

BROWSERS = ("chromium", "firefox", "webkit")


async def check(url: str) -> dict:
    results = []
    async with async_playwright() as playwright:
        for name in BROWSERS:
            browser_type = getattr(playwright, name)
            try:
                browser = await browser_type.launch(headless=True)
                try:
                    page = await browser.new_page(viewport={"width": 1280, "height": 800})
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    body = await page.locator("body").inner_text()
                    status = response.status if response else 0
                    ok = status == 200 and "EagleEye" in body
                    results.append(
                        {"browser": name, "status": "PASS" if ok else "FAIL", "httpStatus": status}
                    )
                finally:
                    await browser.close()
            except Exception as exc:  # noqa: BLE001 - compatibility report captures missing engine details
                results.append(
                    {"browser": name, "status": "INFRA_ERROR", "error": f"{type(exc).__name__}: {exc}"}
                )
    return {
        "schemaVersion": 1,
        "finishedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EagleEye Chromium/Firefox/WebKit smoke matrix")
    parser.add_argument("--url", default="http://127.0.0.1:8766/")
    parser.add_argument("--output", type=Path, default=Path(".runtime/browser-matrix/latest.json"))
    args = parser.parse_args()
    report = asyncio.run(check(args.url))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
