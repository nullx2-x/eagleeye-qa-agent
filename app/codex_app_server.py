from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class CodexAppServerError(RuntimeError):
    """Raised when the local Codex App Server cannot complete a safe request."""


class CodexAppServerTimeout(CodexAppServerError):
    """Raised after a request times out and the App Server has been restarted."""


@dataclass(frozen=True, slots=True)
class CodexAccountSummary:
    """Non-secret account state suitable for returning from EagleEye APIs."""

    connected: bool
    auth_mode: str | None
    plan_type: str | None


@dataclass(frozen=True, slots=True)
class CodexLoginStart:
    """Browser hand-off details for a ChatGPT OAuth login."""

    login_id: str
    auth_url: str


@dataclass(frozen=True, slots=True)
class CodexNotification:
    """A deliberately metadata-only App Server notification."""

    method: str
    thread_id: str | None = None
    turn_id: str | None = None
    item_id: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class StructuredTurnResult:
    """Validated JSON object returned by a read-only ephemeral Codex turn."""

    thread_id: str
    turn_id: str
    output: dict[str, Any]


_AUTH_HOSTS = frozenset(
    {
        "auth.openai.com",
        "chatgpt.com",
        "login.openai.com",
        "platform.openai.com",
    }
)
_LOGIN_ID = re.compile(r"^[A-Za-z0-9_-]{4,200}$")
_SECRET_TEXT = re.compile(
    r"(?i)(bearer\s+|access[_-]?token\s*[:=]\s*|refresh[_-]?token\s*[:=]\s*|"
    r"authorization\s*[:=]\s*|api[_-]?key\s*[:=]\s*|client[_-]?secret\s*[:=]\s*)"
    r"[^\s,;&]+"
)
_MAX_JSONL_BYTES = 4 * 1024 * 1024
_MAX_SCHEMA_BYTES = 256 * 1024
_MAX_RESULT_BYTES = 1024 * 1024


def assert_codex_auth_url(candidate: str) -> str:
    """Return a Codex login URL only when it matches the strict HTTPS allowlist."""

    if not isinstance(candidate, str) or not candidate or len(candidate) > 4096:
        raise CodexAppServerError("Codex returned an invalid authentication URL.")
    if any(ord(character) < 32 for character in candidate):
        raise CodexAppServerError("Codex returned an invalid authentication URL.")
    try:
        url = urlsplit(candidate)
        port = url.port
    except ValueError as exc:
        raise CodexAppServerError("Codex returned an invalid authentication URL.") from exc
    if (
        url.scheme.lower() != "https"
        or url.hostname is None
        or url.hostname.lower() not in _AUTH_HOSTS
        or port not in (None, 443)
        or url.username is not None
        or url.password is not None
        or bool(url.fragment)
    ):
        raise CodexAppServerError("Codex returned an untrusted authentication URL.")
    return candidate


