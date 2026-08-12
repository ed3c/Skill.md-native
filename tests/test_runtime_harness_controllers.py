import hashlib
import unittest
from unittest.mock import patch

from skill_native.models import (
    AgentRef,
    EvidenceBundle,
    ModelRef,
    RunSpec,
    RuntimeRef,
    Scenario,
    SkillRef,
)
from skill_native.openshell import CommandResult
from skill_native.runtime_harness_controllers import (
    CloudflareHarnessController,
    OpenShellHarnessController,
)


class InputRunner:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, timeout=None, input_text=None):
        self.calls.append(
            {"argv": list(argv), "timeout": timeout, "input_text": input_text}
        )
        return CommandResult(argv=list(argv), returncode=0, stdout="{}", stderr="")


class NoopCloudflareClient:
    def get_or_create(self, sandbox_id):
        return {"id": sandbox_id}

    def exec(self, sandbox_id, command, *, timeout_ms):
        raise AssertionError("patched in this test")

    def manifest(self, sandbox_id, root="/workspace"):
        return {}

    def events(self, sandbox_id):
        return []

    def destroy(self, sandbox_id):
        return None


def make_spec(backend="openshell"):
    return RunSpec(
        run_id="continuity",
        skill=SkillRef(
            source_url="https://example.test/skill",
            commit_or_digest="a" * 40,
            provenance_digest="b" * 64,
        ),
        agent=AgentRef(harness="fixture", version="1"),
        model=ModelRef(provider="local", model="fixture", quota_class="local"),
        runtime=RuntimeRef(backend=backend, version="1", image_digest="sha256:test"),
        scenario=Scenario(id="fixture", task="secret task"),
    )


class RuntimeHarnessControllerTests(unittest.TestCase):
    def test_openshell_streams_stdin_once_and_attaches_digests(self):
        runner = InputRunner()
        controller = OpenShellHarnessController(runner=runner)
        spec = make_spec()
        controller._runs["sandbox"] = {"spec": spec, "executions": {}}
        execution_id = controller.execute(
            "sandbox",
            ["agent", "--json"],
            stdin="secret task",
        )
        self.assertEqual(runner.calls[-1]["input_text"], "secret task")
        raw = EvidenceBundle(
            run_id=spec.run_id,
            provenance_digest=spec.skill.provenance_digest,
            commands=[{"argv": ["openshell", "sandbox", "exec"]}],
        )
        with patch(
            "skill_native.runtime_harness_controllers.OpenShellController.collect",
            return_value=raw,
        ):
            evidence = controller.collect(spec.run_id, execution_id)
        self.assertEqual(
            evidence.commands[0]["requested_argv"],
            ["agent", "--json"],
        )
        self.assertEqual(
            evidence.commands[0]["stdin_digest"],
            hashlib.sha256(b"secret task").hexdigest(),
        )

    def test_cloudflare_attaches_requested_argv_without_claiming_stdin(self):
        controller = CloudflareHarnessController(NoopCloudflareClient())
        controller._harness_commands["box:exec:0"] = ["echo", "ok"]
        raw = EvidenceBundle(
            run_id="continuity",
            commands=[{"execution_id": "box:exec:0", "exit_code": 0}],
        )
        with patch(
            "skill_native.runtime_harness_controllers.CloudflareRuntimeController.collect",
            return_value=raw,
        ):
            evidence = controller.collect("continuity", "box:exec:0")
        self.assertEqual(evidence.commands[0]["requested_argv"], ["echo", "ok"])
        self.assertIsNone(evidence.commands[0]["stdin_digest"])


if __name__ == "__main__":
    unittest.main()
