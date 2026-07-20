from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
    return round(ordered[index], 2)


async def benchmark(url: str, requests: int, concurrency: int, p95_limit_ms: float) -> dict:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    failures: list[str] = []

    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:

        async def request_once() -> None:
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        failures.append(f"HTTP {response.status_code}")
                except httpx.HTTPError as exc:
                    failures.append(type(exc).__name__)
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        await asyncio.gather(*(request_once() for _ in range(requests)))
        duration = time.perf_counter() - started

    p95 = percentile(latencies, 0.95)
    status = "PASS" if not failures and p95 <= p95_limit_ms else "FAIL"
    return {
        "schemaVersion": 1,
        "finishedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": status,
        "url": url,
        "sampleCount": requests,
        "concurrency": concurrency,
        "durationSeconds": round(duration, 3),
        "requestsPerSecond": round(requests / duration, 2),
        "failureCount": len(failures),
        "latencyMs": {
            "mean": round(statistics.fmean(latencies), 2),
            "p50": percentile(latencies, 0.50),
            "p95": p95,
            "p99": percentile(latencies, 0.99),
            "limitP95": p95_limit_ms,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded EagleEye health endpoint benchmark")
    parser.add_argument("--url", default="http://127.0.0.1:8766/health")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--p95-limit-ms", type=float, default=250.0)
    parser.add_argument("--output", type=Path, default=Path(".runtime/benchmark/latest.json"))
    args = parser.parse_args()
    if not 1 <= args.requests <= 5_000 or not 1 <= args.concurrency <= 64:
        raise SystemExit("requests must be 1..5000 and concurrency must be 1..64")
    report = asyncio.run(benchmark(args.url, args.requests, args.concurrency, args.p95_limit_ms))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
