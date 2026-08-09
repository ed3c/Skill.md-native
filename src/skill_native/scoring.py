from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from .models import EvidenceBundle


@dataclass(frozen=True)
class ScorePolicy:
    version: str = "v0.1"
    critical_finding_severities: tuple[str, ...] = ("critical", "high")


@dataclass(frozen=True)
class ScoreResult:
    policy_version: str
    security_gate: str
    confidence: str
    sample_count: int
    raw_metrics: dict[str, float | int | str]
    aggregate_score: float


def _severity(finding: dict) -> str:
    value = finding.get("severity") or finding.get("severity_id") or finding.get("severity_name") or ""
    return str(value).lower()


def score_evidence(runs: Iterable[EvidenceBundle], policy: ScorePolicy | None = None) -> ScoreResult:
    policy = policy or ScorePolicy()
    items = list(runs)
    if not items:
        raise ValueError("at least one evidence bundle is required")

    critical = sum(
        1 for run in items for finding in run.findings if _severity(finding) in policy.critical_finding_severities
    )
    assertion_rates = []
    exit_success = []
    undeclared_network = 0
    for run in items:
        values = list(run.assertions.values())
        assertion_rates.append(sum(bool(v) for v in values) / len(values) if values else 0.0)
        exit_success.append(1.0 if run.exit_code == 0 else 0.0)
        undeclared_network += sum(
            1 for event in run.network if str(event.get("action", event.get("action_name", ""))).lower() == "denied"
        )

    task_success = mean(exit_success)
    assertion_pass_rate = mean(assertion_rates)
    security_gate = "fail" if critical else "pass"
    if len(items) >= 10:
        confidence = "verified"
    elif len(items) >= 3:
        confidence = "candidate"
    else:
        confidence = "exploratory"

    aggregate = (task_success * 0.55) + (assertion_pass_rate * 0.45)
    if security_gate == "fail":
        aggregate = 0.0

    raw = {
        "task_success": task_success,
        "assertion_pass_rate": assertion_pass_rate,
        "critical_policy_violations": critical,
        "denied_network_events": undeclared_network,
    }
    return ScoreResult(
        policy_version=policy.version,
        security_gate=security_gate,
        confidence=confidence,
        sample_count=len(items),
        raw_metrics=raw,
        aggregate_score=aggregate,
    )
