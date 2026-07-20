# Devpost submission - EagleEye

> **Submission status:** Submitted to OpenAI Build Week on 2026-07-18 09:22:16 JST. Submission ID: `1089902`.

## Title

**EagleEye - Turn Real Browser Journeys into AI-Generated Regression Tests**

## Tagline

**Observe reality. Generate coverage. Replay proof.**

## Why we built it

Browser automation has an uncomfortable gap. Recorders preserve exactly what happened but rarely create the edge cases a strong QA engineer would add. Prompt-only test generators can propose many cases, but they lack trustworthy context about what a user actually did and can produce tests that look convincing without being runnable.

EagleEye joins those two halves. A user turns on a Chrome extension and follows a normal journey. EagleEye reduces the journey to privacy-aware evidence, preserves it as a deterministic regression test, asks OpenAI for complementary coverage, checks every case before execution, and replays the critical path locally. The result is not a chat answer. It is a test, a run, evidence, and a fix suggestion that a human can review.

## How it works

1. **Observe:** The user explicitly turns capture on and uses a local or approved site normally.
2. **Minimize:** EagleEye builds a sanitized DOM summary, visible-page evidence, and an action timeline without retaining raw input values or secret field types.
3. **Generate:** Codex App Server sends bounded context to OpenAI and returns schema-validated test cases, risks, and improvement suggestions.
4. **Check:** A deterministic quality checker rejects vague steps, missing assertions, unstable selectors, secrets, duplication, retry dependence, and unsafe scope.
5. **Replay:** Playwright executes the recorded path locally. AI suggestions do not become the oracle.
6. **Explain:** EagleEye stores the result and evidence metadata, classifies failures, and proposes the next fix.
7. **Share deliberately:** A human reviews the report before any export or publication.

## What is innovative

### Reality-anchored generation

The recorded journey is always retained as the critical path. OpenAI expands coverage around evidence instead of inventing a suite from a blank prompt.

### Two independent layers of trust

The model proposes; deterministic code validates and executes. Generated cases carry a source label, pass through a quality checker, and must earn evidence in Replay.

### Privacy as an input contract

The design rejects secret input types, strips secret-like URL parameters, avoids persisting typed values, confines browser execution to localhost by default, and treats page text as untrusted data.

### Useful failure, not demo theater

If OpenAI is unavailable, the recorded regression test remains usable and the fallback is labelled. If Replay fails, EagleEye reports the failure and evidence instead of converting it into a success narrative.

### Human-bounded repair

EagleEye can produce a fix handoff and has a bounded repair path, but production writes, release approval, and repair application remain explicit decisions. Automated modification fails closed when repository, attestation, model, environment, or change-limit checks are missing.

## OpenAI usage

EagleEye uses **Codex App Server** as its OpenAI integration layer. App Server owns the ChatGPT account authentication lifecycle and streams structured agent events over its protocol; EagleEye does not ask the user to paste a ChatGPT token into the product. The integration initializes an App Server session, runs a constrained read-only turn, and requests JSON that must match a schema.

For browser generation, the submission prompt contains only the test goal, sanitized URL, action types and accessible target labels, a safe DOM summary, and explicit safety boundaries. OpenAI returns complementary cases, risk observations, and fix suggestions. EagleEye's deterministic quality checker, Playwright runner, evidence collector, and human approval boundary remain authoritative.

Core Codex provider integration and the dedicated browser-generation route are implemented and tested. In the current Authorized target proof session, Codex App Server returned five schema-valid cases through `codex-agent` / `gpt-5.6-terra`; `available=true` and `fallbackUsed=false`. The mechanical case-quality gate scored the result `100 / PASS` before Playwright Replay.

