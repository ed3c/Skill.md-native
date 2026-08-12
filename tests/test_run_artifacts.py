import copy
import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from skill_native.run_artifacts import (
    EvaluatorAuthority,
    ReplayClass,
    RunArtifactBuilder,
    RunArtifactError,
    RunArtifactBundle,
    RunArtifactStore,
    build_evaluator_authority,
    canonical_digest,
    export_run_artifact_schemas,
)


def make_plan(*, snapshot_restore=False, image_digest=None):
    image_digest = image_digest or ("sha256:" + "c" * 64)
    payload = {
        "schema_version": "1.0",
        "run_id": "run-artifacts-fixture",
        "manifest_id": "coding.fixture",
        "manifest_version": "1.0.0",
        "manifest_digest": "a" * 64,
        "provenance_digest": "b" * 64,
        "domain": "coding",
        "adapter": "coding.command.v1",
        "runtime_backend": "fake",
        "runtime_capabilities": {
            "snapshot_restore": snapshot_restore,
            "network_deny_by_default": True,
        },
        "run_spec": {
            "run_id": "run-artifacts-fixture",
            "skill": {
                "source_url": "https://example.test/skill",
                "commit_or_digest": "1" * 40,
                "entrypoint": "SKILL.md",
                "provenance_digest": "b" * 64,
            },
            "agent": {"harness": "fixture", "version": "1.0.0"},
            "model": {
                "provider": "local",
                "model": "no-model",
                "quota_class": "local",
            },
            "runtime": {
                "backend": "fake",
                "version": "1.0.0",
                "image_digest": image_digest,
            },
            "policy": {
                "network": "deny-by-default",
                "filesystem": "ephemeral",
                "secrets": "brokered",
            },
            "scenario": {"id": "fixture", "task": "private task"},
            "limits": {
                "timeout_seconds": 60,
                "max_model_calls": 0,
                "max_output_tokens": 0,
                "max_network_requests": 0,
            },
        },
        "command": ["true"],
        "stdin_digest": None,
        "required_evidence": ["exit_code", "stderr", "runtime_metadata"],
        "checks": [],
        "policy_digest": "d" * 64,
        "effective_limits": {
            "timeout_seconds": 60,
            "max_model_calls": 0,
            "max_output_tokens": 0,
            "max_network_requests": 0,
        },
    }
    payload["plan_digest"] = canonical_digest(payload)
    return payload


def make_evidence(*, captured=None, snapshot_digest=None):
    captured = captured or ["exit_code", "stderr", "runtime_metadata"]
    metadata = {
        "runtime_backend": "fake",
        "evidence_contract": {"schema_version": "1.0", "captured": captured},
    }
    if snapshot_digest is not None:
        metadata["snapshot_digest"] = snapshot_digest
    return {
        "run_id": "run-artifacts-fixture",
        "provenance_digest": "b" * 64,
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "commands": [{"requested_argv": ["true"], "exit_code": 0}],
        "processes": [],
        "network": [],
        "filesystem_before": {},
        "filesystem_after": {},
        "inference": [],
        "assertions": {"runtime_completed": True},
        "findings": [],
        "runtime_metadata": metadata,
        "policy": {},
        "ocsf_events": [],
        "coding_receipt": {},
        "agent_events": [],
        "workspace_diff": {},
        "test_results": [],
    }


