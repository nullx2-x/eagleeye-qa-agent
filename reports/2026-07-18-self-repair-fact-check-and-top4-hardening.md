# EagleEye bounded self-repair fact check and top-four hardening

Status: **IMPLEMENTED / METRICS NOT YET BENCHMARKED**

Date: 2026-07-18 JST

Reviewed base: `nullx2-x/eagleeye-qa-agent:main` at `2683154`

Method: repository code, configuration, tests, and tracked reports were inspected. No claim of measured AI repair accuracy or repair latency is made.

## Conclusion

The supplied review correctly identified four material design gaps: evidence content was not supplied to the evaluator/planner, the complete repair transaction lacked a project lock, verification side effects could remain in the original worktree, and the plan schema could not express a safe refusal. Those four gaps are addressed by this change.

The original numeric scores are reviewer judgments rather than measured facts. They should not be reused as performance or accuracy evidence. The accurate product claim after this change is:

> EagleEye implements a fail-closed local bounded-repair transaction with content-bound redacted text evidence, project-scoped locking, disposable-worktree verification, exact replacement limits, and an explicit no-safe-repair result. End-to-end AI repair accuracy and latency remain unbenchmarked across controlled failure fixtures.

## Claim ledger

| # | Supplied claim | Fact-check before this change | Result after this change |
|---|---|---|---|
| 1 | The AI receives path-string hashes, not evidence contents | **Confirmed.** `RepairService.evaluate()` and `_plan()` hashed `evidencePaths`; they did not read the artifact. `failureSummary` and repository inspection were the main diagnostic inputs. | **Resolved for bounded UTF-8 evidence.** Trusted `artifacts/runs` text receives bounded redaction and a content digest. Binary/visual evidence remains metadata-only and is listed as a residual limitation. |
| 2 | `test_defect` / build-metadata eligibility conflicts with protected paths | **Confirmed with nuance.** `test_defect` was eligible while `tests/` was protected. The build-metadata class was broader than the practically editable set, although ordinary documentation was not globally protected. | **Open.** This was priority 5, outside the requested top four. The evaluator should next receive an explicit editable capability summary or use narrower classes. |
| 3 | The schema cannot return “not safely repairable” | **Confirmed.** `files` required at least one item. | **Resolved.** `RepairPlan.action=no_safe_repair`, an empty file list, response status `NO_SAFE_REPAIR`, and a zero-write regression test were added. |
| 4 | There is no project-wide repair lock | **Confirmed.** Codex App Server serialized turns, but the authorize-plan-checkpoint-apply-verify-finish transaction was not locked by project root. | **Resolved.** A canonical-root keyed process lock and non-blocking OS file lock are held from before authorization through final audit creation. Concurrent repair is denied. |
| 5 | Rollback does not remove verification side effects | **Confirmed.** Rollback restored only planned files; unrelated tracked/untracked verification writes could remain. | **Resolved for apply-mode verification.** Planned changes and fixed verification run in a disposable detached worktree. Unapproved changes fail there; only verified planned postimages are published to the still-clean original worktree. |
| 6 | Repair success and latency are not benchmarked | **Confirmed with nuance.** The tracked benchmark targets `/health`. The repository records deterministic self-repair safety canaries, but does not contain a controlled multi-fixture AI accuracy/latency benchmark. | **Open and explicitly documented.** Unit-level safety evidence must not be presented as AI repair accuracy. |
| 7 | Configured timeout sum can reach about 3,060 seconds | **Confirmed as a theoretical sum, not a measurement.** 180 seconds for evaluation plus two repetitions of 240 + 300 + 900 equals 3,060 seconds, excluding overhead and early termination. The API remains synchronous. | **Open.** Job APIs, cancellation, targeted-first verification, and stage timing remain future work. |
| 8 | `confidence` is not an apply gate | **Confirmed.** It is recorded but no threshold is enforced. | **Open.** A calibrated threshold requires controlled evidence; an arbitrary threshold would create confidence theater. |
| 9 | Editable scope is primarily denylist-based | **Confirmed.** New ordinary source files are eligible unless a protected-path/sensitive rule rejects them. `app/browser_agent.py`, which contains important browser privacy sanitization, was not in the protected set. | **Open.** Move to project-specific editable allowlists. Newly added repair-control modules are protected in the interim. |

## Corrections to the supplied review

### “Self-repair is currently disabled by default” was not uniformly true

Before this change, `.env.example` set `EAGLEEYE_SELF_REPAIR_ENABLED=0`, but `scripts/start-eagleeye.ps1` set it to `1` when the environment variable was absent. Therefore the blanket statement “default disabled” was inaccurate for the standard PowerShell launcher.

