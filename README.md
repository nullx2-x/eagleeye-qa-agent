# EagleEye — Operational AI QA Agent

**Discover, execute, and govern real project QA with browser replay, bounded self-repair, and evidence-backed quality gates.**

**English** | [日本語](README.ja.md)

EagleEye is a local-first QA system for explicitly authorized projects. It detects test, lint, type-check, security, integration, E2E, and build suites; executes them without a shell inside approved project roots; normalizes the results; and creates JSON/Markdown reports with bounded logs and SHA-256 evidence receipts.

The browser agent remains an optional evidence source. It records a privacy-limited DOM summary and action trail without retaining typed values, asks GPT-5.6 through Codex App Server for complementary coverage, validates generated cases deterministically, and replays the recorded critical path with Playwright.

AI can propose tests and bounded repairs. It cannot act as the pass/fail oracle, approve a release, silently write to production, or bypass the configured safety gates.

> **Authorized testing only.** Use EagleEye only on systems you own or have explicit permission to test. Review [Privacy](PRIVACY.md), [Security](SECURITY.md), and [Compliance](COMPLIANCE.md) before collecting evidence from a real system.

## Operational Project QA

Supported detected ecosystems:

- Node.js
- Python
- Go
- Rust
- .NET
- Gradle
- Maven

Repository owners can also define approved command arrays in `.eagleeye/qa.json`.

Every Project QA run requires:

- `authorized=true`;
- a project root inside `EAGLEEYE_PROJECT_ROOTS`;
- an allowlisted executable;
- `shell=False` execution;
- bounded, redacted logs;
- a timeout and process-tree cleanup;
- SHA-256 evidence;
- deterministic quality-gate evaluation.

Project QA does not require CPU-specific checks, machine benchmarks, or web-diagnostic probes unless the repository owner explicitly adds them to `.eagleeye/qa.json`.

## Quick Start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), PowerShell, and Chromium.

```powershell
git clone https://github.com/nullx2-x/eagleeye-qa-agent.git
cd eagleeye-qa-agent
Copy-Item .env.example .env
uv sync --locked --dev
uv run playwright install chromium
.\scripts\start-eagleeye.ps1
```

Authorize the parent directory that contains projects EagleEye may inspect:

```powershell
$env:EAGLEEYE_PROJECT_ROOTS = "C:\WorkSpace\01_Apps"
```

Discover or execute a project QA plan:

```powershell
uv run python scripts/run_project_qa.py C:\WorkSpace\01_Apps\your-project --discover
.\scripts\run-project-qa.ps1 -ProjectRoot C:\WorkSpace\01_Apps\your-project -Mode development
```

## Browser Agent

1. Open `chrome://extensions` and enable Developer mode.
2. Select **Load unpacked** and choose `chrome-extension`.
3. Open an approved HTTP(S) page.
4. Select the EagleEye icon or press `Ctrl+Shift+Y`.
5. Confirm site authorization and privacy consent.
6. Follow **Start → normal use → Stop → Generate → Replay → Report**.
7. Delete the local session when its evidence is no longer required.

The extension requests only `activeTab`, `scripting`, session storage, and loopback API access. Screenshots are opt-in and are not included in the AI prompt.

### Sensitive administration paths

For `/wp-admin`, `/wp-login.php`, and their child paths:

- AI case generation is disabled;
- Replay is rejected;
- the deterministic local recording can still be reviewed manually;
- nonce-like query parameters are removed;
- URL usernames, passwords, fragments, and secret-like query parameters are removed before persistence.

Use a disposable local fixture or a reviewed non-destructive staging environment for administrative workflows.

## Privacy Contract

EagleEye does not collect or retain:

- form values;
- passwords or one-time codes;
- cookies;
- authentication headers;
- `FormData` payloads;
- payment data;
- URL user information or fragments;
- token-, auth-, session-, code-, nonce-, or API-key-like query parameters.

Visible page titles, headings, accessible names, and control labels can still contain sensitive information. Do not start recording on a sensitive page without additional organizational controls.

## Bounded Self-Repair

Self-repair is fail-closed. A repair can proceed only when all configured requirements pass, including:

- local, non-production scope;
- clean Git state;
- an allowed model and operation;
- fresh one-use human attestation;
- strict file and line limits;
- fixed verification commands;
- checkpoint and rollback availability.

A failed gate produces a report; it does not weaken the gate or silently apply a change.

## Service Endpoints

| Service | URL |
|---|---|
| Dashboard and API | `http://127.0.0.1:8766` |
| MCP | `http://127.0.0.1:8768/mcp` |
| Local sample | `http://127.0.0.1:8766/demo-site/` |

Project QA endpoints:

- `POST /api/v1/project-qa/discover`
- `POST /api/v1/project-qa/runs`
- `GET /api/v1/project-qa/runs/{runId}`

Browser Agent endpoints:

- `POST /api/v1/browser-agent/sessions`
- `POST /api/v1/browser-agent/sessions/{sessionId}/generate`
- `POST /api/v1/browser-agent/sessions/{sessionId}/run`
- `GET /api/v1/browser-agent/sessions/{sessionId}/report`
- `DELETE /api/v1/browser-agent/sessions/{sessionId}`

FastAPI `/docs` and `/openapi.json` are disabled by default. Enable them only for loopback development with `EAGLEEYE_ENABLE_API_DOCS=1`.

## Verification

```powershell
uv run ruff format --check app scripts tests
uv run ruff check app scripts tests
uv run pytest -q
```

The repository CI also verifies that generated reports, submission media, obsolete demo routes, and legacy CMS-specific evidence are not tracked in the current product tree.

## Human Responsibility

EagleEye assists with observation, test design, deterministic execution, evidence, and bounded repair proposals. A human remains responsible for authorization, sensitive-data handling, production changes, legal consent, release approval, and publication.

## License

[MIT](LICENSE)
