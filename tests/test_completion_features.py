import json
import tempfile
import unittest
from pathlib import Path

import httpx

from skill_native.adversarial import FIXTURES, hidden_variant, load_malskillbench_jsonl, materialize_all
from skill_native.compatibility import CompatibilityKey
from skill_native.evidence import EvidenceStore, attach_run_receipts, index_evidence
from skill_native.models import EvidenceBundle, InferenceReceipt, QuotaClass
from skill_native.openshell import OpenShellController, OpenShellError
from skill_native.policy import ReceiptLedger
from skill_native.provider_metadata import normalize_quota
from skill_native.registries import JsonMetadataAdapter, SkillsShAdapter
from skill_native.reporting import VerificationPolicy, build_report
from skill_native.scoring import ScorePolicy, score_evidence


class CompletionFeatureTests(unittest.TestCase):
    def test_receipts_materialize_into_evidence_and_persist(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = ReceiptLedger(Path(td) / "receipts.jsonl")
            receipt = InferenceReceipt(
                provider="local", model="m", request_hash="x", quota_class=QuotaClass.LOCAL,
                run_id="r1", input_tokens=3, output_tokens=2,
            )
            ledger.append(receipt, run_id="r1")
            bundle = attach_run_receipts(EvidenceBundle(run_id="r1"), ledger)
            self.assertEqual(len(bundle.inference), 1)
            digest, path = EvidenceStore(Path(td) / "evidence").persist(bundle)
            self.assertEqual(len(digest), 64)
            self.assertTrue(path.is_file())

    def test_evidence_index_is_content_addressed(self):
        bundle = EvidenceBundle(run_id="r", network=[{"action": "Denied", "url": "https://x"}])
        index = index_evidence(bundle)
        self.assertEqual(len(index), 1)
        self.assertEqual(len(next(iter(index))), 64)

    def test_skills_sh_adapter_and_openai_metadata_export(self):
        def handler(request):
            url = str(request.url)
            if "/skills/a/b/c" in url:
                return httpx.Response(200, json={
                    "id": "a/b/c", "source": "a/b", "slug": "c", "hash": "f" * 64,
                    "files": [{"path": "SKILL.md", "contents": "---\nname: c\n---\nok\n"}],
                })
            if "metadata.test" in url:
                return httpx.Response(200, json={"name": "plugin", "skills": ["x"]})
            return httpx.Response(404)
        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = SkillsShAdapter(client=client, token_env="TEST_OIDC")
        import os
        os.environ["TEST_OIDC"] = "token"
        try:
            skill = adapter.fetch("a/b/c")
            with tempfile.TemporaryDirectory() as td:
                provenance = adapter.provenance(skill, td)
                self.assertEqual(len(provenance.content_sha256), 64)
            record = JsonMetadataAdapter("openai-plugin", client=client).fetch("p", "https://metadata.test/p.json")
            self.assertEqual(len(record.immutable_digest), 64)
        finally:
            os.environ.pop("TEST_OIDC", None)

    def test_provider_quota_headers_normalize(self):
        receipt = InferenceReceipt(
            provider="groq", model="m", request_hash="x", quota_class=QuotaClass.FREE,
            rate_limit_headers={"x-ratelimit-remaining-requests": "42", "retry-after": "3"},
        )
        quota = normalize_quota(receipt)
        self.assertEqual(quota.remaining_requests, 42)
        self.assertEqual(quota.reset_seconds, 3.0)

    def test_executable_fixture_materialization_hidden_and_external_import(self):
        with tempfile.TemporaryDirectory() as td:
            paths = materialize_all(td)
            self.assertEqual(len(paths), len(FIXTURES))
            self.assertTrue(all((p / "SKILL.md").is_file() for p in paths))
            variant = hidden_variant(FIXTURES[0], "seed")
            self.assertNotEqual(variant.fixture_id, FIXTURES[0].fixture_id)
            corpus = Path(td) / "cases.jsonl"
            corpus.write_text(json.dumps({"id": "x", "label": "malicious", "category": "network"}) + "\n")
            self.assertTrue(load_malskillbench_jsonl(corpus)[0].malicious)

    def test_multi_axis_verification_and_uncertainty(self):
        rows = []
        evidence = EvidenceBundle(run_id="r", exit_code=0, assertions={"ok": True})
        for agent in ("codex", "claude"):
            for runtime in ("openshell", "cloudflare"):
                for model in ("m1", "m2"):
                    key = CompatibilityKey("sha", agent, runtime, model)
                    rows.extend((key, evidence) for _ in range(3))
        report = build_report(rows, VerificationPolicy())
        self.assertTrue(report["coverage"]["verified"])
        self.assertEqual(report["coverage"]["cells"], 8)
        self.assertIn("assertion_pass_ci95", report["cells"][0]["uncertainty"])

    def test_score_policy_has_versioned_non_correctness_weights(self):
        policy = ScorePolicy()
        self.assertEqual(policy.version, "v0.4")
        self.assertAlmostEqual(policy.correctness_weight + policy.reproducibility_weight + policy.least_privilege_weight, 1.0)
        result = score_evidence([EvidenceBundle(run_id="r", exit_code=0, assertions={"ok": True})], policy)
        self.assertAlmostEqual(result.aggregate_score, 1.0)

    def test_openshell_runtime_pin_mismatch_fails_closed(self):
        controller = OpenShellController()
        from skill_native.models import AgentRef, ModelRef, RunSpec, RuntimeRef, Scenario, SkillRef
        spec = RunSpec(
            run_id="r", skill=SkillRef(source_url="x", commit_or_digest="y"),
            agent=AgentRef(harness="codex", version="1"),
            model=ModelRef(provider="local", model="m", quota_class="local"),
            runtime=RuntimeRef(backend="openshell", version="1.0.0", image_digest="sha256:good"),
            scenario=Scenario(id="s", task="t"),
        )
        with self.assertRaises(OpenShellError):
            controller._attest_runtime(
                spec,
                status={"gateway_version": "2.0.0"},
                gateway_info={},
                metadata={"image_digest": "sha256:good"},
            )


if __name__ == "__main__":
    unittest.main()
