import unittest

from skill_native.cloudflare_runtime import CloudflareExecResult, CloudflareRuntimeController
from skill_native.compatibility import CompatibilityKey, aggregate_matrix
from skill_native.models import AgentRef, Limits, ModelRef, RunSpec, RuntimeRef, Scenario, SkillRef


class FakeCloudflareClient:
    def __init__(self):
        self.calls = 0
    def get_or_create(self, sandbox_id):
        return {"id": sandbox_id, "reused": False, "region": "test"}
    def exec(self, sandbox_id, command, *, timeout_ms):
        self.calls += 1
        return CloudflareExecResult(stdout="ok\n", stderr="", exit_code=0, success=True, metadata={"cpu_ms": 12})
    def manifest(self, sandbox_id, root="/workspace"):
        return {"a.txt": "one"} if self.calls == 0 else {"a.txt": "two", "b.txt": "new"}
    def events(self, sandbox_id):
        return [{"decision": "deny", "method": "GET", "url": "https://evil.test", "reason": "allowlist", "ts": "now"}]
    def destroy(self, sandbox_id):
        pass


def make_spec():
    return RunSpec(
        run_id="cf-1",
        skill=SkillRef(source_url="https://example.test", commit_or_digest="abc", provenance_digest="prov123"),
        agent=AgentRef(harness="codex", version="test"),
        model=ModelRef(provider="local", model="m", quota_class="local"),
        runtime=RuntimeRef(backend="cloudflare", version="test", image_digest="test"),
        scenario=Scenario(id="s", task="t"),
        limits=Limits(timeout_seconds=10),
    )


class CloudflareTests(unittest.TestCase):
    def test_normalized_evidence_and_fs_diff(self):
        controller = CloudflareRuntimeController(FakeCloudflareClient())
        sandbox = controller.prepare(make_spec())
        execution = controller.execute(sandbox, ["echo", "ok"])
        evidence = controller.collect("cf-1", execution)
        self.assertEqual(evidence.exit_code, 0)
        self.assertEqual(evidence.provenance_digest, "prov123")
        self.assertTrue(evidence.runtime_metadata["cold_start"])
        self.assertEqual(evidence.filesystem_after["diff"]["added"], ["b.txt"])
        self.assertEqual(evidence.filesystem_after["diff"]["modified"], ["a.txt"])
        self.assertEqual(evidence.network[0]["action"], "Denied")

    def test_matrix_keeps_model_as_confounder(self):
        controller = CloudflareRuntimeController(FakeCloudflareClient())
        sandbox = controller.prepare(make_spec())
        execution = controller.execute(sandbox, ["true"])
        evidence = controller.collect("cf-1", execution)
        rows = [
            (CompatibilityKey("sha", "codex@test", "cloudflare@test", "local:m1"), evidence),
            (CompatibilityKey("sha", "codex@test", "cloudflare@test", "local:m2"), evidence),
        ]
        cells = aggregate_matrix(rows)
        self.assertEqual(len(cells), 2)
        self.assertNotEqual(cells[0].key.model, cells[1].key.model)


if __name__ == "__main__":
    unittest.main()
