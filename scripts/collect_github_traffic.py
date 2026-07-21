#!/usr/bin/env python3
"""Archive GitHub repository traffic that is otherwise retained for about 14 days."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.github.com"
OUTPUT = Path("analytics/github-traffic")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
DAILY_FIELDS = ["date", "clones", "unique_cloners", "views", "unique_visitors"]
SNAPSHOT_FIELDS = [
    "collected_at",
    "stars",
    "forks",
    "watchers",
    "open_issues",
    "release_downloads",
    "clone_window_count",
    "clone_window_uniques",
    "view_window_count",
    "view_window_uniques",
]


class CollectionError(RuntimeError):
    """Raised when collection cannot finish safely."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def api_get(path: str, token: str, **query):
    suffix = f"?{urlencode(query)}" if query else ""
    request = Request(
        f"{API}{path}{suffix}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "eagleeye-traffic-collector",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS API
            return json.load(response)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            message = (
                "TRAFFIC_TOKEN was rejected. Check expiration, repository selection, and "
                "Administration: Read-only permission."
            )
        else:
            message = f"GitHub API returned HTTP {exc.code} for {path}."
        raise CollectionError(message) from exc
    except (URLError, TimeoutError) as exc:
        raise CollectionError(f"GitHub API request failed for {path}: {exc}") from exc


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def merge_daily(existing: list[dict], clones: list[dict], views: list[dict]) -> list[dict]:
    by_date = {str(row["date"]): dict(row) for row in existing if row.get("date")}
    for source, count_field, unique_field in (
        (clones, "clones", "unique_cloners"),
        (views, "views", "unique_visitors"),
    ):
        for item in source:
            date = str(item.get("timestamp", ""))[:10]
            if not date:
                continue
            row = by_date.setdefault(date, {field: 0 for field in DAILY_FIELDS})
            row["date"] = date
            row[count_field] = int(item.get("count", 0))
            row[unique_field] = int(item.get("uniques", 0))
    return [by_date[date] for date in sorted(by_date)]


def merge_snapshots(existing: list[dict], snapshot: dict) -> list[dict]:
    by_date = {str(row["collected_at"])[:10]: dict(row) for row in existing if row.get("collected_at")}
    by_date[str(snapshot["collected_at"])[:10]] = snapshot
    return [by_date[date] for date in sorted(by_date)]


def release_downloads(repository: str, token: str) -> int:
    total = 0
    for page in range(1, 11):
        releases = api_get(f"/repos/{repository}/releases", token, per_page=100, page=page)
        if not isinstance(releases, list):
            raise CollectionError("Unexpected releases response from GitHub.")
        total += sum(
            int(asset.get("download_count", 0))
            for release in releases
            for asset in release.get("assets", [])
            if isinstance(asset, dict)
        )
        if len(releases) < 100:
            break
    return total


def should_collect(output: Path, now: datetime, min_hours: float, force: bool) -> bool:
    if force or not (output / "latest.json").exists():
        return True
    try:
        latest = json.loads((output / "latest.json").read_text(encoding="utf-8"))
        previous = datetime.fromisoformat(str(latest["collected_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return True
    return now - previous.astimezone(timezone.utc) >= timedelta(hours=min_hours)


def top_items(payload, fields: tuple[str, ...]) -> list[dict]:
    if not isinstance(payload, list):
        return []
    return [{field: item.get(field) for field in fields} for item in payload if isinstance(item, dict)]


def collect(repository: str, token: str, collected_at: datetime) -> dict:
    clones = api_get(f"/repos/{repository}/traffic/clones", token, per="day")
    views = api_get(f"/repos/{repository}/traffic/views", token, per="day")
    repo = api_get(f"/repos/{repository}", token)
    if not all(isinstance(item, dict) for item in (clones, views, repo)):
        raise CollectionError("Unexpected traffic response from GitHub.")

    return {
        "schema_version": 1,
        "repository": repository,
        "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
        "traffic_window_days": 14,
        "traffic": {
            "clones": {
                "count": int(clones.get("count", 0)),
                "uniques": int(clones.get("uniques", 0)),
                "daily": list(clones.get("clones", [])),
            },
            "views": {
                "count": int(views.get("count", 0)),
                "uniques": int(views.get("uniques", 0)),
                "daily": list(views.get("views", [])),
            },
        },
        "repository_metrics": {
            "stars": int(repo.get("stargazers_count", 0)),
            "forks": int(repo.get("forks_count", 0)),
            "watchers": int(repo.get("subscribers_count", 0)),
            "open_issues": int(repo.get("open_issues_count", 0)),
        },
        "release_downloads": release_downloads(repository, token),
        "popular_referrers": top_items(
            api_get(f"/repos/{repository}/traffic/popular/referrers", token),
            ("referrer", "count", "uniques"),
        ),
        "popular_paths": top_items(
            api_get(f"/repos/{repository}/traffic/popular/paths", token),
            ("path", "title", "count", "uniques"),
        ),
    }


def report(latest: dict) -> str:
    traffic = latest["traffic"]
    repo = latest["repository_metrics"]
    rows = [
        ("Clones (rolling window)", traffic["clones"]["count"]),
        ("Unique cloners", traffic["clones"]["uniques"]),
        ("Views (rolling window)", traffic["views"]["count"]),
        ("Unique visitors", traffic["views"]["uniques"]),
        ("Stars", repo["stars"]),
        ("Forks", repo["forks"]),
        ("Watchers", repo["watchers"]),
        ("Release downloads", latest["release_downloads"]),
    ]
    lines = [
        "# GitHub Traffic Report",
        "",
        f"Repository: `{latest['repository']}`  ",
        f"Collected: `{latest['collected_at']}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        *(f"| {name} | {value} |" for name, value in rows),
        "",
        "See `daily.csv`, `snapshots.csv`, and `latest.json` for machine-readable history.",
        "",
    ]
    return "\n".join(lines)


def persist(output: Path, latest: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    daily = merge_daily(
        read_csv(output / "daily.csv"),
        latest["traffic"]["clones"]["daily"],
        latest["traffic"]["views"]["daily"],
    )
    traffic = latest["traffic"]
    repo = latest["repository_metrics"]
    snapshot = {
        "collected_at": latest["collected_at"],
        "stars": repo["stars"],
        "forks": repo["forks"],
        "watchers": repo["watchers"],
        "open_issues": repo["open_issues"],
        "release_downloads": latest["release_downloads"],
        "clone_window_count": traffic["clones"]["count"],
        "clone_window_uniques": traffic["clones"]["uniques"],
        "view_window_count": traffic["views"]["count"],
        "view_window_uniques": traffic["views"]["uniques"],
    }
    snapshots = merge_snapshots(read_csv(output / "snapshots.csv"), snapshot)
    write_csv(output / "daily.csv", DAILY_FIELDS, daily)
    write_csv(output / "snapshots.csv", SNAPSHOT_FIELDS, snapshots)
    (output / "latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "REPORT.md").write_text(report(latest), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--min-hours", type=float, default=47)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    token = os.getenv("TRAFFIC_TOKEN", "")

    if not args.repository or not REPOSITORY.fullmatch(args.repository):
        print("Invalid or missing repository.", file=sys.stderr)
        return 2
    if not token:
        print("TRAFFIC_TOKEN is not configured.", file=sys.stderr)
        return 2
    if args.min_hours < 0:
        print("--min-hours must not be negative.", file=sys.stderr)
        return 2

    collected_at = now_utc()
    if not should_collect(args.output_dir, collected_at, args.min_hours, args.force):
        print("Skipped: cadence gate has not elapsed.")
        return 0
    try:
        latest = collect(args.repository, token, collected_at)
        persist(args.output_dir, latest)
    except CollectionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Collected GitHub traffic for {args.repository}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
