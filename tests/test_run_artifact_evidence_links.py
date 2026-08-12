import unittest

from skill_native.run_artifacts import (
    RunArtifactBuilder,
    RunArtifactError,
    build_evaluator_authority,
    canonical_digest,
)


RUN_ID = "run-artifact-link-fixture"
MANIFEST_DIGEST = "a" * 64
PROVENANCE_DIGEST = "b" * 64


def make_plan():
    payload = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "manifest_id": "coding.link-fixture",
        "manifest_version": "1.0.0",
        "manifest_digest": MANIFEST_DIGEST,
        "provenance_digest": PROVENANCE_DIGEST,
        "domain": "coding",
        "adapter": "coding.command.v1",
        "runtime_backend": "fake",
        "runtime_capabilities": {"snapshot_restore": False},
        "run_spec": {
            "run_id": RUN_ID,
            "skill": {
                "source_url": "https://example.test/skill",
                "commit_or_digest": "1" * 40,
                "entrypoint": "SKILL.md",
                "provenance_digest": PROVENANCE_DIGEST,
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
                "image_digest": "sha256:" + "c" * 64,
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


def make_evidence(commands=None):
    return {
        "run_id": RUN_ID,
        "provenance_digest": PROVENANCE_DIGEST,
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "commands": commands or [],
        "processes": [],
        "network": [],
        "filesystem_before": {},
        "filesystem_after": {},
        "inference": [],
        "assertions": {"runtime_completed": True},
        "findings": [],
        "runtime_metadata": {
            "runtime_backend": "fake",
            "evidence_contract": {
                "schema_version": "1.0",
                "captured": ["exit_code", "stderr", "runtime_metadata"],
            },
        },
        "policy": {},
        "ocsf_events": [],
        "coding_receipt": {},
        "agent_events": [],
        "workspace_diff": {},
        "test_results": [],
    }


def make_check(check_id, *, passed=True, evidence_ids=None):
    return {
        "id": check_id,
        "kind": "fixture",
        "passed": passed,
        "message": "fixture",
        "details": {},
        "evidence_ids": evidence_ids or [],
    }


def make_verdict(plan, evidence, *, checks=None, findings=None, security_gate="pass"):
    checks = checks or [make_check("security-gate", passed=security_gate == "pass")]
    failed = [check["id"] for check in checks if check["passed"] is not True]
    payload = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "manifest_digest": MANIFEST_DIGEST,
        "provenance_digest": PROVENANCE_DIGEST,
        "plan_digest": plan["plan_digest"],
        "evidence_digest": canonical_digest(evidence),
        "runtime_backend": "fake",
        "status": "fail" if failed else "pass",
        "security_gate": security_gate,
        "checks": checks,
        "failed_check_ids": failed,
        "security_findings": findings or [],
    }
    payload["verdict_digest"] = canonical_digest(payload)
    return payload


def make_authority(plan):
    return build_evaluator_authority(
        authority_id="skill-native.link-fixture",
        kind="repository",
        trust_basis="repository-pinned",
        source_url="https://github.com/ed3c/Skill.md-native",
        commit_or_digest="2" * 40,
        manifest_digest=plan["manifest_digest"],
        evaluator_digest="3" * 64,
    )


class EvidenceGraphLinkTests(unittest.TestCase):
    def test_duplicate_source_evidence_ids_are_rejected(self):
        plan = make_plan()
        duplicate_id = "e" * 64
        evidence = make_evidence(
            commands=[
                {"evidence_id": duplicate_id, "argv": ["true"]},
                {"evidence_id": duplicate_id, "argv": ["false"]},
            ]
        )
        verdict = make_verdict(plan, evidence)

        with self.assertRaisesRegex(RunArtifactError, "duplicate source evidence id"):
            RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

    def test_verifier_reference_to_unknown_evidence_is_rejected(self):
        plan = make_plan()
        evidence = make_evidence(
            commands=[{"evidence_id": "e" * 64, "argv": ["true"]}]
        )
        checks = [
            make_check("grounded-verifier", evidence_ids=["f" * 64]),
            make_check("security-gate"),
        ]
        verdict = make_verdict(plan, evidence, checks=checks)

        with self.assertRaisesRegex(RunArtifactError, "unknown source evidence id"):
            RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)

    def test_failed_run_preserves_unresolved_security_reference(self):
        plan = make_plan()
        evidence = make_evidence()
        checks = [make_check("security-gate", passed=False)]
        verdict = make_verdict(
            plan,
            evidence,
            checks=checks,
            findings=[
                {
                    "rule": "fixture",
                    "severity": "high",
                    "evidence_id": "f" * 64,
                }
            ],
            security_gate="fail",
        )

        bundle = RunArtifactBuilder().build(
            make_authority(plan), plan, evidence, verdict
        )
        self.assertFalse(bundle.scorecard.rank_eligible)
        self.assertTrue(
            any(
                node.kind == "unresolved_evidence_reference"
                for node in bundle.evidence_graph.nodes
            )
        )
        self.assertTrue(
            any(
                edge.relation == "references_missing"
                for edge in bundle.evidence_graph.edges
            )
        )

    def test_passing_run_cannot_hide_unresolved_finding_reference(self):
        plan = make_plan()
        evidence = make_evidence()
        verdict = make_verdict(
            plan,
            evidence,
            findings=[
                {
                    "rule": "fixture-low",
                    "severity": "low",
                    "evidence_id": "f" * 64,
                }
            ],
        )

        with self.assertRaisesRegex(RunArtifactError, "unknown source evidence id"):
            RunArtifactBuilder().build(make_authority(plan), plan, evidence, verdict)


if __name__ == "__main__":
    unittest.main()
