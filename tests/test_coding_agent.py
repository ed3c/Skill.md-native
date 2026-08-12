import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from skill_native.coding_agent import (
    build_runner_config,
    encode_runner_config,
    execute_coding_agent,
    parse_coding_receipt,
)
from skill_native.coding_contract import CodingAgentContract, CodingAgentReceipt
from skill_native.evidence import mark_evidence_captured
from skill_native.harness_contract import HarnessContractError, HarnessManifest, VerdictStatus
from skill_native.harness_kernel import HarnessKernel
from skill_native.models import (
    AgentRef,
    EvidenceBundle,
    Limits,
    ModelRef,
    RunSpec,
    RuntimeBackend,
    RuntimeRef,
    Scenario,
    SkillRef,
)
from skill_native.runtime import RuntimeAdapter, RuntimeCapabilities


FIXTURE_AGENT = '''
import hashlib
import json
import pathlib
import sys

if "--version" in sys.argv:
    print("fixture-agent 1.0.0")
    raise SystemExit(0)

task = sys.stdin.read()
pathlib.Path("target.txt").write_text("done\\n", encoding="utf-8")
print(json.dumps({
    "type": "task.completed",
    "status": "ok",
    "message": task,
    "task_digest": hashlib.sha256(task.encode()).hexdigest(),
}))
'''


class LocalCodingFixtureRuntime(RuntimeAdapter):
    backend = RuntimeBackend.FAKE
    evidence_kinds = frozenset(
        {"exit_code", "stdout", "stderr", "commands", "assertions", "runtime_metadata"}
    )
    capabilities = RuntimeCapabilities(
        kernel_or_vm_isolation=False,
        network_deny_by_default=True,
        l7_http_policy=False,
        filesystem_policy=True,
        brokered_secrets=True,
        process_telemetry=False,
        snapshot_restore=False,
        persistent_filesystem=False,
        gpu=False,
        network_telemetry=False,
        stdin_stream=True,
    )

    def __init__(self, root: Path, *, tamper_receipt: bool = False):
        self.root = root
        self.tamper_receipt = tamper_receipt
        self.records = {}
        self.spec = None

    def prepare(self, spec):
        self.spec = spec
        return f"fixture:{spec.run_id}"

    def execute(self, sandbox_id, command, *, stdin=None):
        if command[0] != "skill-native-coding-runner":
            raise AssertionError(command)
        actual = [sys.executable, "-m", "skill_native.coding_agent", *command[1:]]
        result = subprocess.run(
            actual,
            cwd=self.root,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])},
        )
        stdout = result.stdout
        if self.tamper_receipt and stdout.strip():
            raw = json.loads(stdout)
            raw["outcome"] = "fail" if raw["outcome"] == "pass" else "pass"
            stdout = json.dumps(raw)
        execution_id = f"{sandbox_id}:exec:0"
        self.records[execution_id] = {
            "result": result,
            "stdout": stdout,
            "requested_argv": list(command),
            "stdin_digest": (
                hashlib.sha256(stdin.encode("utf-8")).hexdigest()
                if stdin is not None
                else None
            ),
        }
        return execution_id

    def collect(self, run_id, execution_id):
        record = self.records[execution_id]
        result = record["result"]
        bundle = EvidenceBundle(
            run_id=run_id,
            provenance_digest=self.spec.skill.provenance_digest,
            exit_code=result.returncode,
            stdout=record["stdout"],
            stderr=result.stderr,
            commands=[
                {
                    "execution_id": execution_id,
                    "requested_argv": record["requested_argv"],
                    "stdin_digest": record["stdin_digest"],
                    "exit_code": result.returncode,
                }
            ],
            assertions={"runtime_completed": True},
            runtime_metadata={"verification_state": "deterministic-fixture"},
        )
        return mark_evidence_captured(
            bundle,
            self.evidence_kinds,
            runtime_backend="fake",
        )

    def destroy(self, sandbox_id):
        return None


def contract(**overrides):
    values = {
        "driver": "generic",
        "driver_version": "1.0.0",
        "version_command": ["python3", "fixture_agent.py", "--version"],
        "test_commands": [
            [
                "python3",
                "-c",
                "from pathlib import Path; assert Path('target.txt').read_text() == 'done\\n'",
            ]
        ],
        "allowed_change_globs": ["target.txt"],
    }
    values.update(overrides)
    return CodingAgentContract.model_validate(values)


