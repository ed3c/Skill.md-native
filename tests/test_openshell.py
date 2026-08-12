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
from skill_native.openshell import CommandResult, OpenShellController, OpenShellError, OpenShellPolicyCompiler


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


def ok(stdout=""):
    return {"returncode": 0, "stdout": stdout, "stderr": ""}


def make_spec(**policy_overrides):
    return RunSpec(
        run_id="case-001",
        skill=SkillRef(source_url="https://example.test/skill", commit_or_digest="abc"),
        agent=AgentRef(harness="codex", version="test"),
        model=ModelRef(provider="local", model="test", quota_class="local"),
        runtime=RuntimeRef(backend="openshell", version="0.0.44", image_digest="sha256:test"),
        policy=SandboxPolicy(**policy_overrides),
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
        policy = OpenShellPolicyCompiler().compile(make_spec(allowed_hosts=["api.github.com"]))
        endpoint = next(iter(policy["network_policies"].values()))["endpoints"][0]
        self.assertEqual(endpoint["access"], "read-only")
        self.assertEqual(endpoint["protocol"], "rest")

    def test_mutating_access_requires_explicit_network_rule(self):
        policy = OpenShellPolicyCompiler().compile(
            make_spec(network_rules=[NetworkRule(host="api.example.com", access="read-write", binaries=["/usr/bin/python3"])])
        )
        entry = next(iter(policy["network_policies"].values()))
        self.assertEqual(entry["endpoints"][0]["access"], "read-write")
        self.assertEqual(entry["binaries"], [{"path": "/usr/bin/python3"}])

    def test_generic_mcp_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            OpenShellPolicyCompiler().compile(
                make_spec(network_rules=[NetworkRule(host="mcp.example.com", protocol="mcp")])
            )


class ControllerTests(unittest.TestCase):
    def _prepare_prefix(self, before_manifest=""):
        return [
            ok(json.dumps({"status": "connected", "gateway_version": "0.0.44"})),
            ok(json.dumps({"compute_drivers": [{"name": "podman", "version": "5"}]})),
            ok("created\n"),
            ok(json.dumps({"name": "case", "state": "ready", "image": "sha256:test"})),
            ok("ok\n"),
            ok(before_manifest),
        ]

    def test_collect_requires_ocsf_and_captures_filesystem_diff(self):
        ocsf = "\n".join([
            json.dumps({"class_uid": 1007, "activity_name": "Launch"}),
            json.dumps({"class_uid": 4001, "action": "Denied", "dst_endpoint": {"domain": "evil.test"}}),
            json.dumps({"class_uid": 2004, "severity": "High"}),
        ]) + "\n"
        sha_a = "a" * 64
        sha_b = "b" * 64
        sha_c = "c" * 64
        runner = ScriptedRunner(
            self._prepare_prefix(f"{sha_a}  /sandbox/a.txt\n")
            + [
                ok("hello\n"),
                ok(f"{sha_b}  /sandbox/a.txt\n{sha_c}  /sandbox/new.txt\n"),
                ok("version: 1\n"),
                ok("OCSF NET:OPEN DENIED\n"),
                ok(ocsf),
                ok("deleted\n"),
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
        self.assertEqual(evidence.filesystem_after["diff"]["added"], ["/sandbox/new.txt"])
        self.assertEqual(evidence.filesystem_after["diff"]["modified"], ["/sandbox/a.txt"])
        self.assertTrue(evidence.assertions["runtime_attested"])
        self.assertEqual(evidence.runtime_metadata["gateway_status"]["gateway_version"], "0.0.44")
        controller.destroy(sandbox)

    def test_missing_ocsf_fails_closed(self):
        runner = ScriptedRunner(
            self._prepare_prefix()
            + [
                ok("hello\n"),
                ok(""),
                ok("version: 1\n"),
                ok("normal log\n"),
                ok(""),
                ok("deleted\n"),
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

    def test_manifest_diff_marks_removed_files(self):
        before = {"/sandbox/a": {"sha256": "a"}, "/sandbox/b": {"sha256": "b"}}
        after = {"/sandbox/b": {"sha256": "b"}}
        diff = OpenShellController._diff_manifests(before, after)
        self.assertEqual(diff["removed"], ["/sandbox/a"])


if __name__ == "__main__":
    unittest.main()