Official reference: [Codex App Server documentation](https://learn.chatgpt.com/docs/app-server).

## Technical architecture

- Python 3.12
- FastAPI and Pydantic for strict local APIs and schemas
- Codex App Server for structured OpenAI turns and account-managed authentication
- Playwright for deterministic browser Replay and evidence capture
- Risk-adaptive test strategy and quality gates
- Pre-execution test-case quality checker
- SHA-256 evidence metadata and atomic local storage
- MCP for agent interoperability
- `uv` for locked environments
- `pytest` and Ruff for verification
- GitHub Actions matrix for Windows and Linux

## Current implementation status

| Capability | Release status |
|---|---|
| Risk-adaptive strategy, case checker, quality gate | Implemented |
| Local Playwright execution and hashed evidence | Implemented |
| Codex App Server provider | Implemented |
| Failure analysis, proposal handoff, bounded repair policy | Implemented |
| Browser-agent session/generation/replay code | End-to-end verified on the local Authorized target target |
| Chrome extension | Manifest V3, fixed ID, static verifier and ESLint pass; fresh unpacked Chromium ON/OFF flow verified |
| Local report and explicit Markdown export | Implemented and tested; no automatic public upload |
| Windows/Linux CI workflow | Implemented and required for the release commit |
| Six submission screenshots | Captured from the verified flow |
| Public source repository | Security-reviewed MIT release |
| Public video URL | Verified: <https://youtu.be/zLSLiG7QYr4> |
| Final Devpost submit | Submitted: <https://devpost.com/software/eagleeye-browser-native-ai-qa-agent> |

## Challenges we ran into

The hardest problem was not generating more text. It was deciding what the model is allowed to know and what it is allowed to decide. Browser pages can contain secrets and prompt-injection text; recordings can capture personal data; a plausible AI test can still be unsafe or non-runnable. We therefore separated observation, generation, deterministic validation, execution, evidence, and repair approval into distinct boundaries.

The second challenge was graceful degradation. The recorded path remains executable when OpenAI is disconnected, while the UI must clearly say that no AI cases were produced. That distinction is essential for an honest QA product and an honest demo.

## What is next

The following are future work, not current capabilities:

- package the unpacked extension for a signed store/release workflow after the hackathon;
- expand long-running cross-project regression evidence;
- add authenticated, expiring report sharing with retention and deletion controls;
- add stronger visual assertions and accessibility checks;
- evaluate the system across multiple real applications and long-running regression suites;
- add multi-user authorization and audit isolation before any shared-host deployment.

## GitHub

**https://github.com/nullx2-x/eagleeye-qa-agent**

The public MIT repository includes the no-account Quick Start, source, tests, architecture, privacy/security documentation, and reproducible release audit.

## Demo video

<https://youtu.be/zLSLiG7QYr4>

Verified duration: **2:55** (175.018667 seconds), 1920x1080 at 30fps. The local final candidate uses an AI-generated English voice created on-device with Kokoro-82M (`af_nova`), contains no background music, and includes 72 burned-in English subtitle cues plus SRT/VTT sidecars. Script: `docs/build-week/demo-script.md`.

## Public product URL

Not supplied. EagleEye is a local developer tool and the repository includes a login-free demo path and testing instructions; a localhost or private-network address is not represented as a public service.

## Submission screenshots

1. **[Extension ON and normal journey](screenshots/02-extension-recording.png)**
   Caption: "Capture starts with explicit user intent."

2. **[DOM, screen, and interaction history](screenshots/01-dashboard.png)**
   Caption: "Bounded context from what the user actually did."

3. **[Recorded and AI-generated cases](screenshots/05-test-list.png)**
   Caption: "OpenAI adds coverage; the recorded critical path remains deterministic."

4. **[Replay with result and evidence hash](screenshots/04-replay-result.png)**
   Caption: "The test runner, not the model, produces proof."

5. **[Final report and fix suggestion](screenshots/06-report.png)**
   Caption: "From user intent to an evidence-backed next action."

Optional hero: **[Five-stage dashboard](screenshots/01-dashboard.png)**.

## Final submission fields

- Team members: **nullx2-x (individual)**
- Build Week category or track: **Developer Tools**
- Repository: **https://github.com/nullx2-x/eagleeye-qa-agent**
- Video: **public 2:55 English demo with burned-in captions verified**
- Public URL: **not supplied; repository Quick Start is the evaluation path**
- Screenshots: **6 reviewed product assets included in the repository and Devpost entry**
- License: MIT
