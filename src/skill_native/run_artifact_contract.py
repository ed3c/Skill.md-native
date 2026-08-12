from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .run_artifact_common import (
    EvaluatorAuthority,
    EvidenceGraph,
    RunArtifactError,
    _DIGEST_PATTERN,
    _SPAN_ID_PATTERN,
    _TRACE_ID_PATTERN,
    _StrictModel,
    _is_sha256_reference,
    _json_payload,
    canonical_digest,
)


class ReplayClass(str, Enum):
    EXACT = "exact"
    PARTIAL = "partial"
    NONE = "none"


class ReplayManifest(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    authority_digest: str = Field(pattern=_DIGEST_PATTERN)
    provenance_digest: str = Field(pattern=_DIGEST_PATTERN)
    policy_digest: str = Field(pattern=_DIGEST_PATTERN)
    command_digest: str = Field(pattern=_DIGEST_PATTERN)
    stdin_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    runtime_backend: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    runtime_image_digest: str = Field(min_length=1)
    snapshot_capable: bool
    snapshot_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    replay_class: ReplayClass
    reasons: list[str]
    replay_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_replay(self) -> "ReplayManifest":
        if self.reasons != sorted(set(self.reasons)):
            raise ValueError("replay reasons must be sorted and unique")
        if self.replay_class is ReplayClass.EXACT:
            if not self.snapshot_capable or self.snapshot_digest is None:
                raise ValueError("exact replay requires a captured snapshot and capability")
            if not _is_sha256_reference(self.runtime_image_digest):
                raise ValueError("exact replay requires an immutable runtime image digest")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"replay_digest"})
        )
        if expected != self.replay_digest:
            raise ValueError("replay digest does not match replay payload")
        return self


class TraceSpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class LogicalTraceSpan(_StrictModel):
    span_id: str = Field(pattern=_SPAN_ID_PATTERN)
    parent_span_id: str | None = Field(default=None, pattern=_SPAN_ID_PATTERN)
    name: str = Field(min_length=1)
    kind: Literal["internal"] = "internal"
    status: TraceSpanStatus
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_span_id(self) -> "LogicalTraceSpan":
        expected = canonical_digest(
            {
                "parent_span_id": self.parent_span_id,
                "name": self.name,
                "kind": self.kind,
                "status": self.status.value,
                "attributes": self.attributes,
            }
        )[:16]
        if expected != self.span_id:
            raise ValueError("logical span id does not match span payload")
        return self


class LogicalTrace(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    trace_id: str = Field(pattern=_TRACE_ID_PATTERN)
    timing_state: Literal["not-captured"] = "not-captured"
    semantic_convention_targets: list[str]
    spans: list[LogicalTraceSpan]
    trace_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_trace(self) -> "LogicalTrace":
        expected_trace_id = canonical_digest(["logical-trace", self.plan_digest])[:32]
        if self.trace_id != expected_trace_id:
            raise ValueError("logical trace id does not match the plan digest")
        span_ids = [span.span_id for span in self.spans]
        if len(span_ids) != len(set(span_ids)):
            raise ValueError("logical trace span ids must be unique")
        known = set(span_ids)
        if any(
            span.parent_span_id is not None and span.parent_span_id not in known
            for span in self.spans
        ):
            raise ValueError("logical trace contains an unknown parent span")
        if self.semantic_convention_targets != sorted(
            set(self.semantic_convention_targets)
        ):
            raise ValueError("semantic convention targets must be sorted and unique")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"trace_digest"})
        )
        if expected != self.trace_digest:
            raise ValueError("logical trace digest does not match trace payload")
        return self


class ScorecardTier(str, Enum):
    RANKABLE = "rankable"
    PROVISIONAL = "provisional"
    REJECTED = "rejected"