class CodexAppServerClient:
    """Synchronous stdio JSONL client for the locally authenticated Codex App Server.

    The Codex process owns ChatGPT credentials. This client exposes only a compact
    account summary, never the raw ``account/read`` response, stderr, or token fields.
    It supports one structured turn at a time; ordinary RPC calls remain thread-safe.
    """

    def __init__(
        self,
        *,
        command: str | None = None,
        cwd: str | Path | None = None,
        request_timeout: float = 15.0,
        turn_timeout: float = 120.0,
        client_version: str = "1.0.0",
        popen_factory: Callable[..., Any] | None = None,
    ) -> None:
        if request_timeout <= 0 or turn_timeout <= 0:
            raise ValueError("Timeouts must be positive.")
        self._configured_command = command
        self._cwd = Path(cwd).resolve() if cwd is not None else None
        self._request_timeout = request_timeout
        self._turn_timeout = turn_timeout
        self._client_version = client_version
        self._popen_factory = popen_factory or subprocess.Popen

        self._process: Any | None = None
        self._request_id = 0
        self._pending: dict[int, queue.Queue[object]] = {}
        self._notifications: deque[CodexNotification] = deque(maxlen=500)
        self._turn_events: dict[str, threading.Event] = {}
        self._turn_status: dict[str, str] = {}
        self._agent_text: dict[tuple[str, str], str] = {}
        self._completed_messages: dict[str, list[str]] = {}
        self._stderr_tail = ""

        self._state_lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._turn_lock = threading.Lock()
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    def __enter__(self) -> CodexAppServerClient:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def start(self) -> None:
        """Start and initialize App Server if it is not already healthy."""

        with self._lifecycle_lock:
            process = self._process
            if process is not None and process.poll() is None:
                return
            if process is not None:
                self._discard_process(process)

            executable = _resolve_codex_executable(self._configured_command)
            launch_options: dict[str, Any] = {
                "cwd": str(self._cwd) if self._cwd is not None else None,
                "env": _minimal_environment(),
                "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "bufsize": 1,
                "shell": False,
            }
            if os.name == "nt":
                launch_options["creationflags"] = subprocess.CREATE_NO_WINDOW
            try:
                process = self._popen_factory(  # noqa: S603 -- executable is resolved without a shell
                    [executable, "app-server", "--listen", "stdio://"],
                    **launch_options,
                )
            except OSError as exc:
                raise CodexAppServerError("Codex App Server could not be started.") from exc
            if process.stdin is None or process.stdout is None or process.stderr is None:
                _terminate_process(process)
                raise CodexAppServerError("Codex App Server did not expose stdio pipes.")

            with self._state_lock:
                self._process = process
                self._stderr_tail = ""
            self._stdout_thread = threading.Thread(
                target=self._read_stdout,
                args=(process,),
                name="eagleeye-codex-stdout",
                daemon=True,
            )
            self._stderr_thread = threading.Thread(
                target=self._read_stderr,
                args=(process,),
                name="eagleeye-codex-stderr",
                daemon=True,
            )
            self._stdout_thread.start()
            self._stderr_thread.start()
            try:
                self._rpc_request(
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "eagleeye_qa_agent",
                            "title": "EagleEye QA Agent",
                            "version": self._client_version,
                        },
                        "capabilities": {
                            "experimentalApi": False,
                            "requestAttestation": False,
                        },
                    },
                    self._request_timeout,
                )
                self._notify("initialized")
            except Exception:
                self._discard_process(process)
                raise

    def close(self) -> None:
        """Stop App Server and reject all waiting calls."""

        with self._lifecycle_lock:
            process = self._process
            if process is not None:
                self._discard_process(process)

    def restart(self) -> None:
        """Replace App Server with a fresh initialized process."""

        with self._lifecycle_lock:
            self.close()
            self.start()

    def account_read(self, *, refresh_token: bool = False) -> CodexAccountSummary:
        """Read non-secret ChatGPT account state from App Server."""

        result = self._call("account/read", {"refreshToken": refresh_token})
        account = _mapping(result.get("account"))
        if account is None:
            return CodexAccountSummary(connected=False, auth_mode=None, plan_type=None)
        account_type = account.get("type")
        auth_mode = account_type if account_type in {"chatgpt", "apiKey", "amazonBedrock"} else "other"
        plan = account.get("planType")
        plan_type = _redact_text(plan)[:80] if isinstance(plan, str) else None
        return CodexAccountSummary(connected=True, auth_mode=auth_mode, plan_type=plan_type)

    def login_start(self) -> CodexLoginStart:
        """Start App Server-managed ChatGPT OAuth and return its trusted browser URL."""

        result = self._call(
            "account/login/start",
            {
                "type": "chatgpt",
                "useHostedLoginSuccessPage": True,
                "appBrand": "chatgpt",
            },
        )
        login_id = result.get("loginId")
        auth_url = result.get("authUrl")
        if not isinstance(login_id, str) or not _LOGIN_ID.fullmatch(login_id):
            raise CodexAppServerError("Codex returned an invalid login identifier.")
        if not isinstance(auth_url, str):
            raise CodexAppServerError("Codex returned an invalid authentication URL.")
        return CodexLoginStart(login_id=login_id, auth_url=assert_codex_auth_url(auth_url))

    def login_cancel(self, login_id: str) -> None:
        """Cancel an App Server-managed login without handling any OAuth token."""

        if not isinstance(login_id, str) or not _LOGIN_ID.fullmatch(login_id):
            raise CodexAppServerError("Invalid Codex login identifier.")
        self._call("account/login/cancel", {"loginId": login_id})

    def logout(self) -> None:
        """Ask App Server to clear its own authentication state."""

        self._call("account/logout", None)

    def drain_notifications(self) -> tuple[CodexNotification, ...]:
        """Return and clear safe notification metadata collected so far."""

        with self._state_lock:
            result = tuple(self._notifications)
            self._notifications.clear()
        return result

    def run_structured(
        self,
        *,
        cwd: str | Path,
        system_prompt: str,
        prompt: str,
        output_schema: Mapping[str, Any],
        model: str | None = None,
        timeout: float | None = None,
    ) -> StructuredTurnResult:
        """Run one read-only ephemeral turn constrained by a JSON object schema."""

        root = Path(cwd).resolve()
        if not root.is_dir():
            raise CodexAppServerError("Codex working directory is unavailable.")
        system = system_prompt.strip()
        content = prompt.strip()
        if not system or len(system) > 20_000:
            raise CodexAppServerError("System prompt must be between 1 and 20,000 characters.")
        if not content or len(content) > 100_000:
            raise CodexAppServerError("Prompt must be between 1 and 100,000 characters.")
        schema = dict(output_schema)
        if schema.get("type") != "object":
            raise CodexAppServerError("Structured output schema must describe a JSON object.")
        try:
            schema_bytes = json.dumps(schema, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise CodexAppServerError("Structured output schema is not JSON serializable.") from exc
        if len(schema_bytes) > _MAX_SCHEMA_BYTES:
            raise CodexAppServerError("Structured output schema is too large.")
        selected_model = model.strip() if isinstance(model, str) else None
        if selected_model is not None and (not selected_model or len(selected_model) > 200):
            raise CodexAppServerError("Codex model identifier is invalid.")
        turn_timeout = timeout if timeout is not None else self._turn_timeout
        if turn_timeout <= 0:
            raise CodexAppServerError("Turn timeout must be positive.")

        with self._turn_lock:
            thread_result = self._call(
                "thread/start",
                {
                    "cwd": str(root),
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "ephemeral": True,
                    "developerInstructions": system,
                },
            )
            thread = _mapping(thread_result.get("thread"))
            thread_id = thread.get("id") if thread is not None else None
            if not isinstance(thread_id, str) or not thread_id:
                raise CodexAppServerError("Codex did not return a thread identifier.")

            turn_params: dict[str, Any] = {
                "threadId": thread_id,
                "input": [{"type": "text", "text": content, "text_elements": []}],
                "outputSchema": schema,
            }
            if selected_model is not None:
                turn_params["model"] = selected_model
            turn_result = self._call("turn/start", turn_params)
            turn = _mapping(turn_result.get("turn"))
            turn_id = turn.get("id") if turn is not None else None
            if not isinstance(turn_id, str) or not turn_id:
                raise CodexAppServerError("Codex did not return a turn identifier.")
            event = self._turn_event(turn_id)
            if not event.wait(turn_timeout):
                self._recover_after_failure()
                raise CodexAppServerTimeout("Codex structured turn timed out; App Server was restarted.")

            with self._state_lock:
                status = self._turn_status.pop(turn_id, None)
                messages = self._completed_messages.pop(turn_id, [])
                if not messages:
                    messages = [
                        text
                        for (candidate_turn, _), text in self._agent_text.items()
                        if candidate_turn == turn_id and text
                    ]
                self._turn_events.pop(turn_id, None)
                for key in [key for key in self._agent_text if key[0] == turn_id]:
                    self._agent_text.pop(key, None)
            if status != "completed":
                raise CodexAppServerError("Codex structured turn did not complete successfully.")
            if not messages:
                raise CodexAppServerError("Codex structured turn returned no assistant result.")
            raw_output = messages[-1].strip()
            if len(raw_output.encode("utf-8")) > _MAX_RESULT_BYTES:
                raise CodexAppServerError("Codex structured result is too large.")
            try:
                parsed = json.loads(raw_output)
            except json.JSONDecodeError as exc:
                raise CodexAppServerError("Codex structured result was not valid JSON.") from exc
            if not isinstance(parsed, dict):
                raise CodexAppServerError("Codex structured result was not a JSON object.")
            return StructuredTurnResult(thread_id=thread_id, turn_id=turn_id, output=parsed)

    def _call(self, method: str, params: Mapping[str, Any] | None) -> dict[str, Any]:
        self.start()
        try:
            return self._rpc_request(method, params, self._request_timeout)
        except CodexAppServerTimeout as exc:
            self._recover_after_failure()
            raise CodexAppServerTimeout(f"{method} timed out; App Server was restarted.") from exc
        except CodexAppServerError:
            process = self._process
            if process is None or process.poll() is not None:
                self._recover_after_failure()
            raise

    def _rpc_request(
        self,
        method: str,
        params: Mapping[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        with self._state_lock:
            process = self._process
            if process is None or process.poll() is not None:
                raise CodexAppServerError("Codex App Server is not running.")
            self._request_id += 1
            request_id = self._request_id
            response_queue: queue.Queue[object] = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue
        payload: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            payload["params"] = dict(params)
        try:
            self._write_json(process, payload)
        except Exception:
            with self._state_lock:
                self._pending.pop(request_id, None)
            raise
        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty as exc:
            with self._state_lock:
                self._pending.pop(request_id, None)
            raise CodexAppServerTimeout(f"{method} timed out.") from exc
        if isinstance(response, Exception):
            raise response
        if not isinstance(response, dict):
            raise CodexAppServerError("Codex App Server returned an invalid response.")
        return response

    def _notify(self, method: str, params: Mapping[str, Any] | None = None) -> None:
        with self._state_lock:
            process = self._process
        if process is None or process.poll() is not None:
            raise CodexAppServerError("Codex App Server is not running.")
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = dict(params)
        self._write_json(process, payload)

    def _write_json(self, process: Any, payload: Mapping[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        if len(line.encode("utf-8")) > _MAX_JSONL_BYTES:
            raise CodexAppServerError("Codex request exceeded the JSONL size limit.")
        try:
            with self._write_lock:
                if self._process is not process or process.stdin is None:
                    raise CodexAppServerError("Codex App Server is not writable.")
                process.stdin.write(line)
                process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise CodexAppServerError("Codex App Server connection was lost.") from exc

    def _read_stdout(self, process: Any) -> None:
        stream = process.stdout
        if stream is None:
            self._fail_process(process, CodexAppServerError("Codex stdout is unavailable."))
            return
        try:
            while True:
                line = stream.readline()
                if line == "":
                    break
                if len(line.encode("utf-8")) > _MAX_JSONL_BYTES:
                    self._fail_process(
                        process,
                        CodexAppServerError("Codex response exceeded the JSONL size limit."),
                    )
                    return
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    self._fail_process(process, CodexAppServerError("Codex returned malformed JSONL."))
                    return
                if not isinstance(message, dict):
                    self._fail_process(
                        process,
                        CodexAppServerError("Codex returned an invalid JSONL message."),
                    )
                    return
                self._dispatch_message(process, message)
        except (OSError, ValueError):
            pass
        finally:
            self._fail_process(process, CodexAppServerError("Codex App Server exited."), terminate=False)

    def _read_stderr(self, process: Any) -> None:
        stream = process.stderr
        if stream is None:
            return
        try:
            while True:
                chunk = stream.readline()
                if chunk == "":
                    return
                safe = _redact_text(chunk)
                with self._state_lock:
                    if self._process is process:
                        self._stderr_tail = (self._stderr_tail + safe)[-2_000:]
        except (OSError, ValueError):
            return

    def _dispatch_message(self, process: Any, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        method = message.get("method")
        if isinstance(request_id, (int, str)) and isinstance(method, str):
            self._deny_server_request(process, request_id, method)
            return
        if isinstance(request_id, int) and method is None:
            with self._state_lock:
                waiter = self._pending.pop(request_id, None)
            if waiter is None:
                return
            error = _mapping(message.get("error"))
            if error is not None:
                detail = error.get("message")
                safe_detail = _redact_text(detail)[:240] if isinstance(detail, str) else "request failed"
                waiter.put(CodexAppServerError(f"Codex App Server {safe_detail}."))
                return
            result = message.get("result", {})
            waiter.put(result if isinstance(result, dict) else CodexAppServerError("Invalid Codex response."))
            return
        if request_id is None and isinstance(method, str):
            self._handle_notification(method, _mapping(message.get("params")) or {})

    def _deny_server_request(self, process: Any, request_id: int | str, method: str) -> None:
        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "execCommandApproval",
            "applyPatchApproval",
        }:
            payload: dict[str, Any] = {"id": request_id, "result": {"decision": "decline"}}
        else:
            payload = {
                "id": request_id,
                "error": {"code": -32601, "message": "EagleEye does not grant this App Server request."},
            }
        try:
            self._write_json(process, payload)
        except CodexAppServerError:
            return

    def _handle_notification(self, method: str, params: Mapping[str, Any]) -> None:
        thread_id = _optional_string(params.get("threadId"))
        turn_id = _optional_string(params.get("turnId"))
        item_id = _optional_string(params.get("itemId"))
        status: str | None = None
        if method == "item/agentMessage/delta" and turn_id and item_id:
            delta = params.get("delta")
            if isinstance(delta, str):
                with self._state_lock:
                    key = (turn_id, item_id)
                    self._agent_text[key] = self._agent_text.get(key, "") + delta
        elif method == "item/completed" and turn_id:
            item = _mapping(params.get("item"))
            if item is not None and item.get("type") == "agentMessage":
                item_id = _optional_string(item.get("id")) or item_id
                text = item.get("text")
                if isinstance(text, str) and text:
                    with self._state_lock:
                        self._completed_messages.setdefault(turn_id, []).append(text)
        elif method == "turn/completed":
            turn = _mapping(params.get("turn"))
            if turn is not None:
                turn_id = _optional_string(turn.get("id")) or turn_id
                status = _optional_string(turn.get("status"))
            if turn_id:
                with self._state_lock:
                    self._turn_status[turn_id] = status or "unknown"
                    self._turn_events.setdefault(turn_id, threading.Event()).set()
        with self._state_lock:
            self._notifications.append(
                CodexNotification(
                    method=_safe_metadata(method),
                    thread_id=_safe_metadata(thread_id),
                    turn_id=_safe_metadata(turn_id),
                    item_id=_safe_metadata(item_id),
                    status=_safe_metadata(status),
                )
            )

    def _turn_event(self, turn_id: str) -> threading.Event:
        with self._state_lock:
            return self._turn_events.setdefault(turn_id, threading.Event())

    def _recover_after_failure(self) -> None:
        try:
            self.restart()
        except CodexAppServerError:
            self.close()

    def _discard_process(self, process: Any) -> None:
        with self._state_lock:
            if self._process is process:
                self._process = None
        _terminate_process(process)
        self._fail_pending(CodexAppServerError("Codex App Server was stopped."))

    def _fail_process(self, process: Any, error: CodexAppServerError, *, terminate: bool = True) -> None:
        with self._state_lock:
            if self._process is not process:
                return
            self._process = None
        if terminate:
            _terminate_process(process)
        self._fail_pending(error)

    def _fail_pending(self, error: CodexAppServerError) -> None:
        with self._state_lock:
            pending = tuple(self._pending.values())
            self._pending.clear()
        for waiter in pending:
            try:
                waiter.put_nowait(error)
            except queue.Full:
                pass


def _resolve_codex_executable(configured: str | None) -> str:
    command = configured or os.getenv("EAGLEEYE_CODEX_COMMAND", "codex")
    executable = shutil.which(command)
    if executable is None:
        raise CodexAppServerError("Codex CLI is not installed.")
    return executable


def _minimal_environment() -> dict[str, str]:
    allowed = (
        "CODEX_HOME",
        "HOME",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    )
    return {name: os.environ[name] for name in allowed if name in os.environ}


def _terminate_process(process: Any) -> None:
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
    except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
        return


def _redact_text(value: str) -> str:
    return _SECRET_TEXT.sub(lambda match: f"{match.group(1)}[redacted]", value)


def _mapping(value: object) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _safe_metadata(value: str | None) -> str | None:
    return _redact_text(value)[:200] if value is not None else None
