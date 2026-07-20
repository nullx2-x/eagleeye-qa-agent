# EagleEye Build Week demo script - 2:55

## Recording status

The winning path passed a fresh end-to-end run and the six product screenshots plus one Architecture image were captured. The published 2:55 HyperFrames video uses English AI narration generated locally by Kokoro-82M (`af_nova`) and 72 burned-in English subtitle cues, so it remains understandable when Devpost autoplays muted. The exact narration is the ten-scene text in `videos/eagleeye-build-week/audio_request.json`; the longer paragraphs below remain development reference material.

The requested segment caps add up to 3:30 if used in full. This script keeps the same order while fitting the required 2:30-3:00 total:

| Segment | Time | Duration | Cap |
|---|---:|---:|---:|
| Problem | 0:00-0:25 | 25 sec | 30 sec |
| AI generation | 0:25-1:15 | 50 sec | 60 sec |
| Replay | 1:15-2:05 | 50 sec | 60 sec |
| Report | 2:05-2:30 | 25 sec | 30 sec |
| Close | 2:30-2:55 | 25 sec | 30 sec |

Target runtime: **2:55**.

## Hard preflight - stop recording if any item fails

- [x] The demo target is local, resettable, contains no personal data, and its final URL is `http://127.0.0.1:8888/`.
- [x] The checked extension is installed unpacked in fresh Chromium and visibly shows **EagleEye ON**.
- [x] EagleEye `/health` returns `status=ok` and the browser-agent endpoints appear in the running OpenAPI document.
- [x] The extension creates a session, sends four sanitized observations, and stops capture without console errors.
- [x] Integrated negative tests and the safe-summary contract prevent typed values, password/OTP/card fields, secret query values, and credentials from entering persisted browser observations.
- [x] `codex-agent` reports connected and the fresh generation returned five cases with `available=true`, `fallbackUsed=false`.
- [x] The deterministic recorded case remains visible and separately labelled.
- [x] Replay ran against the local Authorized target target and produced `PASS`, `1,745 ms`, screenshot/WebM evidence, and hashes.
- [x] The report displays provider/model, AI/recorded source labels, quality score, run outcome, evidence metadata, and suggestions.
- [ ] The controlled regression fixture, if used, is documented, local-only, and visibly enabled; no result is edited into the video.
- [x] Browser notifications, bookmarks, account avatars, local usernames, absolute paths, unrelated tabs, and raw session IDs are absent from the six selected product screenshots.
- [x] The public GitHub and video URLs were checked independently; the project accurately identifies the product surface as a local-first Quick Start rather than a hosted SaaS.

## Shot plan and narration

### 0:00-0:25 - Problem and normal operation

**Screen**

Open the clean local demo site. Pin the EagleEye extension so its icon and **ON** state are visible. Start capture, then perform one ordinary journey: open the target page, select a public option, and click the primary action. Use synthetic data only.

**Narration - about 54 words**

> Browser tests usually start after a developer guesses what users will do. EagleEye starts with what a user actually does. I turn the extension on and use this local site normally. It captures the journey's structure and visible state, while input values and secret fields stay out of the recording.

**Visible proof**

- Extension state: `ON`
- Capture count increments
- No raw typed value appears in the timeline

### 0:25-1:15 - DOM, screen, history, and OpenAI test generation

**Screen**

Open the EagleEye session. For roughly five seconds, show the three inputs together: safe DOM summary, visible-page screenshot, and interaction timeline. Click **Generate tests**. Show the recorded critical-path case first, then the separately labelled AI cases, priorities, assertions, and quality score.

**Narration - about 105 words**

> EagleEye combines three kinds of evidence: a sanitized DOM summary, the visible page, and the action history. The page is untrusted data, never an instruction. Through Codex App Server, OpenAI receives only the bounded test context and returns schema-validated test ideas. The original journey is always preserved as a deterministic critical-path test. AI adds the cases humans tend to miss - state transitions, negative paths, and risky controls. Before anything runs, EagleEye checks every case for vague steps, missing assertions, unstable selectors, secrets, duplication, and unsafe scope. If OpenAI is unavailable, the recorded test still works; the product fails visibly instead of inventing an AI result.