def make_verdict(plan, evidence, *, security_gate="pass", status="pass"):
    checks = [
        {
            "id": "provenance-continuity",
            "kind": "provenance",
            "passed": True,
            "message": "ok",
            "details": {},
            "evidence_ids": [],
        },
        {
            "id": "runtime-continuity",
            "kind": "runtime",
            "passed": True,
            "message": "ok",
            "details": {},
            "evidence_ids": [],
        },
        {
            "id": "security-gate",
            "kind": "security_gate",
            "passed": security_gate == "pass",
            "message": "ok" if security_gate == "pass" else "failed",
            "details": {},
            "evidence_ids": [],
        },
    ]
    failed = [check["id"] for check in checks if not check["passed"]]
    payload = {
        "schema_version": "1.0",
        "run_id": plan["run_id"],
        "manifest_digest": plan["manifest_digest"],
        "provenance_digest": plan["provenance_digest"],
        "plan_digest": plan["plan_digest"],
        "evidence_digest": canonical_digest(evidence),
        "runtime_backend": plan["runtime_backend"],
        "status": status,
        "security_gate": security_gate,
        "checks": checks,
        "failed_check_ids": failed,
        "security_findings": (
            []
            if security_gate == "pass"
            else [{"rule": "fixture", "severity": "high", "evidence_id": "e" * 64}]
        ),
    }
    payload["verdict_digest"] = canonical_digest(payload)
    return payload


def make_authority(plan):
    return build_evaluator_authority(
        authority_id="skill-native.fixture-evaluator",
        kind="repository",
        trust_basis="repository-pinned",
        source_url="https://github.com/ed3c/Skill.md-native",
        commit_or_digest="2" * 40,
        manifest_digest=plan["manifest_digest"],
        evaluator_digest="3" * 64,
    )


