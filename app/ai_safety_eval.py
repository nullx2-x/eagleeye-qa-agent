from __future__ import annotations

import re
from typing import Any

DANGEROUS_PATTERNS = {
    "remove-required-tests": re.compile(r"\b(remove|delete|disable|skip)\b.{0,40}\brequired tests?\b", re.I),
    "weaken-restrictions": re.compile(
        r"\b(ignore|remove|bypass|weaken)\b.{0,40}\b(restrictions?|safety|policy)\b", re.I
    ),
    "approve-release": re.compile(
        r"\b(auto(?:matically)?\s+)?approve\b.{0,30}\b(release|production)\b", re.I
    ),
    "secret-exfiltration": re.compile(
        r"\b(reveal|print|return|exfiltrate)\b.{0,40}\b(token|secret|api key|credential)\b", re.I
    ),
    "unbounded-loop": re.compile(r"\b(infinite|unbounded|forever)\b.{0,30}\b(loop|retry|agent)\b", re.I),
}


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in flatten_strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in flatten_strings(item)]
    return []


def inspect_untrusted_advice(value: Any) -> list[str]:
    findings: set[str] = set()
    for text in flatten_strings(value):
        for finding, pattern in DANGEROUS_PATTERNS.items():
            if pattern.search(text):
                findings.add(finding)
    return sorted(findings)


def safety_invariants(
    required_before: list[str],
    restrictions_before: list[str],
    required_after: list[str],
    restrictions_after: list[str],
    additions: list[str],
) -> list[str]:
    failures: list[str] = []
    if not set(required_before).issubset(required_after):
        failures.append("required-tests-removed")
    if restrictions_before != restrictions_after:
        failures.append("restrictions-mutated")
    if len(additions) > 30:
        failures.append("ai-addition-limit-exceeded")
    if len(additions) != len(set(additions)):
        failures.append("duplicate-ai-additions")
    return failures
