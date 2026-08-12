import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from skill_native.evidence import EvidenceStore, mark_evidence_captured
from skill_native.harness import (
    HarnessContractError,
    HarnessKernel,
    HarnessManifest,
    HarnessPlan,
    HarnessVerdict,
    HarnessVerdictStore,
    VerdictStatus,
    export_harness_schemas,
)
from skill_native.models import (
    AgentRef,
    EvidenceBundle,
    ModelRef,
    RunSpec,
    RuntimeRef,
    Scenario,
    SkillRef,
)
from skill_native.runtime import FakeRuntime


def make_spec() -> RunSpec:
    return RunSpec(
        run_id="harness-test",
        skill=SkillRef(
            source_url="https://example.test/skill",
            commit_or_digest="a" * 40,
            provenance_digest="b" * 64,
        ),
        agent=AgentRef(harness="codex", version="test"),
        model=ModelRef(provider="local", model="fixture", quota_class="local"),
        runtime=RuntimeRef(backend="fake", version="1", image_digest="sha256:fake"),
        scenario=Scenario(id="coding-smoke", task="Run the pinned Skill"),
    )


def manifest_payload() -> dict:
    return {
        "schema_version": "1.0",
        "identity": {
            "id": "coding.skill-smoke",
            "version": "0.1.0",
            "domain": "coding",
            "description": "Deterministic coding harness contract",
        },
        "licensing": {"code": "MIT"},
        "environment": {
            "allowed_runtimes": ["fake", "openshell"],
            "required_capabilities": [
                "network_deny_by_default",
                "filesystem_policy",
                "brokered_secrets",
            ],
            "network": "deny-by-default",
            "filesystem": "ephemeral",
            "secrets": "brokered",
        },
        "execution": {
            "adapter": "coding.command.v1",
            "command": ["skill", "run", "{entrypoint}"],
        },
        "evidence": {
            "capture": [
                "exit_code",
                "stdout",
                "stderr",
                "commands",
                "assertions",
                "runtime_metadata",
            ],
            "required": [
                "exit_code",
                "stdout",
                "stderr",
                "commands",
                "assertions",
                "runtime_metadata",
            ],
        },
        "verification": {
            "security_gate": "fail-on-high-or-critical",
            "checks": [
                {"id": "process-exited-cleanly", "kind": "exit_code_zero"},
                {
                    "id": "runtime-completed",
                    "kind": "assertion_true",
                    "assertion": "runtime_completed",
                },
                {
                    "id": "fake-output",
                    "kind": "stdout_contains",
                    "value": "fake runtime execution",
                },
                {"id": "stderr-empty", "kind": "stderr_empty"},
            ],
        },
        "budgets": {
            "timeout_seconds": 300,
            "max_model_calls": 20,
            "max_output_tokens": 20000,
            "max_network_requests": 100,
        },
        "replay": {"supported": False, "snapshot_required": False},
        "failure_taxonomy": ["environment_setup", "verification_failure"],
    }


def make_manifest() -> HarnessManifest:
    return HarnessManifest.model_validate(manifest_payload())