**Visible proof**

- `Recorded` and `AI` source labels are distinct
- AI provider/model and fallback state are visible
- Test-quality result is visible

### 1:15-2:05 - Deterministic Replay and fix suggestion

**Screen**

Click **Replay locally**. Show Playwright progress, then the result and fresh evidence. Preferred take: enable a documented, pre-seeded local regression before Replay so the run fails honestly and produces a specific recommendation. If that fixture does not exist, record a passing Replay and show a genuine improvement suggestion from the same run; do not stage a failure.

**Narration - about 102 words**

> Now Replay turns the observation into proof. Playwright repeats the recorded journey locally; the model is not the test oracle. This controlled demo regression changes the expected interaction, so Replay catches it. EagleEye preserves the error, screenshot or video metadata, timestamp, and SHA-256 evidence, then classifies the failure and proposes the smallest next action. A repair proposal is not silently applied. Production writes and release approval remain human decisions, and bounded self-repair is allowed only when its clean-repository, local-only, attestation, model, and change-limit gates all pass.

**Visible proof**

- Replay status is from the current run
- Failure category or pass result is visible
- Evidence hash is visible
- Suggestion is tied to the current run

### 2:05-2:30 - Report and sharing boundary

**Screen**

Open the generated report. Scroll once through generated tests, fix suggestions, and execution evidence. End on the explicit **Markdown bug report** export. Do not imply that this local attachment was uploaded automatically.

**Narration - about 52 words**

> The final report connects intent to evidence: what the user did, what OpenAI added, what Replay proved, and what should change next. Sharing is explicit, never an automatic upload. Today EagleEye is local-first; a public share link stays disabled until authentication, retention, and publication checks are complete.

### 2:30-2:55 - Close

**Screen**

Return to a single summary frame showing the extension, generated cases, Replay result, and report. Overlay the product line: **Observe reality. Generate coverage. Replay proof.**

**Narration - about 52 words**

> EagleEye closes the gap between real behavior and maintainable QA: extension on, normal operation, safe context, OpenAI-generated coverage, deterministic Replay, and evidence-backed fixes. It does not ask teams to trust an AI demo. It gives them a repeatable test and the proof to decide what ships. Observe reality. Generate coverage. Replay proof.

## Edit rules

- Keep one continuous pointer and clock style so cuts do not imply a fake live result.
- Speed up only idle loading footage; never speed up or splice the status transition itself.
- Caption `Recorded`, `AI-generated`, `Replay`, `Evidence`, and `Human approval` consistently.
- If OpenAI falls back or Replay fails unexpectedly, stop and diagnose. Do not relabel fallback output as AI output.
- Use 1080p or higher, 125-150% UI zoom, large cursor, and embedded captions.
- Final exported duration must be between 2:30 and 3:00; target is 2:55.

## Final asset state

- Demo target URL: `http://127.0.0.1:8888/` (local Authorized target proof target)
- Public product URL: **not supplied; the repository Quick Start is the current local-first product surface**
- Local final video: `videos/eagleeye-build-week/output/eagleeye-build-week-submission-en-captioned.mp4` (1920x1080, 30fps, 175.018667 seconds)
- Subtitle sidecars: `videos/eagleeye-build-week/assets/captions/eagleeye-build-week.en.srt` and `.vtt`
- Video URL: <https://youtu.be/zLSLiG7QYr4>
- Public GitHub URL: <https://github.com/nullx2-x/eagleeye-qa-agent>
- Final video checksum: `B4E9B44131C666AF8C2E1EECBD9BEB900FCD2CBB062AAB3CBD1B9C083D1534B4` (SHA-256)
- Screenshots: `docs/build-week/screenshots/01-dashboard.png` through `06-report.png`

Disclosure: the English narration voice is AI-generated locally with Kokoro-82M. No background music is used.
