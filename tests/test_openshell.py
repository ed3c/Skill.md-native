import json
import unittest

from skill_native.models import (
    AgentRef,
    Limits,
    ModelRef,
    NetworkRule,
    RunSpec,
    RuntimeRef,
    SandboxPolicy,
    Scenario,
    SkillRef,
)
from skill_native.openshell import (
    CommandResult,
    OpenShellController,
    OpenShellError,
    OpenShellPolicyCompiler,
)


class ScriptedRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, argv, *, timeout=None):
        self.calls.append((argv, timeout))
        if not self.responses:
            raise AssertionError(f"unexpected command: {argv}")
        response = self.responses.pop(0)
        return CommandResult(argv=argv, **response)


def make_spec(**policy_overrides):
    policy = SandboxPolicy(**policy_overrides)
    return RunSpec(
        run_id="case-001",
        skill=SkillRef(source_url="https://example.test/skill", commit_or_digest="abc"),
        agent=AgentRef(harness="codex", version="test"),
        model=ModelRef(provider="local", model="test", quota_class="local"),
        runtime=RuntimeRef(
            backend="openshell",
            version="0.0.44",
            image_digest="sha256:test",
        ),
        policy=policy,
        scenario=Scenario(id="smoke", task="smoke"),
        limits=Limits(timeout_seconds=10),
    )


class PolicyCompilerTests(unittest.TestCase):
    def test_default_is_deny_by_omission_and_hard_landlock(self):
        policy = OpenShellPolicyCompiler().compile(make_spec())
        self.assertEqual(policy["network_policies"], {})
        self.assertEqual(policy["landlock"]["compatibility"], "hard_requirement")
        self.assertNotIn("/", policy["filesystem_policy"]["read_write"])

    def test_legacy_host_is_read_only_rest(self):
        policy = OpenShellPolicyCompiler().compile(
            make_spec(allowed_hosts=["api.github.com"])
        )
        endpoint = next(iter(policy["network_policies"].values()))["endpoints"][0]
        self.assertEqual(endpoint["access"], "read-only")
        self.assertEqual(endpoint["protocol"], "rest")

    def test_mutating_access_requires_explicit_network_rule(self):
        policy = OpenShellPolicyCompiler().compile(
            make_spec(
                network_rules=[
                    NetworkRule(
                        host="api.example.com",
                        access="read-write",
                        binaries=["/usr/bin/python3"],
                    )
                ]
            )
        )
        entry = next(iter(policy["network_policies"].values()))
        self.assertEqual(entry["endpoints"][0]["access"], "read-write")
        self.assertEqual(entry["binaries"], [{"path": "/usr/bin/python3"}])

    def test_generic_mcp_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            OpenShellPolicyCompiler().compile(
                make_spec(
                    network_rules=[
                        NetworkRule(host="mcp.example.com", protocol="mcp")
                    ]
                )
            )


class ControllerTests(unittest.TestCase):
    def test_collect_requires_ocsf_and_normalizes_events(self):
        ocsf = "\n".join(
            [
                json.dumps({"class_uid": 1007, "activity_name": "Launch"}),
                json.dumps(
                    {
                        "class_uid": 4001,
                        "action": "Denied",
                        "dst_endpoint": {"domain": "evil.test"},
                    }
                ),
                json.dumps({"class_uid": 2004, "severity": "High"}),
            ]
        ) + "\n"
        runner = ScriptedRunner(
            [
                {"returncode": 0, "stdout": "created\n", "stderr": ""},
                {
                    "returncode": 0,
                    "stdout": json.dumps({"name": "case", "state": "ready"}),
                    "stderr": "",
                },
                {"returncode": 0, "stdout": "ok\n", "stderr": ""},
                {"returncode": 0, "stdout": "hello\n", "stderr": ""},
                {"returncode": 0, "stdout": "version: 1\n", "stderr": ""},
                {
                    "returncode": 0,
                    "stdout": "OCSF NET:OPEN DENIED\n",
                    "stderr": "",
                },
                {"returncode": 0, "stdout": ocsf, "stderr": ""},
                {"returncode": 0, "stdout": "deleted\n", "stderr": ""},
            ]
        )
        controller = OpenShellController(runner=runner)
        sandbox = controller.prepare(make_spec())
        execution = controller.execute(sandbox, ["echo", "hello"])
        evidence = controller.collect("case-001", execution)
        self.assertEqual(evidence.exit_code, 0)
        self.assertEqual(len(evidence.processes), 1)
        self.assertEqual(len(evidence.network), 1)
        self.assertEqual(len(evidence.findings), 1)
        self.assertTrue(evidence.assertions["ocsf_captured"])
        controller.destroy(sandbox)

    def test_missing_ocsf_fails_closed(self):
        runner = ScriptedRunner(
            [
                {"returncode": 0, "stdout": "created\n", "stderr": ""},
                {
                    "returncode": 0,
                    "stdout": json.dumps({"name": "case", "state": "ready"}),
                    "stderr": "",
                },
                {"returncode": 0, "stdout": "ok\n", "stderr": ""},
                {"returncode": 0, "stdout": "hello\n", "stderr": ""},
                {"returncode": 0, "stdout": "version: 1\n", "stderr": ""},
                {"returncode": 0, "stdout": "normal log\n", "stderr": ""},
                {"returncode": 0, "stdout": "", "stderr": ""},
                {"returncode": 0, "stdout": "deleted\n", "stderr": ""},
            ]
        )
        controller = OpenShellController(runner=runner)
        sandbox = controller.prepare(make_spec())
        execution = controller.execute(sandbox, ["true"])
        try:
            with self.assertRaises(OpenShellError):
                controller.collect("case-001", execution)
        finally:
            controller.destroy(sandbox)


if __name__ == "__main__":
    unittest.main()
