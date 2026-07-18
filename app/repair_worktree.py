from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import TracebackType
from uuid import uuid4


class DisposableWorktreeError(RuntimeError):
    """Fail-closed disposable Git worktree setup or cleanup failure."""


class DisposableWorktree:
    """A detached Git worktree used to contain all planner verification side effects."""

    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root
        self.base = Path(tempfile.gettempdir()) / "eagleeye-repair-worktrees"
        self.path = self.base / f"repair-{uuid4().hex}"

    def __enter__(self) -> Path:
        self.base.mkdir(parents=True, exist_ok=True)
        attributes = getattr(self.base.lstat(), "st_file_attributes", 0)
        if self.base.is_symlink() or attributes & 0x400:
            raise DisposableWorktreeError("Disposable worktree base may not be a symlink")
        hooks = self.base / ".disabled-hooks"
        hooks.mkdir(exist_ok=True)
        _git(
            self.source_root,
            ["worktree", "add", "--detach", str(self.path), "HEAD"],
            hooks_path=hooks,
        )
        return self.path.resolve(strict=True)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            _git(self.source_root, ["worktree", "remove", "--force", str(self.path)])
        except DisposableWorktreeError:
            if self.path.exists() and self.path.resolve().is_relative_to(self.base.resolve()):
                shutil.rmtree(self.path)
        finally:
            try:
                _git(self.source_root, ["worktree", "prune"])
            except DisposableWorktreeError:
                pass
        # Cleanup failure never widens the write boundary: verification ran only
        # in this detached directory and the original worktree is handled separately.


def _git(root: Path, arguments: list[str], *, hooks_path: Path | None = None) -> None:
    executable = shutil.which("git")
    if executable is None:
        raise DisposableWorktreeError("Git executable is unavailable")
    try:
        command = [executable, "-c", "core.quotepath=false"]
        if hooks_path is not None:
            command.extend(["-c", f"core.hooksPath={hooks_path}"])
        command.extend(["-C", str(root), *arguments])
        completed = subprocess.run(  # noqa: S603 -- argv is generated only by this module
            command,
            capture_output=True,
            check=False,
            timeout=30,
            shell=False,
            env=_minimal_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DisposableWorktreeError("Disposable Git worktree operation failed") from exc
    if completed.returncode != 0:
        raise DisposableWorktreeError("Disposable Git worktree operation failed")


def _minimal_environment() -> dict[str, str]:
    allowed = (
        "COMSPEC",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
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
