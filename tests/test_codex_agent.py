import json
from dataclasses import dataclass
from pathlib import Path

from app import codex_agent


class Completed:
    returncode = 0
    stdout = "Logged in using ChatGPT\n"
    stderr = ""


@dataclass
class Account:
    connected: bool = True


@dataclass
class Structured:
    output: dict


class FakeAppServer:
    def __init__(self) -> None:
        self.call = None

    def account_read(self, *, refresh_token: bool):
        assert refresh_token is False
        return Account()

    def run_structured(self, **kwargs):
        self.call = kwargs
        return Structured({"reasons": ["risk"], "additionalTests": ["auth-boundary"], "anomalies": []})


def test_codex_available_uses_existing_login(monkeypatch) -> None:
    monkeypatch.delenv("EAGLEEYE_CODEX_TRANSPORT", raising=False)
    monkeypatch.setattr(codex_agent, "_app_server", FakeAppServer())
    assert codex_agent.codex_available() is True


def test_codex_agent_uses_app_server_structured_read_only_turn(monkeypatch) -> None:
    fake = FakeAppServer()
    monkeypatch.delenv("EAGLEEYE_CODEX_TRANSPORT", raising=False)
    monkeypatch.setenv("EAGLEEYE_CODEX_MODEL", "gpt-5.6-sol")
    monkeypatch.setattr(codex_agent, "_app_server", fake)

    result = json.loads(codex_agent.invoke_codex_agent("system", "input"))

    assert result["additionalTests"] == ["auth-boundary"]
    assert fake.call["system_prompt"] == "system"
    assert fake.call["prompt"] == "input"
    assert fake.call["output_schema"] == codex_agent.OUTPUT_SCHEMA
    assert fake.call["model"] == "gpt-5.6-sol"
    assert Path(fake.call["cwd"]).name.startswith("eagleeye-codex-")


def test_codex_exec_remains_explicit_compatibility_fallback(monkeypatch) -> None:
    captured = {}
    monkeypatch.setenv("EAGLEEYE_CODEX_TRANSPORT", "exec")
    monkeypatch.setattr(codex_agent.shutil, "which", lambda _: "codex")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(
            json.dumps({"reasons": ["risk"], "additionalTests": ["auth-boundary"], "anomalies": []}),
            encoding="utf-8",
        )
        return Completed()

    monkeypatch.setattr(codex_agent.subprocess, "run", fake_run)
    result = json.loads(codex_agent.invoke_codex_agent("system", "input"))
    assert result["additionalTests"] == ["auth-boundary"]
    assert "--ephemeral" in captured["command"]
    assert "read-only" in captured["command"]
    assert "never" in captured["command"]
    assert "OPENAI_API_KEY" not in captured["environment"]
