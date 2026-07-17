from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

import yaml

from .repair_models import (
    FreshEvalAttestation,
    RepairCapabilities,
    RepairCapability,
    RepairPlan,
    RepairProject,
    RepairProjects,
    RepairRequest,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPABILITIES_PATH = ROOT / "profiles" / "repair-capabilities.yaml"
DEFAULT_PROJECTS_PATH = ROOT / "profiles" / "repair-projects.yaml"
REPARSE_POINT_ATTRIBUTE = 0x400
LOCKFILE_NAMES = {
    "cargo.lock",
    "composer.lock",
    "package-lock.json",
    "packages.lock.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "yarn.lock",
}
BINARY_SUFFIXES = {
    ".7z",
    ".a",
    ".bin",
    ".bmp",
    ".class",
    ".dll",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lib",
    ".mp3",
    ".mp4",
    ".o",
    ".obj",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".tar",
    ".webm",
    ".webp",
    ".xlsx",
    ".zip",
}
SENSITIVE_PARTS = {
    ".aws",
    ".azure",
    ".gnupg",
    ".ssh",
    "config",
    "credential",
    "credentials",
    "key",
    "keys",
    "private",
    "secrets",
}
SENSITIVE_FILE_RE = re.compile(
    r"(?:^|[._-])(?:credential|password|private[-_]?key|secret|token)(?:[._-]|$)", re.I
)
PROTECTED_REPAIR_PATHS = {
    ".gitattributes",
    ".gitignore",
    ".gitmodules",
    "app/ai_advisor.py",
    "app/ai_safety_eval.py",
    "app/codex_agent.py",
    "app/codex_app_server.py",
    "app/configuration.py",
    "app/desktop_adapter.py",
    "app/desktop_models.py",
    "app/guided_api.py",
    "app/guided_models.py",
    "app/guided_service.py",
    "app/guided_storage.py",
    "app/main.py",
    "app/mcp_server.py",
    "app/model_recommendations.py",
    "app/providers.py",
    "app/repair_models.py",
    "app/repair_orchestrator.py",
    "app/repair_policy.py",
    "app/repair_service.py",
    "app/runner.py",
    "app/security.py",
    "app/storage.py",
}
PROTECTED_REPAIR_PREFIXES = (
    ".github/",
    ".gitlab/",
    "profiles/",
    "scripts/",
    "tests/",
)
PROTECTED_BUILD_FILE_NAMES = {
    ".gitlab-ci.yml",
    ".ruff.toml",
    "cargo.toml",
    "composer.json",
    "deno.json",
    "deno.jsonc",
    "makefile",
    "mypy.ini",
    "package.json",
    "poetry.toml",
    "pyproject.toml",
    "pytest.ini",
    "requirements-dev.txt",
    "requirements.txt",
    "ruff.toml",
    "setup.cfg",
    "setup.py",
    "tox.ini",
}
PROTECTED_BUILD_DIRECTORY_PARTS = {".github", ".gitlab"}
SECRET_TEXT_RE = re.compile(
    r"(?:"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"
    r"|\bsk-[A-Za-z0-9_-]{16,}"
    r"|\b(?:api[_-]?key|client[_-]?secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{8,}"
    r")",
    re.I,
)


class RepairPolicyError(RuntimeError):
    """A fail-closed policy decision that must not invoke or apply a repair."""


@dataclass(frozen=True)
class RepairAuthorization:
    root: Path
    project: RepairProject
    capability: RepairCapability
    effective_mode: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PreparedFile:
    relative_path: str
    path: Path
    preimage: bytes
    postimage: bytes
    preimage_sha256: str
    postimage_sha256: str
    changed_lines: int


@dataclass(frozen=True)
class PreparedPlan:
    files: tuple[PreparedFile, ...]
    changed_lines: int
    total_bytes: int


AttestationVerifier = Callable[[FreshEvalAttestation, RepairRequest], bool]


def load_repair_capabilities(path: Path = DEFAULT_CAPABILITIES_PATH) -> RepairCapabilities:
    return RepairCapabilities.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_repair_projects(path: Path = DEFAULT_PROJECTS_PATH) -> RepairProjects:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    for project in payload.get("projects", []):
        candidate = Path(project["root"]).expanduser()
        if not candidate.is_absolute():
            project["root"] = (path.resolve().parent / candidate).resolve()
    return RepairProjects.model_validate(payload)


class RepairPolicy:
    def __init__(
        self,
        capabilities: RepairCapabilities,
        projects: RepairProjects,
        *,
        attestation_verifier: AttestationVerifier | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.projects = projects
        self.attestation_verifier = attestation_verifier
        self.clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_files(
        cls,
        capabilities_path: Path = DEFAULT_CAPABILITIES_PATH,
        projects_path: Path = DEFAULT_PROJECTS_PATH,
        *,
        attestation_verifier: AttestationVerifier | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> RepairPolicy:
        return cls(
            load_repair_capabilities(capabilities_path),
            load_repair_projects(projects_path),
            attestation_verifier=attestation_verifier,
            clock=clock,
        )

    def authorize(self, request: RepairRequest) -> RepairAuthorization:
        if os.getenv(self.capabilities.featureFlag) != "1":
            raise RepairPolicyError("Self-repair feature flag is disabled")
        if request.production or request.environment != "local":
            raise RepairPolicyError("Self-repair is restricted to non-production local environments")

        capability = next(
            (
                item
                for item in self.capabilities.capabilities
                if item.provider == request.provider and request.model in item.models
            ),
            None,
        )
        if capability is None or not capability.proposalAllowed:
            raise RepairPolicyError("Provider and model are not on the exact repair allowlist")

        project = next((item for item in self.projects.projects if item.id == request.projectId), None)
        if project is None or not project.enabled:
            raise RepairPolicyError("Project is not on the enabled repair root allowlist")
        if request.environment not in project.allowedEnvironments:
            raise RepairPolicyError("Project policy does not allow repair in this environment")

        root = self._validate_root(project.root)
        self._require_clean_git(root)
        reasons: list[str] = []
        effective_mode = "proposal_only"
        if request.requestedMode == "apply":
            apply_reasons = self._apply_reasons(request, capability)
            if apply_reasons:
                reasons.extend(apply_reasons)
            else:
                effective_mode = "apply"
        else:
            reasons.append("Request selected proposal-only mode")
        return RepairAuthorization(root, project, capability, effective_mode, tuple(reasons))

    def prepare_plan(self, root: Path, plan: RepairPlan) -> PreparedPlan:
        limits = self.capabilities.limits
        if len(plan.files) > limits.maxFiles:
            raise RepairPolicyError(f"Repair plan exceeds the {limits.maxFiles}-file limit")

        prepared: list[PreparedFile] = []
        for edit in plan.files:
            path, relative = self._resolve_file(root, edit.path)
            self._reject_sensitive_path(relative, path)
            preimage = path.read_bytes()
            if len(preimage) > limits.maxTotalBytes or b"\x00" in preimage:
                raise RepairPolicyError("Binary or oversized files cannot be repaired")
            try:
                original = preimage.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RepairPolicyError("Only UTF-8 text files can be repaired") from exc
            if SECRET_TEXT_RE.search(original):
                raise RepairPolicyError("Files containing apparent secrets cannot be repaired")
            preimage_sha = _sha256(preimage)
            if preimage_sha != edit.expectedSha256:
                raise RepairPolicyError(f"Expected SHA-256 does not match {relative}")

            spans: list[tuple[int, int, str]] = []
            for replacement in edit.replacements:
                if SECRET_TEXT_RE.search(replacement.old) or SECRET_TEXT_RE.search(replacement.new):
                    raise RepairPolicyError("Repair replacements may not contain apparent secrets")
                if original.count(replacement.old) != 1:
                    raise RepairPolicyError(f"Exact replacement must match once in {relative}")
                start = original.index(replacement.old)
                spans.append((start, start + len(replacement.old), replacement.new))
            spans.sort()
            if any(left[1] > right[0] for left, right in zip(spans, spans[1:], strict=False)):
                raise RepairPolicyError(f"Exact replacements overlap in {relative}")
            updated = original
            for start, end, new in reversed(spans):
                updated = updated[:start] + new + updated[end:]
            if not updated:
                raise RepairPolicyError("A repair may not empty a file")
            postimage = updated.encode("utf-8")
            changed_lines = _changed_lines(original, updated)
            prepared.append(
                PreparedFile(
                    relative_path=relative,
                    path=path,
                    preimage=preimage,
                    postimage=postimage,
                    preimage_sha256=preimage_sha,
                    postimage_sha256=_sha256(postimage),
                    changed_lines=changed_lines,
                )
            )

        total_lines = sum(item.changed_lines for item in prepared)
        total_bytes = sum(max(len(item.preimage), len(item.postimage)) for item in prepared)
        if total_lines > limits.maxChangedLines:
            raise RepairPolicyError(f"Repair plan exceeds the {limits.maxChangedLines}-changed-line limit")
        if total_bytes > limits.maxTotalBytes:
            raise RepairPolicyError(f"Repair plan exceeds the {limits.maxTotalBytes}-byte limit")
        return PreparedPlan(tuple(prepared), total_lines, total_bytes)

    def git_changed_paths(self, root: Path) -> set[str]:
        tracked = _git_bytes(root, ["diff", "--name-only", "-z", "HEAD", "--"])
        untracked = _git_bytes(root, ["ls-files", "--others", "--exclude-standard", "-z"])
        values = tracked.split(b"\x00") + untracked.split(b"\x00")
        return {
            value.decode("utf-8", errors="surrogateescape").replace("\\", "/") for value in values if value
        }

    def _apply_reasons(self, request: RepairRequest, capability: RepairCapability) -> list[str]:
        reasons: list[str] = []
        if not capability.automaticApplyAllowed:
            reasons.append("Allowlisted capability is proposal-only")
        if not request.explicitApplyRequested:
            reasons.append("Automatic apply was not explicitly requested")
        attestation = request.attestation
        if capability.requiresFreshEvalAttestation:
            if attestation is None:
                reasons.append("Fresh evaluation attestation is missing")
            else:
                reasons.extend(self._attestation_reasons(request, capability, attestation))
        if self.attestation_verifier is None:
            reasons.append("No trusted evaluation attestation verifier is configured")
        elif attestation is not None and not self.attestation_verifier(attestation, request):
            reasons.append("Evaluation attestation authenticity verification failed")
        return reasons

    def _attestation_reasons(
        self,
        request: RepairRequest,
        capability: RepairCapability,
        attestation: FreshEvalAttestation,
    ) -> list[str]:
        reasons: list[str] = []
        now = self.clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        if attestation.projectId != request.projectId:
            reasons.append("Evaluation attestation project does not match")
        if attestation.failureFingerprint != request.failureFingerprint:
            reasons.append("Evaluation attestation failure fingerprint does not match")
        if attestation.issuedAt > now + timedelta(seconds=30):
            reasons.append("Evaluation attestation issuance is in the future")
        if now - attestation.issuedAt > timedelta(seconds=capability.maxAttestationAgeSeconds):
            reasons.append("Evaluation attestation is stale")
        if attestation.expiresAt <= now:
            reasons.append("Evaluation attestation has expired")
        return reasons

    @staticmethod
    def _validate_root(candidate: Path) -> Path:
        if not candidate.is_absolute() or not candidate.is_dir():
            raise RepairPolicyError("Allowlisted project root must be an existing absolute directory")
        if _is_link_or_reparse(candidate):
            raise RepairPolicyError("Symlink or reparse-point project roots are forbidden")
        resolved = candidate.resolve(strict=True)
        absolute = Path(os.path.abspath(candidate))
        if os.path.normcase(str(absolute)) != os.path.normcase(str(resolved)):
            raise RepairPolicyError("Project root ancestry may not traverse a reparse point")
        git_root = _git_text(resolved, ["rev-parse", "--show-toplevel"]).strip()
        if not git_root or Path(git_root).resolve(strict=True) != resolved:
            raise RepairPolicyError("Allowlisted root must be the exact Git worktree root")
        return resolved

    @staticmethod
    def _require_clean_git(root: Path) -> None:
        status = _git_bytes(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
        if status:
            raise RepairPolicyError("Dirty Git worktrees are not eligible for self-repair")

    @staticmethod
    def _resolve_file(root: Path, supplied: str) -> tuple[Path, str]:
        normalized = supplied.replace("\\", "/")
        relative = PurePosixPath(normalized)
        if relative.is_absolute() or not relative.parts or ".." in relative.parts or ":" in normalized:
            raise RepairPolicyError("Repair path must be a relative in-root path")
        path = root.joinpath(*relative.parts)
        current = root
        for part in relative.parts:
            current /= part
            if current.exists() and _is_link_or_reparse(current):
                raise RepairPolicyError("Symlink and reparse-point paths are forbidden")
        if not path.is_file():
            raise RepairPolicyError("Repairs may only replace existing regular files")
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise RepairPolicyError("Repair path escapes the allowlisted root") from exc
        if resolved.stat().st_nlink > 1:
            raise RepairPolicyError("Hard-linked files are forbidden")
        return resolved, relative.as_posix()

    @staticmethod
    def _reject_sensitive_path(relative: str, path: Path) -> None:
        lowered_parts = {part.casefold() for part in PurePosixPath(relative).parts}
        name = path.name.casefold()
        if (
            relative.casefold() in PROTECTED_REPAIR_PATHS
            or relative.casefold().startswith(PROTECTED_REPAIR_PREFIXES)
            or name in PROTECTED_BUILD_FILE_NAMES
            or lowered_parts.intersection(PROTECTED_BUILD_DIRECTORY_PARTS)
        ):
            raise RepairPolicyError("Repair safety policy and VCS control files are protected")
        if name in LOCKFILE_NAMES or path.suffix.casefold() == ".lock":
            raise RepairPolicyError("Dependency and application lockfiles are forbidden")
        if path.suffix.casefold() in BINARY_SUFFIXES:
            raise RepairPolicyError("Binary files are forbidden")
        sensitive = (
            lowered_parts.intersection(SENSITIVE_PARTS)
            or name.startswith(".env")
            or SENSITIVE_FILE_RE.search(name)
        )
        if sensitive:
            raise RepairPolicyError("Secret-bearing paths are forbidden")


def _changed_lines(before: str, after: str) -> int:
    changes = difflib.ndiff(before.splitlines(), after.splitlines())
    return sum(line.startswith(("- ", "+ ")) for line in changes)


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & REPARSE_POINT_ATTRIBUTE)


def _git_bytes(root: Path, arguments: list[str]) -> bytes:
    executable = shutil.which("git")
    if executable is None or not Path(executable).is_file():
        raise RepairPolicyError("Git executable is unavailable")
    command = [executable, "-c", "core.quotepath=false", "-C", str(root), *arguments]
    try:
        result = subprocess.run(  # noqa: S603 -- git argv is fixed by policy, never planner data
            command,
            capture_output=True,
            check=False,
            timeout=15,
            shell=False,
            env=_minimal_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepairPolicyError("Git policy inspection failed") from exc
    if result.returncode != 0:
        raise RepairPolicyError("Git policy inspection failed")
    return result.stdout


def _git_text(root: Path, arguments: list[str]) -> str:
    return _git_bytes(root, arguments).decode("utf-8", errors="replace")


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


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
