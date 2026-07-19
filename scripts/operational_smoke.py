from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from playwright.async_api import async_playwright

API_URL = "http://127.0.0.1:8766"
MCP_URL = "http://127.0.0.1:8768/mcp"
REPORT_HUB_URL = os.getenv("EAGLEEYE_REPORT_HUB_URL", "http://127.0.0.1:8780/reports/health")
REQUIRED_MCP_TOOLS = {
    "eagleeye_status",
    "generate_test_profile",
    "evaluate_gate",
    "check_test_case_quality",
    "get_test_evidence",
    "prepare_local_run",
    "list_ai_providers",
    "guided_list_scenarios",
    "guided_register_scenario",
    "guided_prepare_session",
    "guided_session_status",
    "guided_next_step",
    "guided_control_session",
    "guided_record_human_result",
    "guided_get_retest",
    "discover_project_qa",
    "run_project_qa",
    "project_qa_run_status",
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def check_api(api_url: str) -> dict[str, Any]:
    with httpx.Client(timeout=10, trust_env=False) as client:
        health = client.get(f"{api_url}/health")
        health.raise_for_status()
        body = health.json()
        configuration = client.get(f"{api_url}/api/v1/configuration")
        configuration.raise_for_status()
    return {
        "ok": body.get("status") == "ok",
        "version": body.get("version"),
        "service": body.get("service"),
        "configurationStatus": configuration.status_code,
    }


async def check_mcp(mcp_url: str) -> dict[str, Any]:
    async with streamable_http_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            status = await session.call_tool("eagleeye_status")
    missing = sorted(REQUIRED_MCP_TOOLS - names)
    return {
        "ok": not missing and not status.isError,
        "toolCount": len(names),
        "missingTools": missing,
        "statusCallError": status.isError,
    }


async def check_browser(api_url: str) -> dict[str, Any]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            response = await page.goto(f"{api_url}/", wait_until="domcontentloaded", timeout=30_000)
            text = await page.locator("body").inner_text()
            title = await page.title()
        finally:
            await browser.close()
    status = response.status if response else 0
    return {
        "ok": status == 200 and "EagleEye" in text,
        "httpStatus": status,
        "title": title,
        "bodyContainsEagleEye": "EagleEye" in text,
    }


def check_report_hub(url: str) -> dict[str, Any]:
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        body = response.json()
    return {
        "ok": body.get("status") == "ok" and body.get("service") == "report-hub",
        "status": response.status_code,
        "service": body.get("service"),
    }


def passed(checks: dict[str, dict[str, Any]]) -> bool:
    return bool(checks) and all(result.get("ok") is True for result in checks.values())


async def run(args: argparse.Namespace) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    operations = [("api", lambda: check_api(args.api_url)), ("mcp", lambda: check_mcp(args.mcp_url))]
    if not args.skip_browser:
        operations.append(("browser", lambda: check_browser(args.api_url)))
    if not args.skip_report_hub:
        operations.append(("reportHub", lambda: check_report_hub(args.report_hub_url)))

    for name, operation in operations:
        try:
            result = operation()
            checks[name] = await result if asyncio.iscoroutine(result) else result
        except Exception as exc:  # noqa: BLE001 - smoke report must preserve boundary failures
            checks[name] = {"ok": False}
            errors.append({"check": name, "error": f"{type(exc).__name__}: {exc}"})

    return {
        "schemaVersion": 1,
        "startedAt": args.started_at,
        "finishedAt": now(),
        "status": "PASS" if passed(checks) else "FAIL",
        "checks": checks,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EagleEye operational smoke")
    parser.add_argument("--api-url", default=API_URL)
    parser.add_argument("--mcp-url", default=MCP_URL)
    parser.add_argument("--report-hub-url", default=REPORT_HUB_URL)
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--skip-report-hub", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    args.started_at = now()
    return args


def main() -> int:
    args = parse_args()
    report = asyncio.run(run(args))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
