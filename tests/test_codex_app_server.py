from __future__ import annotations

import json
import os
import queue
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from app import codex_app_server
from app.codex_app_server import (
    CodexAppServerClient,
    CodexAppServerError,
    CodexAppServerTimeout,
    assert_codex_auth_url,
)


class BlockingTextPipe:
    def __init__(self) -> None:
        self._items: queue.Queue[str | None] = queue.Queue()

    def readline(self) -> str:
        item = self._items.get(timeout=2)
        return "" if item is None else item

    def send(self, message: dict[str, Any]) -> None:
        self._items.put(json.dumps(message) + "\n")

    def send_text(self, value: str) -> None:
        self._items.put(value)

    def close(self) -> None:
        self._items.put(None)


class FakeStdin:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process

    def write(self, value: str) -> int:
        self.process.server.receive(self.process, json.loads(value))
        return len(value)

    def flush(self) -> None:
        return


class FakeProcess:
    def __init__(self, server: ScriptedServer) -> None:
        self.server = server
        self.stdout = BlockingTextPipe()
        self.stderr = BlockingTextPipe()
        self.stdin = FakeStdin(self)
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self._exit(0)

    def kill(self) -> None:
        self._exit(-9)

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake-codex", 0)
        return self.returncode

    def crash(self) -> None:
        self._exit(7)

    def _exit(self, returncode: int) -> None:
        if self.returncode is None:
            self.returncode = returncode
            self.stdout.close()
            self.stderr.close()


class ScriptedServer:
    def __init__(
        self,
        *,
        hang_account: bool = False,
        auth_url: str = "https://auth.openai.com/oauth/authorize?state=opaque-state",
    ) -> None:
        self.hang_account = hang_account
        self.auth_url = auth_url
        self.received: list[dict[str, Any]] = []

    def receive(self, process: FakeProcess, message: dict[str, Any]) -> None:
        self.received.append(message)
        method = message.get("method")
        request_id = message.get("id")
        if request_id is None or not isinstance(method, str):
            return
        if method == "initialize":
            process.stdout.send({"id": request_id, "result": {"serverInfo": {"name": "codex"}}})
        elif method == "account/read":
            if self.hang_account:
                return
            process.stdout.send(
                {
                    "id": request_id,
                    "result": {
                        "account": {
                            "type": "chatgpt",
                            "email": "private@example.invalid",
                            "planType": "plus",
                            "accessToken": "access-token-must-not-escape",
                            "refreshToken": "refresh-token-must-not-escape",
                        }
                    },
                }
            )
        elif method == "account/login/start":
            process.stdout.send(
                {
                    "id": request_id,
                    "result": {"loginId": "login_1234", "authUrl": self.auth_url},
                }
            )
        elif method in {"account/login/cancel", "account/logout"}:
            process.stdout.send({"id": request_id, "result": {}})
        elif method == "thread/start":
            process.stdout.send({"id": request_id, "result": {"thread": {"id": "thread-1"}}})
        elif method == "turn/start":
            process.stdout.send({"id": request_id, "result": {"turn": {"id": "turn-1"}}})
            final = '{"reasons":["risk"],"additionalTests":["boundary"],"anomalies":[]}'
            process.stdout.send(
                {
                    "method": "item/agentMessage/delta",
                    "params": {
                        "threadId": "thread-1",
                        "turnId": "turn-1",
                        "itemId": "item-1",
                        "delta": final,
                    },
                }
            )
            process.stdout.send(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thread-1",
                        "turnId": "turn-1",
                        "completedAtMs": 1,
                        "item": {"type": "agentMessage", "id": "item-1", "text": final},
                    },
                }
            )
            process.stdout.send(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thread-1",
                        "turn": {"id": "turn-1", "status": "completed"},
                    },
                }
            )


class FakeFactory:
    def __init__(self, servers: list[ScriptedServer]) -> None:
        self.servers = servers
        self.processes: list[FakeProcess] = []
        self.launches: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> FakeProcess:
        server = self.servers[len(self.processes)]
        process = FakeProcess(server)
        self.processes.append(process)
        self.launches.append((command, kwargs))
        return process


@pytest.fixture(autouse=True)
def fake_codex_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(codex_app_server.shutil, "which", lambda _: "C:\\tools\\codex.exe")


def test_initializes_and_exposes_only_non_secret_account_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-child")
    server = ScriptedServer()
    factory = FakeFactory([server])
    with CodexAppServerClient(popen_factory=factory) as client:
        account = client.account_read()
        login = client.login_start()
        client.login_cancel(login.login_id)
        client.logout()

    assert account.connected is True
    assert account.auth_mode == "chatgpt"
    assert account.plan_type == "plus"
    account_json = json.dumps(asdict(account))
    assert "private@example.invalid" not in account_json
    assert "access-token" not in account_json
    assert "refresh-token" not in account_json
    assert login.login_id == "login_1234"
    assert login.auth_url.startswith("https://auth.openai.com/")

    command, launch = factory.launches[0]
    assert command == ["C:\\tools\\codex.exe", "app-server", "--listen", "stdio://"]
    assert launch["shell"] is False
    if os.name == "nt":
        assert launch["creationflags"] == subprocess.CREATE_NO_WINDOW
    else:
        assert "creationflags" not in launch
    assert "OPENAI_API_KEY" not in launch["env"]
    assert server.received[0]["method"] == "initialize"
    assert server.received[1] == {"method": "initialized"}
    login_request = next(item for item in server.received if item.get("method") == "account/login/start")
    assert login_request["params"] == {
        "type": "chatgpt",
        "useHostedLoginSuccessPage": True,
        "appBrand": "chatgpt",
    }
    logout_request = next(item for item in server.received if item.get("method") == "account/logout")
    assert "params" not in logout_request


