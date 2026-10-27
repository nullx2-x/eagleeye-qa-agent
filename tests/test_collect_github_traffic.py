from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import collect_github_traffic as collector
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
    now = datetime(2026, 7, 21, 0, 17, tzinfo=UTC)
    latest = {"collected_at": (now - timedelta(hours=24)).isoformat()}
    (tmp_path / "latest.json").write_text(json.dumps(latest), encoding="utf-8")

    assert not should_collect(tmp_path, now, min_hours=47, force=False)
    assert should_collect(tmp_path, now, min_hours=47, force=True)
    assert should_collect(tmp_path, now + timedelta(hours=24), min_hours=47, force=False)


@pytest.mark.parametrize(
    ("status", "headers", "expected"),
    [
        (401, {}, "invalid, expired, or revoked"),
        (403, {}, "secondary rate limit"),
        (403, {"X-RateLimit-Remaining": "0"}, "rate limited"),
        (429, {}, "rate limited"),
        (500, {}, "GitHub API HTTP 500"),
    ],
)
def test_api_errors_are_diagnosed_without_token(
    monkeypatch: pytest.MonkeyPatch, status: int, headers: dict[str, str], expected: str
) -> None:
    path = "/repos/example/project/traffic/views"
    dummy = "dummy-token-for-test"

    def reject(*args, **kwargs):
        raise HTTPError(f"https://api.github.com{path}", status, "error", headers, None)

    monkeypatch.setattr(collector, "urlopen", reject)
    with pytest.raises(collector.CollectionError) as exc_info:
        collector.api_get(path, dummy)

    message = str(exc_info.value)
    assert f"HTTP {status}" in message
    assert path in message
    assert expected in message
    assert dummy not in message


def test_collection_failure_preserves_history_and_reports_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "history"
    output.mkdir()
    (output / "daily.csv").write_text("date,clones\n2026-10-11,7\n", encoding="utf-8")
    (output / "latest.json").write_text('{"collected_at":"2026-10-11T00:00:00Z"}\n', encoding="utf-8")
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    summary = tmp_path / "summary.md"
    dummy = "dummy-token-for-test"
    responses = iter(
        [
            BytesIO(json.dumps({"count": 1, "uniques": 1, "clones": []}).encode()),
            HTTPError("https://api.github.com/repos/example/project/traffic/views", 403, "error", {}, None),
        ]
    )

    def get_next(*args, **kwargs):
        result = next(responses)
        if isinstance(result, HTTPError):
            raise result
        return result

    monkeypatch.setattr(collector, "urlopen", get_next)
    monkeypatch.setenv("TRAFFIC_TOKEN", dummy)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    result = collector.main(["--repository", "example/project", "--output-dir", str(output), "--force"])

    assert result == 1
    assert {path.name: path.read_bytes() for path in output.iterdir()} == before
    error = capsys.readouterr().err
    assert "::error title=GitHub traffic collection::" in error
    assert "HTTP 403" in error
    assert "HTTP 403" in summary.read_text(encoding="utf-8")
    assert dummy not in error
    assert dummy not in summary.read_text(encoding="utf-8")
