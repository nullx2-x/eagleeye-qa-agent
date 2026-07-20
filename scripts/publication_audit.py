"""Fail-closed checks for EagleEye's public release tree.

This audit deliberately prints only file names, line numbers, and rule IDs. It
never echoes a suspected credential value into CI logs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int = 0

    def render(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{self.rule} {location}"


REQUIRED_FILES = {
    ".env.example",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    "COMPLIANCE.md",
    "LICENSE",
    "PRIVACY.md",
    "README.ja.md",
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/release/1.0.0-publication-audit.md",
}

PUBLIC_STATUS_FILES = {
    "README.md",
    "README.ja.md",
    "docs/build-week/README.md",
    "docs/build-week/demo-script.md",
    "docs/build-week/devpost-draft.md",
}

TEXT_SUFFIXES = {".json", ".md", ".ps1", ".py", ".txt", ".yaml", ".yml"}
FORBIDDEN_SUFFIXES = {".jks", ".key", ".p12", ".pfx", ".pem", ".sqlite", ".sqlite3"}
FORBIDDEN_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
    "service-account.json",
}


def tracked_files(root: Path) -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required for the publication audit")
    result = subprocess.run(  # noqa: S603 - fixed executable and arguments
        [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        timeout=15,
    )
    candidates = {part.decode("utf-8") for part in result.stdout.split(b"\0") if part}
    return sorted(relative for relative in candidates if (root / relative).exists())


def read_text(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def check_required_files(tracked: set[str]) -> list[Finding]:
    return [Finding("REQUIRED_FILE_MISSING", path) for path in sorted(REQUIRED_FILES - tracked)]


def check_forbidden_artifacts(tracked: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for relative in sorted(tracked):
        path = Path(relative)
        lowered = path.name.lower()
        if relative.startswith("reports/"):
            findings.append(Finding("INTERNAL_REPORT_TRACKED", relative))
        if lowered in FORBIDDEN_NAMES or (path.suffix.lower() in FORBIDDEN_SUFFIXES):
            findings.append(Finding("SENSITIVE_ARTIFACT_TRACKED", relative))
    return findings


def check_action_pins(root: Path, tracked: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for relative in sorted(path for path in tracked if path.startswith(".github/workflows/")):
        for line_number, line in enumerate(read_text(root, relative).splitlines(), 1):
            match = re.search(r"\buses:\s*([^\s#]+)", line)
            if not match or match.group(1).startswith("./"):
                continue
            reference = match.group(1).rsplit("@", 1)
            if len(reference) != 2 or re.fullmatch(r"[0-9a-f]{40}", reference[1]) is None:
                findings.append(Finding("ACTION_NOT_PINNED_TO_SHA", relative, line_number))
    return findings


def check_codeql_boundary(root: Path) -> list[Finding]:
    relative = ".github/workflows/codeql.yml"
    content = read_text(root, relative)
    required_fragments = {
        "CODEQL_ACTIONS_READ_MISSING": "actions: read",
        "CODEQL_CONTENTS_READ_MISSING": "contents: read",
        "CODEQL_SECURITY_WRITE_MISSING": "security-events: write",
        "CODEQL_PRIVATE_UPLOAD_POLICY_MISSING": "github.event.repository.private && 'never' || 'always'",
        "CODEQL_PRIVATE_SARIF_MISSING": "Preserve SARIF while the repository is private",
        "CODEQL_ARTIFACT_FAILURE_POLICY_MISSING": "if-no-files-found: error",
    }
    return [
        Finding(rule, relative) for rule, fragment in required_fragments.items() if fragment not in content
    ]


def check_environment_template(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    sensitive_name = re.compile(r"(?:API_KEY|PASSWORD|PRIVATE_KEY|SECRET|TOKEN)", re.IGNORECASE)
    for line_number, raw_line in enumerate(read_text(root, ".env.example").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if sensitive_name.search(name) and value.strip():
            findings.append(Finding("ENV_EXAMPLE_SECRET_VALUE", ".env.example", line_number))
    return findings


def check_public_text(root: Path, tracked: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    absolute_path = re.compile(r"(?:[A-Za-z]:\\(?:Users|WorkSpace)\\|/(?:Users|home)/[^/\s]+/)")
    stale_status = re.compile(r"(?:private judge-review|release-gated|remote run evidence TBD)", re.I)
    for relative in sorted(tracked):
        path = Path(relative)
        if path.suffix.lower() not in TEXT_SUFFIXES or relative == "docs/build-week/publication-security.md":
            continue
        for line_number, line in enumerate(read_text(root, relative).splitlines(), 1):
            if absolute_path.search(line):
                findings.append(Finding("LOCAL_ABSOLUTE_PATH", relative, line_number))
            if relative in PUBLIC_STATUS_FILES and ("TBD" in line or stale_status.search(line)):
                findings.append(Finding("STALE_PUBLIC_STATUS", relative, line_number))
    return findings


def check_markdown_links(root: Path, tracked: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    markdown_link = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    for relative in sorted(path for path in tracked if path.endswith(".md")):
        for line_number, line in enumerate(read_text(root, relative).splitlines(), 1):
            for raw_target in markdown_link.findall(line):
                target = raw_target.strip().strip("<>").split(" ", 1)[0]
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                local_target = unquote(target.split("#", 1)[0])
                resolved = (root / Path(relative).parent / local_target).resolve()
                try:
                    resolved.relative_to(root.resolve())
                except ValueError:
                    findings.append(Finding("MARKDOWN_LINK_ESCAPES_ROOT", relative, line_number))
                    continue
                if not resolved.exists():
                    findings.append(Finding("MARKDOWN_LINK_BROKEN", relative, line_number))
    return findings


def check_extension_manifest(root: Path) -> list[Finding]:
    relative = "chrome-extension/manifest.json"
    manifest = json.loads(read_text(root, relative))
    findings: list[Finding] = []
    if set(manifest.get("permissions", [])) != {"activeTab", "scripting", "storage"}:
        findings.append(Finding("EXTENSION_PERMISSION_DRIFT", relative))
    expected_hosts = {"http://127.0.0.1:8766/*", "http://localhost:8766/*"}
    if set(manifest.get("host_permissions", [])) != expected_hosts:
        findings.append(Finding("EXTENSION_HOST_PERMISSION_DRIFT", relative))
    if manifest.get("incognito") != "not_allowed":
        findings.append(Finding("EXTENSION_INCOGNITO_DRIFT", relative))
    return findings


def audit_repository(root: Path) -> list[Finding]:
    tracked = set(tracked_files(root))
    findings: list[Finding] = []
    findings.extend(check_required_files(tracked))
    findings.extend(check_forbidden_artifacts(tracked))
    findings.extend(check_action_pins(root, tracked))
    findings.extend(check_codeql_boundary(root))
    findings.extend(check_environment_template(root))
    findings.extend(check_public_text(root, tracked))
    findings.extend(check_markdown_links(root, tracked))
    findings.extend(check_extension_manifest(root))
    return sorted(findings, key=lambda finding: (finding.rule, finding.path, finding.line))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = audit_repository(root)
    if findings:
        print(f"Publication audit: FAIL ({len(findings)} finding(s))")
        for finding in findings:
            print(f"- {finding.render()}")
        return 1
    print("Publication audit: PASS (0 findings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
