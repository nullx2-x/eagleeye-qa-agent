# EagleEye - OpenAI Build Week submission pack

This directory is the working submission pack for EagleEye. It is written for judges and the release team, while keeping the implementation status explicit.

## Core story

**Chrome extension ON -> normal user journey -> privacy-safe DOM, screen, and interaction-history analysis -> OpenAI-powered test generation -> deterministic Replay -> fix suggestions -> shareable evidence.**

## Documents

- [Architecture](architecture.md): judge-facing system design, trust boundaries, OpenAI integration, and implementation status.
- [Demo script](demo-script.md): a timed 2:55 recording plan with live-evidence gates.
- [Devpost submission](devpost-draft.md): submitted copy, public links, and media references.
- [Phase checklist](submission-checklist.md): mechanical Phase 1-9 and bonus readiness gates.
- [Publication security](publication-security.md): mandatory pre-publication security procedure.

## Verified snapshot

The current submission tree retains the reproducible browser-flow material. Operational acceptance is produced by `scripts/quality-gate.ps1`, `scripts/publication_audit.py`, and Project QA under `artifacts/project-qa/`; generated runtime artifacts are not committed.

The local report and explicit Markdown bug-report export are implemented; no report is uploaded automatically. The source repository, captioned demo, and Devpost entry use the public links below. EagleEye remains a local-first developer tool and does not claim a hosted product URL.

- Repository: <https://github.com/nullx2-x/eagleeye-qa-agent>
- Captioned demo: <https://youtu.be/zLSLiG7QYr4>
- Devpost: <https://devpost.com/software/eagleeye-browser-native-ai-qa-agent>
