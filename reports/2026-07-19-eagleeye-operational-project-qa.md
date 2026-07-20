# EagleEye operational Project QA completion report

Date: 2026-07-19
Status: PASS

## Outcome

EagleEye 1.1 now discovers and executes repository QA as an operational system instead of relying on a bundled browser demonstration. It supports detected Node.js, Python, Go, Rust, .NET, Gradle, and Maven suites, plus explicitly approved `.eagleeye/qa.json` suites.

The former CMS-specific demonstration labels, routes, evidence, and media were removed from the current product tree. The browser workflow remains available as an optional local sample and evidence source.

## Safety boundaries

- Explicit `authorized=true` is required for REST and MCP execution.
- Project roots are confined by `EAGLEEYE_PROJECT_ROOTS`.
- Commands use a fixed executable allowlist and `shell=False`.
- Each suite has a timeout and process-tree termination.
- Logs are redacted, bounded to 2 MiB, hashed with SHA-256, and written beside JSON/Markdown reports.
- Missing executables become evidence-backed `INFRA_ERROR` results instead of terminating a run without a report.
- Windows Node runners use `.cmd`/`.exe` entry points safely without enabling a shell.
- Windows suite temp paths use short 48-bit keys and are removed after execution.

## Product validation

- EagleEye final quality gate: PASS
  - pytest: 164 passed
  - Ruff check: PASS
  - Ruff format check: PASS
  - REST/MCP/browser/Report Hub operational smoke: PASS
  - Chromium, Firefox, WebKit: PASS
  - 200-request benchmark: 142.72 requests/s, p95 96.89 ms, zero failures
  - AI safety evaluations: 8/8 PASS
  - backup create and restore drill: PASS
- Strict EagleEye self-host: `3a8d291a58434fdfa757b4816e9a1c3b`, 3/3 PASS
- CONTINUE full Project QA: `76cd80c155d34bb58b529efd5c7e7c1d`, 9/9 PASS
- Cursor Agent CLI, Cursor Grok 4.5 High: technical gate PASS; no release approval or product commit performed by Cursor

## Operational interfaces

- REST `POST /api/v1/project-qa/discover`
- REST `POST /api/v1/project-qa/runs`
- REST `GET /api/v1/project-qa/runs/{runId}`
- MCP `discover_project_qa`
- MCP `run_project_qa`
- MCP `project_qa_run_status`
- CLI `uv run python scripts/run_project_qa.py <project-root>`
- PowerShell `scripts/run-project-qa.ps1`
