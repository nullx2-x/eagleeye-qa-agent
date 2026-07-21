#!/usr/bin/env python3
"""Collect GitHub repository traffic and persist a durable history."""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://api.github.com"
OUTPUT = Path("analytics/github-traffic")
DAILY_FIELDS = ["timestamp", "clones", "unique_cloners", "views", "unique_visitors"]
SNAPSHOT_FIELDS = [
    "collected_at",
    "stars",
    "forks",
    "watchers",
    "open_issues",
    "release_downloads",
]


def request_json(path: str, token: str):
    request = Request(
        f"{API}{path}",
        headers={
            "Accept": "application