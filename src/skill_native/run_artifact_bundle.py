from __future__ import annotations

from typing import Any

from pydantic import model_validator

from .run_artifact_common import canonical_digest
from .run_artifact_contract import RunArtifactBundle as BaseRunArtifactBundle


class RunArtifactBundle(BaseRunArtifactBundle):
    """Cross-artifact continuity checks layered over each artifact's self-digest.

    A digest is not a signature: an attacker can modify a nested artifact and recompute
    that artifact's digest. This validator ensures independently valid nested artifacts
    still describe the same authority, plan, evidence, verdict, runtime, and replay state.
    """

    @model_validator(mode="after")
    def validate_cross_artifact_continuity(self) -> "RunArtifactBundle":
        authority_digest = self.authority.authority_digest
        if self.replay_manifest.authority_digest != authority_digest:
            raise ValueError("replay authority digest does not match bundle authority")
        if self.scorecard.replay_class is not self.replay_manifest.replay_class:
            raise ValueError("scorecard replay class does not match replay manifest")

        runtime = {
            "backend": self.replay_manifest.runtime_backend,
            "version": self.replay_manifest.runtime_version,
            "image_digest": self.replay_manifest.runtime_image_digest,
        }
        if self.scorecard.confounders.get("runtime") != runtime:
            raise ValueError("scorecard runtime confounder does not match replay manifest")

        required_graph_nodes = {
            ("evaluator_authority", authority_digest),
            ("harness_plan", self.plan_digest),
            ("skill_provenance", self.replay_manifest.provenance_digest),
            ("evidence_bundle", self.evidence_digest),
            ("harness_verdict", self.verdict_digest),
            ("runtime", canonical_digest(runtime)),
        }
        observed_graph_nodes = {
            (node.kind, node.payload_digest) for node in self.evidence_graph.nodes
        }
        missing_graph_nodes = required_graph_nodes - observed_graph_nodes
        if missing_graph_nodes:
            raise ValueError(
                "evidence graph is missing bundle continuity nodes: "
                + ", ".join(
                    f"{kind}:{digest}" for kind, digest in sorted(missing_graph_nodes)
                )
            )

        trace_attributes: list[dict[str, Any]] = [
            span.attributes for span in self.logical_trace.spans
        ]
        required_trace_attributes = {
            "skill.native.authority_digest": authority_digest,
            "skill.native.plan_digest": self.plan_digest,
            "skill.native.evidence_digest": self.evidence_digest,
            "skill.native.verdict_digest": self.verdict_digest,
        }
        missing_trace_attributes = [
            key
            for key, value in required_trace_attributes.items()
            if not any(attributes.get(key) == value for attributes in trace_attributes)
        ]
        if missing_trace_attributes:
            raise ValueError(
                "logical trace is missing bundle continuity attributes: "
                + ", ".join(sorted(missing_trace_attributes))
            )
        return self
