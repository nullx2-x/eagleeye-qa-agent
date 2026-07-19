from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_required(content: str, old: str, new: str, label: str) -> str:
    if old not in content:
        if new in content:
            return content
        raise RuntimeError(f"Expected source fragment not found: {label}")
    return content.replace(old, new)


def patch_browser_agent() -> None:
    path = "app/browser_agent.py"
    content = read(path)
    content = replace_required(
        content,
        r'_SECRET_QUERY_KEYS = re.compile(r"(?i)(token|secret|password|passwd|api[_-]?key|auth|code|session)")',
        r'_SECRET_QUERY_KEYS = re.compile(r"(?i)(token|secret|password|passwd|api[_-]?key|auth|code|session|nonce|wpnonce|rest[_-]?nonce)")',
        "browser secret query mask",
    )

    legacy_block = re.compile(
        r"def create_wordpress_demo\(\) -> BrowserAgentSession:\n.*?\n\n\ndef load_session",
        re.DOTALL,
    )
    replacement = """def create_local_sample() -> BrowserAgentSession:
    # Generic login-free sample without CMS-specific routes or labels.
    target = os.getenv("EAGLEEYE_SAMPLE_TARGET", "http://127.0.0.1:8766/demo-site/")
    if not is_run_url_allowed(target):
        raise ValueError("The sample target must be a loopback HTTP(S) URL.")
    sample_target = target.rstrip("/") + "/sample"
    session = create_session(
        BrowserSessionCreate(
            name="Authorized local sample journey",
            goal="普段の閲覧操作から回帰テストを生成し、公開ページの主要導線を検証する",
            startUrl=target,
            locale="ja",
        )
    )
    append_observation(
        session.id,
        BrowserObservation(
            id="sample-goto",
            timestamp=1,
            action="goto",
            url=target,
            redacted=False,
            dom=BrowserDomSnapshot(
                pageTitle="EagleEye Local QA Lab",
                headings=["EagleEye Local QA Lab"],
                landmarks=["main"],
                controls=[],
            ),
        ),
    )
    append_observation(
        session.id,
        BrowserObservation(
            id="sample-click",
            timestamp=2,
            action="click",
            url=target,
            target={"role": "link", "name": "Sample Page", "tagName": "a"},
            redacted=False,
        ),
    )
    append_observation(
        session.id,
        BrowserObservation(
            id="sample-snapshot",
            timestamp=3,
            action="snapshot",
            url=sample_target,
            redacted=False,
            dom=BrowserDomSnapshot(
                pageTitle="EagleEye Local QA Lab",
                headings=["Sample Page"],
                landmarks=["main"],
                controls=[],
            ),
        ),
    )
    return generate_session(session.id)


def load_session"""
    content, count = legacy_block.subn(replacement, content)
    if count not in {0, 1}:
        raise RuntimeError(f"Unexpected legacy demo block count: {count}")
    if count == 0 and "def create_local_sample()" not in content:
        raise RuntimeError("Neither legacy nor current local sample function was found")

    sanitize_block = re.compile(
        r"def _sanitize_url\(value: str\) -> str:\n.*?\n\n\ndef _with_query_value",
        re.DOTALL,
    )
    safe_sanitize = """def _sanitize_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) browser URLs are accepted.")

    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    query_items = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not _SECRET_QUERY_KEYS.search(key)
    ]
    return urlunsplit((parsed.scheme, netloc, parsed.path or "/", urlencode(query_items), ""))


def _with_query_value"""
    content, count = sanitize_block.subn(safe_sanitize, content)
    if count != 1 and "hostname = parsed.hostname" not in content:
        raise RuntimeError("Could not harden Python URL sanitizer")

    if "def _is_sensitive_admin_url(" not in content:
        marker = "\n\ndef _same_origin(left: str, right: str) -> bool:\n"
        helper = """

def _is_sensitive_admin_url(value: str) -> bool:
    path = urlsplit(value).path.casefold().rstrip("/")
    return path == "/wp-login.php" or path == "/wp-admin" or path.startswith("/wp-admin/")


def _session_has_sensitive_admin_path(session: BrowserAgentSession) -> bool:
    urls = [str(session.startUrl), *(str(item.url) for item in session.observations)]
    return any(_is_sensitive_admin_url(value) for value in urls)
"""
        content = replace_required(content, marker, helper + marker, "sensitive admin helper")

    run_marker = (
        "def run_session(session_id: str) -> BrowserAgentSession:\n    session = load_session(session_id)\n"
    )
    run_guard = (
        "def run_session(session_id: str) -> BrowserAgentSession:\n"
        "    session = load_session(session_id)\n"
        "    if _session_has_sensitive_admin_path(session):\n"
        "        raise PermissionError(\n"
        '            "Replay is disabled for WordPress administration and login paths. "\n'
        '            "Use a disposable local fixture or reviewed non-destructive environment."\n'
        "        )\n"
    )
    content = replace_required(content, run_marker, run_guard, "admin replay guard")

    ai_marker = (
        "def _ai_cases(\n"
        "    session: BrowserAgentSession,\n"
        ") -> tuple[list[GeneratedBrowserTestCase], BrowserAIResult, list[str], list[str]]:\n"
        '    provider = os.getenv("EAGLEEYE_AI_PROVIDER", "codex-agent").strip().casefold()\n'
    )
    ai_guard = (
        "def _ai_cases(\n"
        "    session: BrowserAgentSession,\n"
        ") -> tuple[list[GeneratedBrowserTestCase], BrowserAIResult, list[str], list[str]]:\n"
        '    provider = os.getenv("EAGLEEYE_AI_PROVIDER", "codex-agent").strip().casefold()\n'
        "    if _session_has_sensitive_admin_path(session):\n"
        "        model = (\n"
        '            os.getenv("EAGLEEYE_BROWSER_AI_MODEL", "").strip()\n'
        '            or os.getenv("EAGLEEYE_CODEX_MODEL", "").strip()\n'
        '            or "gpt-5.6-terra"\n'
        "        )\n"
        "        return (\n"
        "            [],\n"
        "            BrowserAIResult(\n"
        "                provider=provider,\n"
        "                model=model,\n"
        "                available=False,\n"
        "                fallbackUsed=True,\n"
        '                message="AI generation is disabled for sensitive administration paths.",\n'
        "            ),\n"
        "            [],\n"
        '            ["管理画面ではAI送信を行わず、非破壊の手動レビューを使用する"],\n'
        "        )\n"
    )
    content = replace_required(content, ai_marker, ai_guard, "admin AI guard")
    write(path, content)


