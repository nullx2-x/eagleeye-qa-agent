from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from types import TracebackType

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class ProjectRepairBusyError(RuntimeError):
    """Raised when another repair already owns the same project root."""


class ProjectRepairLock:
    """Process and OS-level non-blocking lock keyed by the canonical project root."""

    def __init__(self, project_root: Path, lock_root: Path) -> None:
        key = os.path.normcase(str(project_root.resolve(strict=True)))
        with _LOCKS_GUARD:
            self._thread_lock = _LOCKS.setdefault(key, threading.Lock())
        self._lock_root = lock_root
        self._lock_name = hashlib.sha256(key.encode()).hexdigest() + ".lock"
        self._handle = None

    def __enter__(self) -> ProjectRepairLock:
        if not self._thread_lock.acquire(blocking=False):
            raise ProjectRepairBusyError("Another repair is already active for this project")
        try:
            self._lock_root.mkdir(parents=True, exist_ok=True)
            attributes = getattr(self._lock_root.lstat(), "st_file_attributes", 0)
            if self._lock_root.is_symlink() or attributes & 0x400:
                raise OSError("Unsafe repair lock directory")
            self._handle = (self._lock_root / self._lock_name).open("a+b")
            self._handle.seek(0)
            if self._handle.read(1) == b"":
                self._handle.write(b"0")
                self._handle.flush()
            self._handle.seek(0)
            _lock_file(self._handle)
        except (OSError, ProjectRepairBusyError):
            if self._handle is not None:
                self._handle.close()
                self._handle = None
            self._thread_lock.release()
            raise ProjectRepairBusyError("Another repair is already active for this project") from None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self._handle is not None:
                _unlock_file(self._handle)
                self._handle.close()
                self._handle = None
        finally:
            self._thread_lock.release()


def _lock_file(handle) -> None:
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise ProjectRepairBusyError from exc
    else:
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ProjectRepairBusyError from exc


def _unlock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
