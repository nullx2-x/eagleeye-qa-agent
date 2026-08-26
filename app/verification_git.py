from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

from .project_qa import discover_project
from .verification_models import GitVerificationContext

_REF = re.compile(r"^[A-Za-z0-9._/@:+-]{1,200}$")
_MAX_UNTRACKED_FILE_BYTES = 32 * 1024 * 1024
_MAX_UNTRACKED_TOTAL_BYTES = 128 * 1024 * 1024


def collect_git_context(
    project_root: str,
    *,
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    allow_dirty: bool = False,
) -> GitVerificationContext:
    discovery = discover_project(project_root)
    root = Path(discovery.projectRoot)
    _ensure_git_repository(root)
    head_ref = _validated_ref(head_ref)
    resolved_head = _rev_parse(root, head_ref)
    current_head = _rev_parse(root, "HEAD")
    if resolved_head != current_head:
        raise ValueError("headRef must resolve to the currently checked out HEAD")

    resolved_base = _resolve_base(root, base_ref, resolved_head)
    merge_base = _merge_base(root, resolved_base, resolved_head)
    changed_files = _changed_files(root, resolved_base, resolved_head)
    status = _git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    dirty = bool(status)
    untracked = _untracked_paths(status)
    if dirty and not allow_dirty:
        raise ValueError("Working tree is dirty; commit changes or set allowDirty=true")

    working_tree_sha = None
    if dirty:
        working_tree_sha = _working_tree_fingerprint(root, status, untracked)
        changed_files = sorted(set(changed_files) | set(_status_paths(status)))

    diff = _git(
        root,
        ["diff", "--binary", "--no-ext-diff", f"{resolved_base}...{resolved_head}", "--"],
    )
    digest = hashlib.sha256()
    digest.update(resolved_base.encode())
    digest.update(b"\0")
    digest.update(resolved_head.encode())
    digest.update(b"\0")
    digest.update(diff)

    return GitVerificationContext(
        repositoryRoot=str(root),
        repositoryId=discovery.projectId,
        rootFingerprint=discovery.rootFingerprint,
        branch=_branch(root),
        baseCommit=resolved_base,
        headCommit=resolved_head,
        mergeBase=merge_base,
        changedFiles=changed_files,
        diffSha256=digest.hexdigest(),
        workingTreeSha256=working_tree_sha,
        dirty=dirty,
        untrackedPresent=bool(untracked),
    )


def _ensure_git_repository(root: Path) -> None:
    result = _git_result(root, ["rev-parse", "--is-inside-work-tree"])
    if result.returncode != 0 or result.stdout.strip() != b"true":
        raise ValueError("Project root is not a Git working tree")


def _resolve_base(root: Path, base_ref: str | None, head: str) -> str:
    if base_ref:
        return _rev_parse(root, _validated_ref(base_ref))
    parent = _git_result(root, ["rev-parse", "--verify", "HEAD^1^{commit}"])
    if parent.returncode == 0:
        return parent.stdout.decode().strip()
    return head


def _rev_parse(root: Path, ref: str) -> str:
    ref = _validated_ref(ref)
    result = _git_result(root, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if result.returncode != 0:
        raise ValueError("Git ref could not be resolved")
    value = result.stdout.decode().strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        raise ValueError("Resolved Git object is not a commit")
    return value


def _merge_base(root: Path, base: str, head: str) -> str:
    if base == head:
        return head
    result = _git_result(root, ["merge-base", base, head])
    if result.returncode != 0:
        raise ValueError("Git merge-base could not be determined")
    value = result.stdout.decode().strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        raise ValueError("Invalid Git merge-base")
    return value


def _changed_files(root: Path, base: str, head: str) -> list[str]:
    if base == head:
        return []
    output = _git(root, ["diff", "--name-only", "-z", f"{base}...{head}", "--"])
    return sorted({_safe_relative_name(part) for part in output.split(b"\0") if part})


def _branch(root: Path) -> str | None:
    result = _git_result(root, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if result.returncode != 0:
        return None
    value = result.stdout.decode("utf-8", "replace").strip()
    return value[:200] or None


def _status_paths(status: bytes) -> list[str]:
    paths: list[str] = []
    for entry in status.split(b"\0"):
        if not entry:
            continue
        raw = entry[3:] if len(entry) >= 3 and entry[2:3] == b" " else entry
        if raw:
            paths.append(_safe_relative_name(raw))
    return paths


def _untracked_paths(status: bytes) -> list[str]:
    values: list[str] = []
    for entry in status.split(b"\0"):
        if entry.startswith(b"?? "):
            values.append(_safe_relative_name(entry[3:]))
    return values


def _working_tree_fingerprint(root: Path, status: bytes, untracked: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(status)
    digest.update(_git(root, ["diff", "--binary", "--no-ext-diff", "HEAD", "--"]))
    digest.update(_git(root, ["diff", "--binary", "--no-ext-diff", "--cached", "HEAD", "--"]))
    total = 0
    resolved_root = root.resolve()
    for relative in sorted(untracked):
        candidate = root / relative
        if candidate.is_symlink():
            digest.update(relative.encode("utf-8", "replace"))
            digest.update(b"\0SYMLINK\0")
            digest.update(os.readlink(candidate).encode("utf-8", "replace"))
            continue
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
            raise ValueError("Untracked path escapes the authorized project root")
        size = resolved.stat().st_size
        if size > _MAX_UNTRACKED_FILE_BYTES or total + size > _MAX_UNTRACKED_TOTAL_BYTES:
            raise ValueError("Untracked files are too large to fingerprint safely")
        total += size
        digest.update(relative.encode("utf-8", "replace"))
        digest.update(b"\0")
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_name(value: bytes) -> str:
    text = value.decode("utf-8", "replace").replace("\\", "/")
    if text.startswith("/") or "/../" in f"/{text}/" or text == "..":
        raise ValueError("Git returned an unsafe repository path")
    return text[:2_000]


def _validated_ref(value: str) -> str:
    value = value.strip()
    if value.startswith("-") or not _REF.fullmatch(value):
        raise ValueError("Invalid Git ref")
    return value


def _git(root: Path, args: list[str]) -> bytes:
    result = _git_result(root, args)
    if result.returncode != 0:
        raise ValueError(f"Git command failed: {args[0]}")
    return result.stdout


def _git_result(root: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git is required for verification")
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        in {
            "HOME",
            "HOMEDRIVE",
            "HOMEPATH",
            "PATH",
            "PATHEXT",
            "SYSTEMROOT",
            "TEMP",
            "TMP",
            "TMPDIR",
            "USERPROFILE",
            "WINDIR",
        }
    }
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(  # noqa: S603 - resolved git executable, fixed argv, shell disabled
        [executable, *args],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
        shell=False,
    )
