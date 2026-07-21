from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.collect_github_traffic import merge_daily, merge_snapshots, should_collect


def test_merge_daily_replaces_overlapping_days() -> None:
    existing = [
        {
            "date": "2026-07-19",
            "clones": "1",
            "unique_cloners": "1",
            "views": "3",
            "unique_visitors": "2",
        }
    ]
    clones = [{"timestamp": "2026-07-19T00:00:00Z", "count": 5, "uniques": 4}]
    views = [{"timestamp": "2026-07-20T00:00:00Z", "count": 8, "uniques": 6}]

    assert merge_daily(existing, clones, views) == [
        {
            "date": "2026-07-19",
            "clones": 5,
            "unique_cloners": 4,
            "views": "3",
            "unique_visitors": "2",
        },
        {
            "date": "2026-07-20",
            "clones": 0,
            "unique_cloners": 0,
            "views": 8,
            "unique_visitors": 6,
        },
    ]


def test_merge_snapshots_keeps_one_row_per_utc_day() -> None:
    existing = [{"collected_at": "2026-07-20T00:17:00Z", "stars": "1"}]
    replacement = {"collected_at": "2026-07-20T12:00:00Z", "stars": 2}

    assert merge_snapshots(existing, replacement) == [replacement]


def test_should_collect_honors_interval_and_force(tmp_path: Path) -> None:
    now = datetime(2026, 7, 21, 0, 17, tzinfo=timezone.utc)
    latest = {"collected_at": (now - timedelta(hours=24)).isoformat()}
    (tmp_path / "latest.json").write_text(json.dumps(latest), encoding="utf-8")

    assert not should_collect(tmp_path, now, min_hours=47, force=False)
    assert should_collect(tmp_path, now, min_hours=47, force=True)
    assert should_collect(tmp_path, now + timedelta(hours=24), min_hours=47, force=False)
