from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import EvidenceBundle
from .scoring import ScoreResult, score_evidence


@dataclass(frozen=True)
class CompatibilityKey:
    skill_digest: str
    agent: str
    runtime: str
    model: str


@dataclass(frozen=True)
class CompatibilityCell:
    key: CompatibilityKey
    score: ScoreResult


def aggregate_matrix(rows: Iterable[tuple[CompatibilityKey, EvidenceBundle]]) -> list[CompatibilityCell]:
    grouped: dict[CompatibilityKey, list[EvidenceBundle]] = defaultdict(list)
    for key, evidence in rows:
        grouped[key].append(evidence)
    return [
        CompatibilityCell(key=key, score=score_evidence(grouped[key]))
        for key in sorted(grouped, key=lambda k: (k.skill_digest, k.agent, k.runtime, k.model))
    ]