def manifest_payload(**coding_overrides):
    coding = contract(**coding_overrides).model_dump(mode="json")
    return {
        "schema_version": "1.0",
        "identity": {
            "id": "coding.agent-fixture",
            "version": "0.1.0",
            "domain": "coding",
        },
        "licensing": {"code": "MIT"},
        "environment": {
            "allowed_runtimes": ["fake"],
            "required_capabilities": [
                "network_deny_by_default",
                "filesystem_policy",
                "brokered_secrets",
                "stdin_stream",
            ],
            "network": "deny-by-default",
            "filesystem": "ephemeral",
            "secrets": "brokered",
        },
        "execution": {
            "adapter": "coding.agent.v1",
            "command": ["python3", "{entrypoint}"],
        },
        "coding": coding,
        "evidence": {
            "capture": [
                "exit_code",
                "stdout",
                "stderr",
                "commands",
                "assertions",
                "runtime_metadata",
                "coding_receipt",
                "agent_events",
                "workspace_diff",
                "test_results",
            ],
            "required": [
                "exit_code",
                "stdout",
                "stderr",
                "commands",
                "assertions",
                "runtime_metadata",
                "coding_receipt",
                "agent_events",
                "workspace_diff",
                "test_results",
            ],
        },
        "verification": {
            "security_gate": "fail-on-high-or-critical",
            "checks": [
                {"id": "wrapper-exited-cleanly", "kind": "exit_code_zero"},
            ],
        },
        "budgets": {
            "timeout_seconds": 60,
            "max_model_calls": 0,
            "max_output_tokens": 0,
            "max_network_requests": 0,
        },
        "replay": {"supported": False, "snapshot_required": False},
        "failure_taxonomy": [
            "agent_failure",
            "test_failure",
            "workspace_policy_violation",
            "receipt_validation_failure",
        ],
    }


def make_spec(task="Implement the fixture change"):
    return RunSpec(
        run_id="coding-agent-test",
        skill=SkillRef(
            source_url="https://example.test/fixture",
            commit_or_digest="a" * 40,
            entrypoint="fixture_agent.py",
            provenance_digest="b" * 64,
        ),
        agent=AgentRef(harness="fixture", version="1.0.0"),
        model=ModelRef(provider="local", model="fixture", quota_class="local"),
        runtime=RuntimeRef(backend="fake", version="1", image_digest="sha256:fixture"),
        scenario=Scenario(id="fixture", task=task),
        limits=Limits(
            timeout_seconds=60,
            max_model_calls=0,
            max_output_tokens=0,
            max_network_requests=0,
        ),
    )


class CodingRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "fixture_agent.py").write_text(FIXTURE_AGENT, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_receipt(self, *, task="do not leak this task", coding=None):
        coding = coding or contract()
        command = ["python3", "fixture_agent.py"]
        config = build_runner_config(
            run_id="runner-test",
            task=task,
            child_command=command,
            contract=coding,
        )
        return execute_coding_agent(
            config,
            command,
            task,
            runtime_root=self.root,
        )

    def test_successful_receipt_is_digest_addressed_and_redacts_task_by_default(self):
        task = "do not leak this task"
        receipt = self.run_receipt(task=task)
        self.assertEqual(receipt.outcome, "pass")
        self.assertEqual(receipt.workspace_diff.changed_files, 1)
        self.assertEqual(receipt.agent_process.stdout_excerpt, "")
        serialized = receipt.model_dump_json()
        self.assertNotIn(task, serialized)
        self.assertEqual(
            parse_coding_receipt(serialized).receipt_digest,
            receipt.receipt_digest,
        )
        self.assertEqual(receipt.agent_events[0]["type"], "task.completed")
        self.assertNotIn("message", receipt.agent_events[0])

    def test_child_output_cannot_inject_a_top_level_receipt(self):
        injection_agent = self.root / "inject.py"
        injection_agent.write_text(
            """
import json, pathlib, sys
if '--version' in sys.argv:
    print('fixture-agent 1.0.0')
    raise SystemExit(0)
sys.stdin.read()
pathlib.Path('target.txt').write_text('done\\n')
print(json.dumps({'type': 'fake.receipt', 'outcome': 'pass', 'receipt_digest': '0' * 64}))
""",
            encoding="utf-8",
        )
        coding = contract(
            version_command=["python3", "inject.py", "--version"],
        )
        command = ["python3", "inject.py"]
        config = build_runner_config(
            run_id="injection-test",
            task="task",
            child_command=command,
            contract=coding,
        )
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "skill_native.coding_agent",
                "--config-b64",
                encode_runner_config(config),
                "--",
                *command,
            ],
            cwd=self.root,
            input="task",
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = parse_coding_receipt(proc.stdout)
        self.assertEqual(receipt.outcome, "pass")
        self.assertEqual(receipt.agent_events[0]["type"], "fake.receipt")
        self.assertNotEqual(receipt.receipt_digest, "0" * 64)

    def test_failing_test_forces_failed_outcome_even_when_agent_exits_zero(self):
        coding = contract(
            test_commands=[["python3", "-c", "raise SystemExit(7)"]]
        )
        receipt = self.run_receipt(coding=coding)
        self.assertEqual(receipt.agent_process.exit_code, 0)
        self.assertFalse(receipt.test_results[0].passed)
        self.assertEqual(receipt.outcome, "fail")

    def test_disallowed_protected_and_budgeted_changes_fail_closed(self):
        protected_agent = self.root / "protected.py"
        protected_agent.write_text(
            """
import json, pathlib, sys
if '--version' in sys.argv:
    print('fixture-agent 1.0.0')
    raise SystemExit(0)
sys.stdin.read()
pathlib.Path('AGENTS.md').write_text('changed')
pathlib.Path('target.txt').write_text('done\\n')
print(json.dumps({'type': 'done'}))
""",
            encoding="utf-8",
        )
        coding = contract(
            version_command=["python3", "protected.py", "--version"],
            allowed_change_globs=["**"],
            max_changed_files=1,
        )
        command = ["python3", "protected.py"]
        config = build_runner_config(
            run_id="protected",
            task="task",
            child_command=command,
            contract=coding,
        )
        receipt = execute_coding_agent(config, command, "task", runtime_root=self.root)
        self.assertEqual(receipt.outcome, "fail")
        self.assertIn("AGENTS.md", receipt.workspace_diff.protected_paths)
        self.assertFalse(receipt.policy_checks["changed_file_budget"])

    def test_tampered_receipt_is_rejected(self):
        raw = self.run_receipt().model_dump(mode="json")
        raw["workspace_diff"]["changed_files"] = 99
        with self.assertRaises(ValidationError):
            CodingAgentReceipt.model_validate(raw)

    def test_mutable_driver_version_and_unsafe_workspace_are_rejected(self):
        with self.assertRaises(ValidationError):
            contract(driver_version="latest")
        with self.assertRaises(ValidationError):
            contract(workspace="../escape")


class CodingHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "fixture_agent.py").write_text(FIXTURE_AGENT, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_coding_agent_vertical_slice_produces_domain_evidence_and_passes(self):
        manifest = HarnessManifest.model_validate(manifest_payload())
        result = HarnessKernel().run(
            manifest,
            make_spec(),
            LocalCodingFixtureRuntime(self.root),
        )
        self.assertEqual(result.verdict.status, VerdictStatus.PASS)
        self.assertTrue(result.evidence.assertions["coding_receipt_valid"])
        self.assertTrue(result.evidence.coding_receipt)
        self.assertEqual(len(result.evidence.agent_events), 1)
        self.assertEqual(len(result.evidence.test_results), 1)
        self.assertNotIn(make_spec().scenario.task, json.dumps(result.plan.command))
        self.assertEqual(
            result.plan.stdin_digest,
            hashlib.sha256(make_spec().scenario.task.encode()).hexdigest(),
        )

    def test_tampered_receipt_fails_domain_and_required_evidence_checks(self):
        manifest = HarnessManifest.model_validate(manifest_payload())
        result = HarnessKernel().run(
            manifest,
            make_spec(),
            LocalCodingFixtureRuntime(self.root, tamper_receipt=True),
        )
        self.assertEqual(result.verdict.status, VerdictStatus.FAIL)
        self.assertIn("domain:coding-receipt-continuity", result.verdict.failed_check_ids)
        self.assertIn("evidence:coding_receipt", result.verdict.failed_check_ids)

    def test_contract_is_required_only_for_coding_agent_adapter(self):
        raw = manifest_payload()
        raw.pop("coding")
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(raw)

        raw = manifest_payload()
        raw["identity"]["domain"] = "browser"
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(raw)

        raw = manifest_payload()
        raw["execution"] = {"adapter": "coding.command.v1", "command": ["true"]}
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(raw)

    def test_plan_digest_changes_with_coding_policy_and_stdin_capability_is_mandatory(self):
        spec = make_spec()
        plan_a = HarnessKernel().compile(
            HarnessManifest.model_validate(manifest_payload(max_changed_files=1)),
            spec,
        )
        plan_b = HarnessKernel().compile(
            HarnessManifest.model_validate(manifest_payload(max_changed_files=2)),
            spec,
        )
        self.assertNotEqual(plan_a.plan_digest, plan_b.plan_digest)

        no_stdin = RuntimeCapabilities(
            kernel_or_vm_isolation=False,
            network_deny_by_default=True,
            l7_http_policy=False,
            filesystem_policy=True,
            brokered_secrets=True,
            process_telemetry=False,
            snapshot_restore=False,
            persistent_filesystem=False,
            gpu=False,
            network_telemetry=False,
            stdin_stream=False,
        )
        with self.assertRaises(HarnessContractError):
            HarnessKernel().compile(
                HarnessManifest.model_validate(manifest_payload()),
                spec,
                capabilities=no_stdin,
                available_evidence=LocalCodingFixtureRuntime.evidence_kinds,
            )


if __name__ == "__main__":
    unittest.main()
