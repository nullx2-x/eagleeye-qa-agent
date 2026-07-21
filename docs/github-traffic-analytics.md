# Repository traffic collection

EagleEye archives GitHub repository traffic because GitHub exposes clone and view detail only for a rolling window. The collector runs in GitHub Actions and stores overlapping daily values by date, preventing repeated collections from double-counting the same traffic.

## Data collected

- clones and unique cloners;
- views and unique visitors;
- stars, forks, watchers, and open issues;
- release asset download totals;
- popular referrers and repository paths.

## Schedule

The workflow is triggered every day at 00:17 UTC (09:17 JST). `scripts/collect_github_traffic.py` checks `analytics/github-traffic/latest.json` and skips scheduled runs until 47 hours have elapsed. Manual runs can use the `force` input.

## Authentication boundary

`TRAFFIC_TOKEN` must be stored as a GitHub Actions repository secret. The fine-grained token should be restricted to `eagleeye-qa-agent` and grant only **Administration: Read-only**. The workflow's built-in `GITHUB_TOKEN` is used separately to commit generated analytics files.

## Failure behavior

Missing, expired, or insufficiently scoped credentials stop the workflow before repository data is modified. API responses do not overwrite existing history unless the collection completes successfully.