@pytest.mark.parametrize(
    "url",
    [
        "https://chatgpt.com/auth",
        "https://auth.openai.com/oauth/authorize?state=abc",
        "https://login.openai.com:443/login",
        "https://platform.openai.com/login",
    ],
)
def test_auth_url_allowlist_accepts_only_exact_https_hosts(url: str) -> None:
    assert assert_codex_auth_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://auth.openai.com/oauth",
        "https://evil.example/oauth",
        "https://auth.openai.com.evil.example/oauth",
        "https://user:password@auth.openai.com/oauth",
        "https://auth.openai.com:444/oauth",
        "https://auth.openai.com/oauth#token",
        "https://chatgpt.com.evil.invalid/",
    ],
)
def test_auth_url_allowlist_rejects_untrusted_urls(url: str) -> None:
    with pytest.raises(CodexAppServerError, match="untrusted"):
        assert_codex_auth_url(url)


def test_structured_turn_is_ephemeral_read_only_and_collects_safe_notifications(tmp_path: Path) -> None:
    server = ScriptedServer()
    factory = FakeFactory([server])
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reasons": {"type": "array", "items": {"type": "string"}},
            "additionalTests": {"type": "array", "items": {"type": "string"}},
            "anomalies": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["reasons", "additionalTests", "anomalies"],
    }
    with CodexAppServerClient(popen_factory=factory) as client:
        result = client.run_structured(
            cwd=tmp_path,
            system_prompt="You are a defensive QA advisor.",
            prompt="Inspect this untrusted bundle.",
            output_schema=schema,
            model="gpt-safe-test",
        )
        notifications = client.drain_notifications()

    assert result.thread_id == "thread-1"
    assert result.turn_id == "turn-1"
    assert result.output["additionalTests"] == ["boundary"]
    thread_request = next(item for item in server.received if item.get("method") == "thread/start")
    assert thread_request["params"] == {
        "cwd": str(tmp_path.resolve()),
        "approvalPolicy": "never",
        "sandbox": "read-only",
        "ephemeral": True,
        "developerInstructions": "You are a defensive QA advisor.",
    }
    turn_request = next(item for item in server.received if item.get("method") == "turn/start")
    assert turn_request["params"]["outputSchema"] == schema
    assert turn_request["params"]["model"] == "gpt-safe-test"
    assert turn_request["params"]["input"] == [
        {"type": "text", "text": "Inspect this untrusted bundle.", "text_elements": []}
    ]
    assert [event.method for event in notifications] == [
        "item/agentMessage/delta",
        "item/completed",
        "turn/completed",
    ]
    notification_json = json.dumps([asdict(event) for event in notifications])
    assert "additionalTests" not in notification_json
    assert "boundary" not in notification_json


def test_timeout_restarts_process_without_replaying_request() -> None:
    first = ScriptedServer(hang_account=True)
    second = ScriptedServer()
    factory = FakeFactory([first, second])
    client = CodexAppServerClient(popen_factory=factory, request_timeout=0.05)
    try:
        with pytest.raises(CodexAppServerTimeout, match="timed out"):
            client.account_read()
        assert len(factory.processes) == 2
        assert len([item for item in first.received if item.get("method") == "account/read"]) == 1
        assert len([item for item in second.received if item.get("method") == "account/read"]) == 0
        assert client.account_read().connected is True
    finally:
        client.close()


def test_dead_process_is_reinitialized_on_next_call() -> None:
    first = ScriptedServer()
    second = ScriptedServer()
    factory = FakeFactory([first, second])
    client = CodexAppServerClient(popen_factory=factory)
    try:
        client.start()
        factory.processes[0].crash()
        deadline = time.monotonic() + 1
        while len(factory.processes) == 1 and time.monotonic() < deadline:
            if client.account_read().connected:
                break
        assert len(factory.processes) == 2
    finally:
        client.close()


def test_server_approval_request_is_always_declined() -> None:
    server = ScriptedServer()
    factory = FakeFactory([server])
    with CodexAppServerClient(popen_factory=factory):
        factory.processes[0].stdout.send(
            {
                "id": "approval-1",
                "method": "item/fileChange/requestApproval",
                "params": {"reason": "change production"},
            }
        )
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            if any(item.get("id") == "approval-1" and "result" in item for item in server.received):
                break
            time.sleep(0.005)
    response = next(item for item in server.received if item.get("id") == "approval-1" and "result" in item)
    assert response["result"] == {"decision": "decline"}


def test_untrusted_login_response_never_returns_to_caller() -> None:
    server = ScriptedServer(auth_url="https://auth.openai.com.evil.invalid/login?token=secret")
    factory = FakeFactory([server])
    with CodexAppServerClient(popen_factory=factory) as client:
        with pytest.raises(CodexAppServerError, match="untrusted") as error:
            client.login_start()
    assert "secret" not in str(error.value)