def patch_main() -> None:
    path = "app/main.py"
    content = read(path)
    old = """@app.get("/demo-site/", response_class=HTMLResponse)
def bundled_demo_site(page_id: int | None = Query(default=None, ge=1, le=99)) -> HTMLResponse:
    policy = (
        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    )
    return HTMLResponse(
        demo_site_html(sample_page=page_id == 2),
        headers={"Content-Security-Policy": policy, "Cache-Control": "no-store"},
    )
"""
    new = """@app.get("/demo-site/", response_class=HTMLResponse)
def bundled_demo_site() -> HTMLResponse:
    policy = (
        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    )
    return HTMLResponse(
        demo_site_html(sample_page=False),
        headers={"Content-Security-Policy": policy, "Cache-Control": "no-store"},
    )
"""
    write(path, replace_required(content, old, new, "generic sample route"))


def patch_extension() -> None:
    old = "const SECRET_QUERY_KEY = /(token|secret|password|passwd|api[_-]?key|auth|code|session)/iu;"
    new = (
        "const SECRET_QUERY_KEY = "
        "/(token|secret|password|passwd|api[_-]?key|auth|code|session|nonce|wpnonce|rest[_-]?nonce)/iu;"
    )
    for path in ("chrome-extension/background.js", "chrome-extension/content.js"):
        write(path, replace_required(read(path), old, new, f"{path} nonce mask"))


