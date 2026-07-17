# EagleEye - OpenAI Build Week submission pack

This directory is the working submission pack for EagleEye. It is written for judges and the release team, while keeping the implementation status explicit.

## Core story

**Chrome extension ON -> normal user journey -> privacy-safe DOM, screen, and interaction-history analysis -> OpenAI-powered test generation -> deterministic Replay -> fix suggestions -> shareable evidence.**

## Documents

- [Architecture](architecture.md): judge-facing system design, trust boundaries, OpenAI integration, and implementation status.
- [Demo script](demo-script.md): a timed 2:55 recording plan with live-evidence gates.
- [Devpost draft](devpost-draft.md): submission copy and explicit media/link placeholders.
- [Phase checklist](submission-checklist.md): mechanical Phase 1-9 and bonus readiness gates.
- [Publication security](publication-security.md): mandatory pre-publication security procedure.

## Verified snapshot

The 2026-07-17 submission tree has current end-to-end proof for the complete local winning path. A fresh unpacked Chromium profile loaded the checked Manifest V3 extension, remained silent while OFF (`session delta = 0`), started capture through the real keyboard command, observed the previously tested WordPress site, generated five cases through Codex App Server with `fallbackUsed=false`, passed the mechanical case-quality gate at `100`, and replayed the recorded journey with Playwright in `1,745 ms`. The run stored screenshot and WebM evidence with byte counts, timestamps, and SHA-256 hashes. Six current product screenshots plus one Architecture image are tracked under `screenshots/`, and the machine-readable run record is [extension-wordpress-e2e.json](evidence/extension-wordpress-e2e.json).

The local report and explicit Markdown bug-report export are implemented; no report is uploaded automatically. Public GitHub visibility, the final rendered/uploaded video URL, the Devpost submission, and any public product URL remain release-gated until the user explicitly approves those external actions.

Never replace a release-gated placeholder with a success claim based only on a local artifact. Conversely, do not retain stale `IN_PROGRESS` language for a local path that has current machine-readable proof.