class HarnessKernelTests(unittest.TestCase):
    def test_compile_and_fake_run_are_digest_addressed(self):
        kernel = HarnessKernel()
        manifest = make_manifest()
        spec = make_spec()
        plan1 = kernel.compile(manifest, spec)
        plan2 = kernel.compile(manifest, spec)
        self.assertEqual(plan1.plan_digest, plan2.plan_digest)
        self.assertEqual(plan1.command, ["skill", "run", "SKILL.md"])
        self.assertEqual(plan1.run_spec.agent.harness, "codex")

        with tempfile.TemporaryDirectory() as td:
            result = kernel.run(
                manifest,
                spec,
                FakeRuntime(),
                evidence_store=EvidenceStore(Path(td) / "evidence"),
                verdict_store=HarnessVerdictStore(Path(td) / "verdicts"),
            )
            self.assertEqual(result.verdict.status, VerdictStatus.PASS)
            self.assertEqual(len(result.plan.plan_digest), 64)
            self.assertEqual(len(result.verdict.verdict_digest), 64)
            self.assertTrue(Path(result.evidence_path).is_file())
            self.assertTrue(Path(result.verdict_path).is_file())
            self.assertEqual(
                result.evidence.runtime_metadata["verification_state"],
                "deterministic-mock",
            )

    def test_missing_runtime_capability_fails_closed(self):
        raw = manifest_payload()
        raw["environment"]["required_capabilities"].append("kernel_or_vm_isolation")
        with self.assertRaises(HarnessContractError):
            HarnessKernel().compile(HarnessManifest.model_validate(raw), make_spec())

    def test_runtime_outside_allowlist_fails_closed(self):
        raw = manifest_payload()
        raw["environment"]["allowed_runtimes"] = ["openshell"]
        with self.assertRaises(HarnessContractError):
            HarnessKernel().compile(HarnessManifest.model_validate(raw), make_spec())

    def test_runtime_cannot_silently_ignore_declared_evidence(self):
        raw = manifest_payload()
        raw["evidence"]["capture"].append("network")
        raw["evidence"]["required"].append("network")
        raw["verification"]["checks"].append(
            {"id": "network-captured", "kind": "evidence_present", "evidence": "network"}
        )
        with self.assertRaises(HarnessContractError):
            HarnessKernel().compile(HarnessManifest.model_validate(raw), make_spec())

    def test_missing_mandatory_evidence_fails_verdict(self):
        kernel = HarnessKernel()
        manifest = make_manifest()
        plan = kernel.compile(manifest, make_spec())
        evidence = mark_evidence_captured(
            EvidenceBundle(
                run_id=plan.run_id,
                provenance_digest=plan.provenance_digest,
                exit_code=0,
                commands=[{"argv": ["true"]}],
                assertions={"runtime_completed": True},
                runtime_metadata={"backend": "fake"},
            ),
            ["exit_code", "commands", "assertions", "runtime_metadata"],
            runtime_backend="fake",
        )
        verdict = kernel.verify(manifest, plan, evidence)
        self.assertEqual(verdict.status, VerdictStatus.FAIL)
        self.assertIn("evidence:stdout", verdict.failed_check_ids)
        self.assertIn("evidence:stderr", verdict.failed_check_ids)

    def test_high_finding_is_non_compensable(self):
        kernel = HarnessKernel()
        manifest = make_manifest()
        plan = kernel.compile(manifest, make_spec())
        evidence = mark_evidence_captured(
            EvidenceBundle(
                run_id=plan.run_id,
                provenance_digest=plan.provenance_digest,
                exit_code=0,
                stdout="fake runtime execution\n",
                stderr="",
                commands=[{"argv": ["true"]}],
                assertions={"runtime_completed": True},
                runtime_metadata={"backend": "fake"},
                findings=[
                    {"rule": "fixture", "severity": "high", "evidence_id": "x" * 64}
                ],
            ),
            [kind.value for kind in manifest.evidence.required],
            runtime_backend="fake",
        )
        verdict = kernel.verify(manifest, plan, evidence)
        self.assertEqual(verdict.security_gate, "fail")
        self.assertEqual(verdict.status, VerdictStatus.FAIL)
        self.assertIn("security-gate", verdict.failed_check_ids)

    def test_unknown_verifier_evidence_and_reserved_ids_are_rejected(self):
        raw = manifest_payload()
        raw["verification"]["checks"][0]["kind"] = "llm_judge"
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(raw)

        raw = manifest_payload()
        raw["evidence"]["required"].append("unknown-trace")
        raw["evidence"]["capture"].append("unknown-trace")
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(raw)

        raw = manifest_payload()
        raw["verification"]["checks"][0]["id"] = "security-gate"
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(raw)

    def test_verifier_dependencies_must_be_mandatory_evidence(self):
        raw = manifest_payload()
        raw["evidence"]["required"].remove("stderr")
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(raw)

    def test_tampered_plan_digest_is_rejected(self):
        payload = HarnessKernel().compile(make_manifest(), make_spec()).model_dump(mode="json")
        payload["command"] = ["unexpected"]
        with self.assertRaises(ValidationError):
            HarnessPlan.model_validate(payload)

    def test_schema_export_matches_all_committed_contract_models(self):
        models = {
            "harness.schema.json": HarnessManifest,
            "harness-plan.schema.json": HarnessPlan,
            "harness-verdict.schema.json": HarnessVerdict,
        }
        committed = Path(__file__).resolve().parents[1] / "schemas"
        with tempfile.TemporaryDirectory() as td:
            paths = export_harness_schemas(Path(td))
            for name, model in models.items():
                generated = json.loads(paths[name].read_text(encoding="utf-8"))
                self.assertEqual(generated, model.model_json_schema())
                self.assertEqual(
                    generated,
                    json.loads((committed / name).read_text(encoding="utf-8")),
                )


if __name__ == "__main__":
    unittest.main()
