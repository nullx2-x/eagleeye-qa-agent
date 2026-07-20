# OpenAI Build Week submission checklist - EagleEye 1.0.0

Release snapshot: 2026-07-20 (JST)

This checklist records the public release state. A checked item means the implementation and
its cited evidence exist; marketing language alone is not evidence.

## Phase 1 - Five-minute MVP story

- [x] The English README explains the value, trust boundary, and winning path above the fold.
- [x] The no-account Quick Start reaches the local dashboard, MCP service, browser flow, Replay, and report.
- [x] The recorded critical path still runs when AI is unavailable or times out.
- [x] README, MIT License, `.env.example`, Privacy, Security, Compliance, and third-party notices exist.

## Phase 2 - OpenAI integration

- [x] Codex App Server reuses the locally authenticated Codex account without exposing its OAuth token to EagleEye.
- [x] Direct OpenAI API mode uses an API key and does not imitate a nonexistent end-user OAuth flow.
- [x] Prompts contain only bounded, sanitized browser context and require schema-valid output.
- [x] Provider errors, timeouts, unavailable AI, and missing configuration produce explicit guidance and deterministic fallback.
- [x] AI suggestions cannot replace the runner result, approve a release, or silently apply a repair.

## Phase 3 - Browser-native QA agent

- [x] Manifest V3 extension with explicit ON/OFF capture and minimum permissions.
- [x] Bounded DOM summary, action history, and opt-in visible screenshot capture.
- [x] OpenAI-assisted test generation plus deterministic quality validation.
- [x] Playwright Replay with screenshot, WebM, byte count, MIME type, timestamp, and SHA-256 evidence.
- [x] HTML and Markdown reports with repair suggestions and explicit bug-report export.
- [x] Natural-language intent, Japanese UI/documentation, MCP integration, history evidence, and bounded repair handoff.

## Phase 4 - Product UI

- [x] Start/dashboard state, session flow, test list, running/result state, and report view are implemented.
- [x] Dark product styling and readable success/failure/fallback states are demonstrated in six reviewed screenshots.
- [x] Untrusted values are escaped and absolute local paths or credentials are not rendered into reports.

## Phase 5 - Demo video

- [x] Public 2:55 video follows problem → AI generation → Replay → report → summary.
- [x] English AI narration is disclosed and 72 English caption cues are burned in.
- [x] 1920x1080 H.264/AAC video decodes end to end and remains understandable while muted.
- [x] Video: <https://youtu.be/zLSLiG7QYr4>

## Phase 6 - GitHub release quality

- [x] English and Japanese READMEs, Quick Start, Architecture, screenshots, install steps, and MIT License are present.
- [x] All third-party Actions are pinned to full commit SHAs and checkout credentials are not persisted.
- [x] actionlint 1.7.12 validates the CI and CodeQL workflows.
- [x] Windows and Linux CI run pytest, Ruff lint, Ruff format, and repository-clean checks.
- [x] CodeQL analyzes Python and JavaScript/TypeScript; Private pre-release SARIF is retained as an artifact and Public results upload to Code Scanning.
- [x] Public-release invariants check links, required files, secret-like environment values, action pins, extension permissions, internal reports, and machine-specific paths.

## Phase 7 - Devpost

- [x] Title, tagline, problem, implementation, innovation, future work, OpenAI usage, architecture, and limitations are documented.
- [x] GitHub: <https://github.com/nullx2-x/eagleeye-qa-agent>
- [x] Demo video: <https://youtu.be/zLSLiG7QYr4>
- [x] Devpost: <https://devpost.com/software/eagleeye-browser-native-ai-qa-agent>
- [x] Five primary screenshots plus an optional hero/architecture asset are included.
- [x] No hosted product URL is claimed; evaluation follows the local-first repository Quick Start.

## Phase 8 - Reviewer questions

- [x] **Why:** browser recorders lack intelligent coverage, while prompt-only generators lack real execution context.
- [x] **How:** explicit browser capture → minimization → OpenAI generation → deterministic validation → Playwright proof → human decision.
- [x] **Innovation:** reality-anchored AI coverage with an independent execution oracle and privacy as an input contract.
- [x] **Future:** signed extension packaging, stronger visual/accessibility assertions, authenticated report sharing, and multi-user isolation.

## Phase 9 - Publication audit

- [x] Gitleaks 8.30.1 scanned all fetched reachable commits with zero findings.
- [x] No non-public personal data, private infrastructure address, local username, machine-specific user path, key, token, password, or credential is present in the public candidate.
- [x] Dated internal reports and generated runtime artifacts are excluded from the public tree.
- [x] `uv sync --locked --dev` succeeds; 167 pytest tests pass; Ruff lint and format pass.
- [x] Chrome-extension safety verifier and ESLint pass.
- [x] OSV and npm audits report zero known vulnerabilities in the checked locked dependencies; Bandit reports zero high/medium findings.
- [x] Public GitHub, video, README links, and Devpost entry have an unauthenticated evaluation path.
- [x] Release evidence and rollback guidance are recorded in [the publication audit](../release/1.0.0-publication-audit.md).

## Residual scope

Cross-browser Firefox/WebKit coverage, signed Chrome Web Store distribution, authenticated
multi-user report hosting, and organization-specific legal certification are future work. They
are not represented as current features and do not weaken the local-first release boundary.
