from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean, median
from typing import Iterable

from .models import EvidenceBundle
from .security import evaluate_security


@dataclass(frozen=True)
class ScorePolicy:
    version: str = "v0.2"
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


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return float(ordered[index])


def score_evidence(runs: Iterable[EvidenceBundle], policy: ScorePolicy | None = None) -> ScoreResult:
    policy = policy or ScorePolicy()
    items = list(runs)
    if not items:
        raise ValueError("at least one evidence bundle is required")

    evaluations = [evaluate_security(run) for run in items]
    all_findings = [finding for evaluation in evaluations for finding in evaluation.findings]
    critical = sum(1 for finding in all_findings if _severity(finding) in policy.critical_finding_severities)

    assertion_rates: list[float] = []
    exit_success: list[float] = []
    signatures: list[tuple] = []
    denied_network = 0
    latencies: list[float] = []
    input_tokens = 0
    output_tokens = 0
    estimated_cost = 0.0
    recovery_values: list[float] = []

    for run, evaluation in zip(items, evaluations):
        values = list(run.assertions.values())
        assertion_rate = sum(bool(v) for v in values) / len(values) if values else 0.0
        assertion_rates.append(assertion_rate)
        exit_ok = 1.0 if run.exit_code == 0 else 0.0
        exit_success.append(exit_ok)
        signatures.append((run.exit_code, tuple(sorted(run.assertions.items())), evaluation.security_gate))
        denied_network += sum(
            1
            for event in run.network
            if str(event.get("action", event.get("action_name", ""))).lower() == "denied"
        )
        for receipt in run.inference:
            latencies.append(float(receipt.latency_ms))
            input_tokens += int(receipt.input_tokens)
            output_tokens += int(receipt.output_tokens)
            estimated_cost += float(receipt.price_usd)
        if "recovery_success" in run.assertions:
            recovery_values.append(1.0 if run.assertions["recovery_success"] else 0.0)

    task_success = mean(exit_success)
    assertion_pass_rate = mean(assertion_rates)
    most_common_signature = Counter(signatures).most_common(1)[0][1]
    reproducibility_rate = most_common_signature / len(signatures)
    least_privilege = 1.0 if denied_network == 0 and critical == 0 else 0.0
    recovery_success = mean(recovery_values) if recovery_values else 0.0
    security_gate = "fail" if critical else "pass"

    if len(items) >= 10:
        confidence = "verified"
    elif len(items) >= 3:
        confidence = "candidate"
    else:
        confidence = "exploratory"

    # Correctness remains the base score. Security is a non-compensable gate;
    # other dimensions are preserved raw until a versioned weighting policy is adopted.
    aggregate = (task_success * 0.55) + (assertion_pass_rate * 0.45)
    if security_gate == "fail":
        aggregate = 0.0

    raw = {
        "task_success": task_success,
        "assertion_pass_rate": assertion_pass_rate,
        "reproducibility_rate": reproducibility_rate,
        "least_privilege": least_privilege,
        "critical_policy_violations": critical,
        "denied_network_events": denied_network,
        "latency_ms_p50": float(median(latencies)) if latencies else 0.0,
        "latency_ms_p95": _percentile(latencies, 0.95),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "token_efficiency_output_per_success": output_tokens / max(1.0, sum(exit_success)),
        "estimated_cost_usd": estimated_cost,
        "recovery_success": recovery_success,
    }
    return ScoreResult(
        policy_version=policy.version,
        security_gate=security_gate,
        confidence=confidence,
        sample_count=len(items),
        raw_metrics=raw,
        aggregate_score=aggregate,
    )
