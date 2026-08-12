import unittest

from pydantic import ValidationError

from skill_native.run_artifacts import (
    RunArtifactBuilder,
    RunArtifactBundle,
    RunArtifactError,
    canonical_digest,
)
from tests.test_run_artifacts import (
    make_authority,
    make_evidence,
    make_plan,
    make_verdict,
)


def _redigest(payload, field):
    payload[field] = canonical_digest(
        {key: value for key, value in payload.items() if key != field}
    )


class RunArtifactBundleContinuityTests(unittest.TestCase):
    def make_bundle(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        return RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

    def test_rehashed_replay_authority_substitution_is_rejected(self):
        raw = self.make_bundle().model_dump(mode="json")
        raw["replay_manifest"]["authority_digest"] = "f" * 64
        _redigest(raw["replay_manifest"], "replay_digest")
        _redigest(raw, "bundle_digest")
        with self.assertRaises(ValidationError):
            RunArtifactBundle.model_validate(raw)

    def test_rehashed_graph_missing_evidence_node_is_rejected(self):
        raw = self.make_bundle().model_dump(mode="json")
        evidence_nodes = {
            node["id"]
            for node in raw["evidence_graph"]["nodes"]
            if node["kind"] == "evidence_bundle"
        }
        raw["evidence_graph"]["nodes"] = [
            node
            for node in raw["evidence_graph"]["nodes"]
            if node["id"] not in evidence_nodes
        ]
        raw["evidence_graph"]["edges"] = [
            edge
            for edge in raw["evidence_graph"]["edges"]
            if edge["source"] not in evidence_nodes
            and edge["target"] not in evidence_nodes
        ]
        _redigest(raw["evidence_graph"], "graph_digest")
        _redigest(raw, "bundle_digest")
        with self.assertRaises(ValidationError):
            RunArtifactBundle.model_validate(raw)

    def test_duplicate_source_evidence_ids_are_rejected(self):
        plan = make_plan()
        evidence = make_evidence()
        duplicate = "duplicate-evidence-id"
        evidence["commands"] = [
            {"evidence_id": duplicate, "requested_argv": ["true"], "exit_code": 0},
            {"evidence_id": duplicate, "requested_argv": ["true"], "exit_code": 0},
        ]
        verdict = make_verdict(plan, evidence)
        with self.assertRaises(RunArtifactError):
            RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

    def test_verifier_reference_to_unknown_evidence_is_rejected(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        verdict["checks"][0]["evidence_ids"] = ["missing-evidence-id"]
        _redigest(verdict, "verdict_digest")
        with self.assertRaises(RunArtifactError):
            RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

    def test_passing_verdict_cannot_reference_unknown_finding_evidence(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        verdict["security_findings"] = [
            {
                "rule": "fixture-low",
                "severity": "low",
                "evidence_id": "missing-finding-evidence",
            }
        ]
        _redigest(verdict, "verdict_digest")
        with self.assertRaises(RunArtifactError):
            RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

    def test_failed_verdict_preserves_unresolved_finding_reference(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(
            plan,
            evidence,
            security_gate="fail",
            status="fail",
        )
        bundle = RunArtifactBuilder().build(
            make_authority(plan), plan, evidence, verdict
        )
        unresolved = [
            node
            for node in bundle.evidence_graph.nodes
            if node.kind == "unresolved_evidence_reference"
        ]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(
            unresolved[0].attributes["source_evidence_id"],
            "e" * 64,
        )

    def test_rehashed_trace_without_evidence_continuity_is_rejected(self):
        raw = self.make_bundle().model_dump(mode="json")
        for span in raw["logical_trace"]["spans"]:
            if "skill.native.evidence_digest" not in span["attributes"]:
                continue
            span["attributes"]["skill.native.evidence_digest"] = "e" * 64
            span["span_id"] = canonical_digest(
                {
                    "parent_span_id": span["parent_span_id"],
                    "name": span["name"],
                    "kind": span["kind"],
                    "status": span["status"],
                    "attributes": span["attributes"],
                }
            )[:16]
        # Rebuild descendants because parent span IDs are content-derived.
        previous = None
        for span in raw["logical_trace"]["spans"]:
            span["parent_span_id"] = previous
            span["span_id"] = canonical_digest(
                {
                    "parent_span_id": span["parent_span_id"],
                    "name": span["name"],
                    "kind": span["kind"],
                    "status": span["status"],
                    "attributes": span["attributes"],
                }
            )[:16]
            previous = span["span_id"]
        _redigest(raw["logical_trace"], "trace_digest")
        _redigest(raw, "bundle_digest")
        with self.assertRaises(ValidationError):
            RunArtifactBundle.model_validate(raw)


if __name__ == "__main__":
    unittest.main()
