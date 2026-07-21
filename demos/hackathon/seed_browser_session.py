from __future__ import annotations

import json
import os
import urllib.request

API_BASE = os.getenv("EAGLEEYE_DEMO_API_BASE", "http://127.0.0.1:8766")
TARGET = os.getenv("EAGLEEYE_DEMO_TARGET_URL", "http://127.0.0.1:8767/")


def request_json(path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(  # noqa: S310 - fixed loopback demo service
        f"{API_BASE}{path}",
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)


def main() -> None:
    session = request_json(
        "/api/v1/browser-agent/sessions",
        {
            "name": "Hackathon fixture journey",
            "goal": "Record the isolated public fixture and generate a bounded regression case",
            "startUrl": TARGET,
            "locale": "en",
        },
    )
    session_id = session["id"]
    observations = [
        {"id": "fixture-goto", "timestamp": 1, "action": "goto", "url": TARGET},
        {
            "id": "fixture-click",
            "timestamp": 2,
            "action": "click",
            "url": TARGET,
            "target": {"role": "link", "name": "Sample Page", "tagName": "a"},
        },
        {
            "id": "fixture-snapshot",
            "timestamp": 3,
            "action": "snapshot",
            "url": f"{TARGET}?page_id=2",
        },
    ]
    for observation in observations:
        observation["redacted"] = False
        request_json(f"/api/v1/browser-agent/sessions/{session_id}/observations", observation)
    generated = request_json(f"/api/v1/browser-agent/sessions/{session_id}/generate")
    print(json.dumps({"sessionId": session_id, "status": generated["status"]}, indent=2))


if __name__ == "__main__":
    main()