def patch_mcp() -> None:
    path = "app/mcp_server.py"
    content = read(path)
    imports = (
        "from .project_qa import discover_project, load_project_run, run_project\n"
        "from .project_qa_models import ProjectRunRequest\n"
    )
    if imports not in content:
        content = replace_required(
            content,
            "from .providers import broker\n",
            "from .providers import broker\n" + imports,
            "Project QA MCP imports",
        )

    tools = """@mcp.tool()
def discover_project_qa(project_root: str, authorized: bool = False) -> dict:
    if not authorized:
        raise PermissionError("Project QA discovery requires authorized=true")
    return discover_project(project_root).model_dump(mode="json")


@mcp.tool()
def run_project_qa(
    project_root: str,
    authorized: bool = False,
    suite_ids: list[str] | None = None,
    mode: str = "development",
    timeout_seconds: int = 900,
    fail_fast: bool = False,
) -> dict:
    if not authorized:
        raise PermissionError("Project QA execution requires authorized=true")
    request = ProjectRunRequest.model_validate(
        {
            "projectRoot": project_root,
            "authorized": True,
            "suiteIds": suite_ids or [],
            "mode": mode,
            "timeoutSeconds": timeout_seconds,
            "failFast": fail_fast,
        }
    )
    return run_project(request).model_dump(mode="json")


@mcp.tool()
def project_qa_run_status(run_id: str) -> dict:
    return load_project_run(run_id).model_dump(mode="json")


"""
    marker = '@mcp.resource("qa://strategy/spec")\n'
    if "def discover_project_qa(" not in content:
        content = replace_required(content, marker, tools + marker, "Project QA MCP tools")
    write(path, content)


def patch_configuration_and_docs() -> None:
    env = read(".env.example").replace("EAGLEEYE_DEMO_TARGET=", "EAGLEEYE_SAMPLE_TARGET=")
    write(".env.example", env)

    ignore = read(".gitignore")
    for line in (
        "artifacts/project-qa/",
        "reports/",
        "videos/eagleeye-build-week/",
        "docs/build-week/",
    ):
        if line not in ignore.splitlines():
            ignore += ("" if ignore.endswith("\n") else "\n") + line + "\n"
    write(".gitignore", ignore)

    readme = (
        "\n".join(
            line
            for line in read("README.md").splitlines()
            if "wordpress" not in line.casefold()
            and "eagleeye-demo-flow.gif" not in line
            and "youtu.be/zLSLiG7QYr4" not in line
            and "videos/eagleeye-build-week" not in line
            and "docs/build-week/" not in line
        )
        + "\n"
    )
    readme = readme.replace("/demo/wordpress", "/sample/local")
    readme = readme.replace("EAGLEEYE_DEMO_TARGET", "EAGLEEYE_SAMPLE_TARGET")
    write("README.md", readme)

    notices = ROOT / "THIRD_PARTY_NOTICES.md"
    if notices.is_file():
        content = (
            "\n".join(
                line
                for line in notices.read_text(encoding="utf-8").splitlines()
                if "videos/eagleeye-build-week" not in line
                and "Kokoro-82M" not in line
                and "Faster-Whisper" not in line
            )
            + "\n"
        )
        notices.write_text(content, encoding="utf-8")


def remove_generated_history() -> None:
    for relative in ("reports", "videos/eagleeye-build-week", "docs/build-week"):
        path = ROOT / relative
        if path.is_dir():
            shutil.rmtree(path)
    path = ROOT / "scripts/start-build-week-demo.ps1"
    if path.is_file():
        path.unlink()


def main() -> None:
    patch_browser_agent()
    patch_main()
    patch_extension()
    patch_mcp()
    patch_configuration_and_docs()
    remove_generated_history()


if __name__ == "__main__":
    main()
