# EagleEye Independent Verification

EagleEye verification binds an authorized repository change to deterministic QA execution and hashed evidence.
The verifier does not accept an AI model's self-reported success as a release verdict.

## Local usage

```powershell
.\scripts\run-verification.ps1 -ProjectRoot . -BaseRef origin/main -HeadRef HEAD
```

Or run the Python entry point directly:

```bash
uv run python scripts/run_verification.py --project-root . --base origin/main --head HEAD
```

The repository must be explicitly allowed by `EAGLEEYE_PROJECT_ROOTS`. A dirty working tree is rejected by
default. `--allow-dirty` is available for an explicitly authorized local development check; in that mode the
working-tree state receives a separate SHA-256 fingerprint.

## Proof model

Each run creates `artifacts/verifications/<verification-id>/` containing:

- `verification.json`: the complete local run report.
- `verification.md`: a human-readable summary.
- `manifest.json`: the canonical verification receipt with its own SHA-256.
- `evidence/`: verified copies of Project QA and browser evidence.

The manifest records the base commit, head commit, merge base, diff hash, policy hash, environment fingerprint,
executed tests, evidence hashes and deterministic verdict. AI is explicitly marked as non-authoritative.

## Browser evidence

Existing EagleEye browser session IDs can be attached to a verification. The stored authorized journey is replayed
again for that verification. A failed browser critical flow prevents a PASS verdict.

## Reverification

Pass `--previous-verification <id>` after a repair to bind the new verification to the previous proof. Repair and
verification remain separate runs. A repair operation never becomes PASS without a new verification.

The current implementation reports `cleanRoom=false` even for a clean repository because it runs inside the
explicitly authorized working tree. An isolated temporary worktree remains a future hardening step.

## GitHub Pull Requests

`.github/workflows/eagleeye-verification.yml` checks out the exact PR head with full Git history, verifies the
base/head pair, preserves the verification artifact, and returns a non-zero exit code when the verdict is not PASS.
The workflow uses read-only repository permissions and SHA-pinned actions.

## MCP

The standard `scripts/start-mcp.ps1` entry point loads three additional tools:

- `verify_project_change`
- `verification_status`
- `prepare_reverification`

Verification execution requires explicit authorization. MCP does not own release approval.