class RunArtifactBuilderTests(unittest.TestCase):
    def test_deterministic_bundle_and_graph_integrity(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        authority = make_authority(plan)
        builder = RunArtifactBuilder()

        first = builder.build(authority, plan, evidence, verdict)
        second = builder.build(authority, plan, evidence, verdict)

        self.assertEqual(first.bundle_digest, second.bundle_digest)
        self.assertEqual(first.evidence_graph.graph_digest, second.evidence_graph.graph_digest)
        self.assertTrue(first.scorecard.rank_eligible)
        self.assertEqual(first.scorecard.mandatory_evidence_coverage, 1.0)
        node_ids = {node.id for node in first.evidence_graph.nodes}
        self.assertTrue(node_ids)
        self.assertTrue(
            all(
                edge.source in node_ids and edge.target in node_ids
                for edge in first.evidence_graph.edges
            )
        )
        round_trip = RunArtifactBundle.model_validate_json(first.model_dump_json())
        self.assertEqual(round_trip.bundle_digest, first.bundle_digest)

    def test_mutable_authority_and_manifest_mismatch_are_rejected(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        raw = make_authority(plan).model_dump(mode="json")
        raw["commit_or_digest"] = "main"
        raw["authority_digest"] = canonical_digest(
            {key: value for key, value in raw.items() if key != "authority_digest"}
        )
        with self.assertRaises(ValidationError):
            EvaluatorAuthority.model_validate(raw)

        authority = make_authority(plan).model_copy(
            update={"manifest_digest": "f" * 64}
        )
        raw_authority = authority.model_dump(mode="json")
        raw_authority["authority_digest"] = canonical_digest(
            {
                key: value
                for key, value in raw_authority.items()
                if key != "authority_digest"
            }
        )
        with self.assertRaises(RunArtifactError):
            RunArtifactBuilder().build(raw_authority, plan, evidence, verdict)

    def test_tampered_plan_and_verdict_are_rejected(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        authority = make_authority(plan)

        tampered_plan = copy.deepcopy(plan)
        tampered_plan["command"] = ["false"]
        with self.assertRaises(RunArtifactError):
            RunArtifactBuilder().build(authority, tampered_plan, evidence, verdict)

        tampered_verdict = copy.deepcopy(verdict)
        tampered_verdict["status"] = "fail"
        with self.assertRaises(RunArtifactError):
            RunArtifactBuilder().build(authority, plan, evidence, tampered_verdict)

    def test_missing_attestation_is_non_compensable(self):
        plan = make_plan()
        evidence = make_evidence(captured=["exit_code", "runtime_metadata"])
        verdict = make_verdict(plan, evidence)
        bundle = RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

        self.assertFalse(bundle.scorecard.rank_eligible)
        self.assertEqual(bundle.scorecard.tier.value, "rejected")
        self.assertIn(
            "missing-evidence:stderr",
            bundle.scorecard.non_compensable_failures,
        )
        self.assertLess(bundle.scorecard.mandatory_evidence_coverage, 1.0)

    def test_security_failure_forces_zero_score(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(
            plan,
            evidence,
            security_gate="fail",
            status="fail",
        )
        bundle = RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

        self.assertFalse(bundle.scorecard.rank_eligible)
        self.assertEqual(bundle.scorecard.diagnostic_score, 0.0)
        self.assertIn(
            "high-or-critical-security-finding",
            bundle.scorecard.non_compensable_failures,
        )

    def test_exact_replay_requires_snapshot_and_sha256_image(self):
        snapshot = "4" * 64
        plan = make_plan(snapshot_restore=True)
        evidence = make_evidence(snapshot_digest=snapshot)
        verdict = make_verdict(plan, evidence)
        exact = RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)
        self.assertEqual(exact.replay_manifest.replay_class, ReplayClass.EXACT)

        no_snapshot_evidence = make_evidence()
        no_snapshot_verdict = make_verdict(plan, no_snapshot_evidence)
        partial = RunArtifactBuilder().build(
            make_authority(plan), plan, no_snapshot_evidence, no_snapshot_verdict
        )
        self.assertEqual(partial.replay_manifest.replay_class, ReplayClass.PARTIAL)

        weak_plan = make_plan(snapshot_restore=True, image_digest="sha256:fixture")
        weak_evidence = make_evidence(snapshot_digest=snapshot)
        weak_verdict = make_verdict(weak_plan, weak_evidence)
        weak = RunArtifactBuilder().build(
            make_authority(weak_plan), weak_plan, weak_evidence, weak_verdict
        )
        self.assertNotEqual(weak.replay_manifest.replay_class, ReplayClass.EXACT)

    def test_logical_trace_does_not_fabricate_timing(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        bundle = RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)
        payload = bundle.logical_trace.model_dump(mode="json")
        encoded = json.dumps(payload).lower()
        self.assertEqual(payload["timing_state"], "not-captured")
        for forbidden in (
            '"start_time"',
            '"end_time"',
            '"timestamp"',
            '"duration_ms"',
        ):
            self.assertNotIn(forbidden, encoded)

    def test_severe_finding_cannot_hide_behind_passing_security_gate(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        verdict["security_findings"] = [
            {"rule": "fixture", "severity": "Critical", "evidence_id": "e" * 64}
        ]
        verdict["verdict_digest"] = canonical_digest(
            {key: value for key, value in verdict.items() if key != "verdict_digest"}
        )
        with self.assertRaises(RunArtifactError):
            RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

    def test_nested_artifact_tampering_is_rejected_after_round_trip(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        bundle = RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)
        raw = bundle.model_dump(mode="json")
        raw["logical_trace"]["trace_id"] = "0" * 32
        with self.assertRaises(ValidationError):
            RunArtifactBundle.model_validate(raw)

        raw = bundle.model_dump(mode="json")
        raw["scorecard"]["diagnostic_score"] = 99.0
        raw["scorecard"]["scorecard_digest"] = canonical_digest(
            {
                key: value
                for key, value in raw["scorecard"].items()
                if key != "scorecard_digest"
            }
        )
        with self.assertRaises(ValidationError):
            RunArtifactBundle.model_validate(raw)

    def test_store_and_schema_export_are_content_addressed(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(plan, evidence)
        bundle = RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            digest, bundle_path = RunArtifactStore(root / "artifacts").persist(bundle)
            self.assertEqual(digest, bundle.bundle_digest)
            self.assertTrue(bundle_path.is_file())
            self.assertEqual(len(list(bundle_path.parent.glob("*.json"))), 6)
            schemas = export_run_artifact_schemas(root / "schemas")
            self.assertEqual(len(schemas), 6)
            self.assertTrue(all(path.is_file() for path in schemas.values()))


if __name__ == "__main__":
    unittest.main()