class OutcomeScorecard(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_version: Literal["evidence-first-v1"] = "evidence-first-v1"
    run_id: str = Field(min_length=1)
    authority_digest: str = Field(pattern=_DIGEST_PATTERN)
    plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    evidence_digest: str = Field(pattern=_DIGEST_PATTERN)
    verdict_digest: str = Field(pattern=_DIGEST_PATTERN)
    outcome_status: Literal["pass", "fail"]
    security_gate: Literal["pass", "fail"]
    mandatory_evidence_total: int = Field(ge=0)
    mandatory_evidence_captured: int = Field(ge=0)
    mandatory_evidence_coverage: float = Field(ge=0, le=1)
    verifier_total: int = Field(ge=0)
    verifier_passed: int = Field(ge=0)
    verifier_pass_rate: float = Field(ge=0, le=1)
    replay_class: ReplayClass
    rank_eligible: bool
    tier: ScorecardTier
    diagnostic_score: float = Field(ge=0, le=100)
    non_compensable_failures: list[str]
    confounders: dict[str, Any]
    scorecard_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_scorecard(self) -> "OutcomeScorecard":
        if self.mandatory_evidence_captured > self.mandatory_evidence_total:
            raise ValueError("captured mandatory evidence exceeds total")
        if self.verifier_passed > self.verifier_total:
            raise ValueError("passed verifier count exceeds total")
        if self.non_compensable_failures != sorted(
            set(self.non_compensable_failures)
        ):
            raise ValueError("non-compensable failures must be sorted and unique")
        eligible = (
            self.outcome_status == "pass"
            and self.security_gate == "pass"
            and self.mandatory_evidence_coverage == 1.0
            and self.verifier_pass_rate == 1.0
            and not self.non_compensable_failures
        )
        if self.rank_eligible != eligible:
            raise ValueError("rank eligibility does not match non-compensable policy")
        expected_tier = (
            ScorecardTier.RANKABLE
            if eligible
            else ScorecardTier.REJECTED
            if self.non_compensable_failures
            else ScorecardTier.PROVISIONAL
        )
        if self.tier is not expected_tier:
            raise ValueError("scorecard tier does not match scorecard state")
        expected_coverage = (
            1.0
            if self.mandatory_evidence_total == 0
            else self.mandatory_evidence_captured / self.mandatory_evidence_total
        )
        if self.mandatory_evidence_coverage != expected_coverage:
            raise ValueError("mandatory evidence coverage does not match evidence counts")
        expected_pass_rate = (
            1.0
            if self.verifier_total == 0
            else self.verifier_passed / self.verifier_total
        )
        if self.verifier_pass_rate != expected_pass_rate:
            raise ValueError("verifier pass rate does not match verifier counts")
        replay_points = {
            ReplayClass.EXACT: 10.0,
            ReplayClass.PARTIAL: 5.0,
            ReplayClass.NONE: 0.0,
        }[self.replay_class]
        expected_score = round(
            35.0 * self.mandatory_evidence_coverage
            + 35.0 * self.verifier_pass_rate
            + (20.0 if self.outcome_status == "pass" else 0.0)
            + replay_points,
            2,
        )
        if self.security_gate == "fail":
            expected_score = 0.0
        if self.diagnostic_score != expected_score:
            raise ValueError("diagnostic score does not match evidence-first-v1 policy")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"scorecard_digest"})
        )
        if expected != self.scorecard_digest:
            raise ValueError("scorecard digest does not match scorecard payload")
        return self


class RunArtifactBundle(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    authority: EvaluatorAuthority
    evidence_graph: EvidenceGraph
    replay_manifest: ReplayManifest
    logical_trace: LogicalTrace
    scorecard: OutcomeScorecard
    plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    evidence_digest: str = Field(pattern=_DIGEST_PATTERN)
    verdict_digest: str = Field(pattern=_DIGEST_PATTERN)
    bundle_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_bundle(self) -> "RunArtifactBundle":
        run_ids = {
            self.run_id,
            self.evidence_graph.run_id,
            self.replay_manifest.run_id,
            self.logical_trace.run_id,
            self.scorecard.run_id,
        }
        if len(run_ids) != 1:
            raise ValueError("run artifact bundle contains multiple run ids")
        if self.authority.authority_digest != self.scorecard.authority_digest:
            raise ValueError("scorecard authority digest does not match authority")
        if not (
            self.plan_digest == self.replay_manifest.plan_digest
            == self.logical_trace.plan_digest
            == self.scorecard.plan_digest
        ):
            raise ValueError("bundle plan digest continuity failed")
        if self.evidence_digest != self.scorecard.evidence_digest:
            raise ValueError("bundle evidence digest continuity failed")
        if self.verdict_digest != self.scorecard.verdict_digest:
            raise ValueError("bundle verdict digest continuity failed")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"bundle_digest"})
        )
        if expected != self.bundle_digest:
            raise ValueError("bundle digest does not match bundle payload")
        return self


@dataclass(frozen=True)
class RunArtifactStore:
    root: Path

    def persist(self, bundle: RunArtifactBundle) -> tuple[str, Path]:
        digest = bundle.bundle_digest
        directory = self.root / digest
        directory.mkdir(parents=True, exist_ok=True)
        artifacts: dict[str, BaseModel] = {
            "authority.json": bundle.authority,
            "evidence-graph.json": bundle.evidence_graph,
            "replay-manifest.json": bundle.replay_manifest,
            "logical-trace.json": bundle.logical_trace,
            "outcome-scorecard.json": bundle.scorecard,
            "run-artifact-bundle.json": bundle,
        }
        for name, artifact in artifacts.items():
            path = directory / name
            encoded = json.dumps(
                artifact.model_dump(mode="json"),
                sort_keys=True,
                indent=2,
            ) + "\n"
            if path.exists() and path.read_text(encoding="utf-8") != encoded:
                raise RunArtifactError(f"content-addressed artifact collision: {path}")
            path.write_text(encoded, encoding="utf-8")
        return digest, directory / "run-artifact-bundle.json"


def export_run_artifact_schemas(output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    schemas = {
        "evaluator-authority.schema.json": EvaluatorAuthority.model_json_schema(),
        "evidence-graph.schema.json": EvidenceGraph.model_json_schema(),
        "replay-manifest.schema.json": ReplayManifest.model_json_schema(),
        "logical-trace.schema.json": LogicalTrace.model_json_schema(),
        "outcome-scorecard.schema.json": OutcomeScorecard.model_json_schema(),
        "run-artifact-bundle.schema.json": RunArtifactBundle.model_json_schema(),
    }
    result: dict[str, Path] = {}
    for name, schema in schemas.items():
        path = output / name
        path.write_text(
            json.dumps(schema, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        result[name] = path
    return result