This change makes the launcher default `0`. An operator must now explicitly set `EAGLEEYE_SELF_REPAIR_ENABLED=1`; all existing policy gates still apply.

### Safety canaries are not an accuracy benchmark

The tracked 2026-07-16 report records five self-repair canary tests for apply/audit, rollback/retry, one-use attestation, request binding, and forged-attestation rejection. This is valid safety-control evidence. It does not measure model diagnosis accuracy, successful repair rate, p50/p95, or realistic browser-failure coverage.

### Numeric ratings are not facts

Ratings such as 8/10 or 4/10 have no stated rubric, sample, or confidence interval. They can be retained as personal review opinion, but not as product evidence. This report uses `confirmed`, `resolved`, `open`, and `unmeasured` instead.

## Implemented top four

### 1. Safe, content-bound evidence

- Only files under the trusted project `artifacts/runs` boundary are considered.
- At most 10 artifacts are processed.
- UTF-8 text/JSON/log/XML/YAML/Markdown/CSV/HTML files receive at most 8,192 characters each and 32,768 characters total.
- Bearer values, common secret assignments, OpenAI-style keys, JWTs, email addresses, Windows user paths, and `/Users` or `/home` paths are redacted.
- The failure summary receives the same prompt redaction.
- Paths are represented only by SHA-256 in AI input; local absolute paths are not disclosed.
- Symlink, reparse-point, hard-link, out-of-root, missing, non-regular, and over-256-MiB inputs fail closed or become unavailable metadata.
- Images, video, oversized text, and unknown binaries are metadata-only. Raw binary bytes are never embedded in the prompt.
- The canonical safe-evidence digest is included in the fresh attestation and exact request binding. Evidence substitution between evaluation and execute downgrades apply to proposal-only.
- Evidence is labeled untrusted and prompt instructions inside an excerpt are data, not authority.

### 2. Project-scoped transaction lock

- Lock identity is the normalized canonical project root, not only the caller-supplied project ID.
- A process-level lock prevents concurrent threads in one service process.
- A hashed lockfile with native Windows or POSIX non-blocking locking protects cooperating processes.
- The lock is acquired before `authorize()` and retained through planning, verification, publication, and hashed audit generation.
- A competing request returns `DENIED`; it does not wait behind a potentially long repair or consume an apply transaction concurrently.

### 3. Disposable Git worktree verification

- Planning remains read-only against the locked original root.
- The planned source preimages are policy-validated first, then copied byte-for-byte into a detached temporary Git worktree. This avoids Windows checkout line-ending drift.
- Replacement, postimage validation, Ruff/pytest, and changed-path comparison run in the disposable worktree.
- Verification-created untracked or tracked side effects remain in that worktree and are discarded.
- The original root is checked clean again immediately before publication.
- Only the already validated planned files are atomically written to the original root, followed by SHA-256 and changed-path verification.
- If publication is interrupted, the existing checkpoint is used to restore planned original files and clean-Git state must be proven.

### 4. Explicit `no_safe_repair`

- `action=repair` requires one or more files.
- `action=no_safe_repair` requires zero files.
- The planner prompt explicitly selects this result for insufficient evidence or no eligible edit.
- EagleEye returns `NO_SAFE_REPAIR` as a normal, audited, zero-write outcome instead of forcing invalid edits or exhausting retries.

## Verification added for this change

- safe evidence content is redacted and local paths are absent from the evaluator prompt;
- changing ignored runtime evidence invalidates the content-bound apply attestation;
- 32 concurrent attestation checks still permit exactly one consumption;
- a concurrent repair on one canonical root is denied;
- a verification command that creates an untracked file and fails leaves no side effect in the original worktree;
- `no_safe_repair` returns normally with zero file writes;
- existing apply, proposal, rollback/retry, dirty-Git, model, production, symlink, sensitive-path, byte, and changed-line controls remain covered.

## Residual risks and next direction

1. Align eligibility classes with an explicit per-project editable allowlist. Protect privacy and authorization modules by default.
2. Build controlled broken fixtures and record AI repair success/failure, false-repair rate, p50/p95, stage timings, and model/version.
3. Move synchronous evaluate/execute into cancellable jobs with status and retention controls.
4. Calibrate a confidence gate from fixture data instead of choosing an unevidenced constant.
5. Add a privacy-reviewed visual evidence pipeline if screenshot semantics are required. Until then, screenshots and videos remain metadata-only.
6. Add a true multi-process lock integration test and orphan-worktree cleanup telemetry. A cleanup failure can leave a temporary detached directory, although it cannot publish unverified side effects to the original root.

## Decision

The top-four hardening is suitable for review as one cohesive security transaction change. It does not justify claims of high repair accuracy or validated repair performance. Merge should depend on full test, lint, secret scan, and CI results recorded in the pull request.
