# GitHub repository traffic archive

This directory is updated by `.github/workflows/collect-repository-traffic.yml`.

The scheduled workflow starts daily at 00:17 UTC (09:17 JST), while the collector only writes a new snapshot when at least 47 hours have elapsed. This provides an approximately every-other-day archive without relying on an invalid cross-month cron expression. A manual workflow run can bypass the cadence gate.

Generated files:

- `daily.csv`: durable per-day clone and view history. GitHub exposes a rolling traffic window, so overlapping dates are replaced instead of added.
- `snapshots.csv`: repository-level metrics and rolling-window totals, one row per UTC collection date.
- `latest.json`: complete latest API snapshot, including popular referrers and paths.
- `REPORT.md`: human-readable latest summary.

Authentication uses the repository Actions secret `TRAFFIC_TOKEN`. Use a fine-grained personal access token limited to this repository with **Repository permissions → Administration: Read-only**. Do not commit the token or print it in workflow logs.

The token expiration date must be tracked operationally. When it expires, the workflow fails closed and no analytics files are updated.
