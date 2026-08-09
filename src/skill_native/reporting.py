from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from math import sqrt
from typing import Iterable

from .compatibility import CompatibilityKey, aggregate_matrix
from .models import EvidenceBundle


@dataclass(frozen=True)
class VerificationPolicy:
    min_samples_per_cell: int = 3
    min_agents: int = 2
    min_runtimes: int = 2
    min_models: int = 2


@dataclass(frozen=True)
class Coverage:
    agents: int
    runtimes: int
    models: int
    cells: int
    verified_cells: int
    verified: bool


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 1.0
    p = successes / total
    denom = 1 + (z * z / total)
    centre = (p + z * z / (2 * total)) / denom
    margin = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def build_report(
    rows: Iterable[tuple[CompatibilityKey, EvidenceBundle]],
    policy: VerificationPolicy | None = None,
) -> dict:
    policy = policy or VerificationPolicy()
    items = list(rows)
    cells = aggregate_matrix(items)
    grouped: dict[CompatibilityKey, list[EvidenceBundle]] = {}
    for key, evidence in items:
        grouped.setdefault(key, []).append(evidence)

    agents = {c.key.agent for c in cells}
    runtimes = {c.key.runtime for c in cells}
    models = {c.key.model for c in cells}
    verified_cells = sum(1 for c in cells if c.score.sample_count >= policy.min_samples_per_cell and c.score.security_gate == "pass")
    coverage = Coverage(
        agents=len(agents), runtimes=len(runtimes), models=len(models), cells=len(cells), verified_cells=verified_cells,
        verified=(
            len(agents) >= policy.min_agents
            and len(runtimes) >= policy.min_runtimes
            and len(models) >= policy.min_models
            and verified_cells == len(cells)
            and len(cells) > 0
        ),
    )

    output_cells = []
    for cell in cells:
        runs = grouped[cell.key]
        assertion_successes = sum(sum(1 for v in r.assertions.values() if v) for r in runs)
        assertion_total = sum(len(r.assertions) for r in runs)
        reproducible_successes = round(float(cell.score.raw_metrics.get("reproducibility_rate", 0.0)) * len(runs))
        assertion_ci = wilson(assertion_successes, assertion_total)
        reproducibility_ci = wilson(reproducible_successes, len(runs))
        output_cells.append({
            "key": asdict(cell.key),
            "score": asdict(cell.score),
            "uncertainty": {
                "assertion_pass_ci95": list(assertion_ci),
                "reproducibility_ci95": list(reproducibility_ci),
            },
        })

    return {
        "schema_version": "report-v1",
        "verification_policy": asdict(policy),
        "coverage": asdict(coverage),
        "cells": output_cells,
    }


def serve_report(report: dict, host: str = "127.0.0.1", port: int = 8790) -> None:
    payload = json.dumps(report, sort_keys=True).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in {"/", "/v1/report"}:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers(); self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
