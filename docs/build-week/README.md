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

The 2026-07-17 submission tree retains historical browser-flow material. Current operational acceptance is produced by `scripts/quality-gate.ps1` and Project QA under `artifacts/project-qa/`; it supersedes the removed event-specific proof fixture.

The local report and explicit Markdown bug-report export are implemented; no report is uploaded automatically. Public GitHub visibility, the final rendered/uploaded video URL, the Devpost submission, and any public product URL remain release-gated until the user explicitly approves those external actions.

Never replace a release-gated placeholder with a success claim based only on a local artifact. Conversely, do not retain stale `IN_PROGRESS` language for a local path that has current machine-readable proof.
