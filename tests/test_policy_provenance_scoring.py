import json
import tempfile
import unittest
from pathlib import Path

from skill_native.models import EvidenceBundle, InferenceReceipt, QuotaClass
from skill_native.policy import ProviderPolicy, ReceiptLedger
from skill_native.provenance import SourceAttestation, build_provenance, merge_equivalent
from skill_native.providers import ProviderConfig, ProviderKind
from skill_native.scoring import ScorePolicy, persist_score_artifact, score_evidence


class PolicyTests(unittest.TestCase):
    def test_local_only_filters_external_providers(self):
        providers = [
            ProviderConfig(name="local", kind=ProviderKind.LOCAL, base_url="http://127.0.0.1:1", model="m", quota_class="local"),
            ProviderConfig(name="groq", kind=ProviderKind.GROQ, base_url="https://example.test", model="m", quota_class="free"),
        ]
        selected = ProviderPolicy(local_only=True).filter(providers)
        self.assertEqual([p.name for p in selected], ["local"])

    def test_receipt_ledger_enforces_request_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ReceiptLedger(Path(tmp) / "receipts.jsonl")
            ledger.append(InferenceReceipt(provider="local", model="m", request_hash="abc", quota_class=QuotaClass.LOCAL))
            with self.assertRaises(RuntimeError):
                ledger.assert_budget(ProviderPolicy(max_daily_requests=1))


class ProvenanceTests(unittest.TestCase):
    def _skill(self, root: Path):
        (root / "SKILL.md").write_text("---\nname: test\n---\nDo a thing.\n")
        (root / "LICENSE").write_text("MIT License\n")
        (root / "requirements.txt").write_text("httpx==0.27.0\n")

    def test_mutable_ref_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._skill(root)
            with self.assertRaises(ValueError):
                build_provenance(root, entrypoint="SKILL.md", attestation=SourceAttestation(registry="github", source_url="https://example.test", immutable_ref="main"))

    def test_identical_content_deduplicates_attestations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._skill(root)
            a = build_provenance(root, entrypoint="SKILL.md", attestation=SourceAttestation(registry="github", source_url="https://a.test", immutable_ref="a" * 40))
            b = build_provenance(root, entrypoint="SKILL.md", attestation=SourceAttestation(registry="skills.sh", source_url="https://b.test", immutable_ref="a" * 40))
            merged = merge_equivalent([a, b])
            self.assertEqual(len(merged), 1)
            self.assertEqual(len(merged[0].attestations), 2)
            self.assertEqual(merged[0].license_expression, "MIT")
            self.assertEqual(merged[0].dependency_files, ("requirements.txt",))


class ScoringTests(unittest.TestCase):
    def test_critical_finding_is_non_compensable(self):
        evidence = EvidenceBundle(run_id="r", exit_code=0, assertions={"ok": True}, findings=[{"severity": "High"}])
        result = score_evidence([evidence])
        self.assertEqual(result.security_gate, "fail")
        self.assertEqual(result.aggregate_score, 0.0)
        self.assertEqual(result.confidence, "exploratory")

    def test_runtime_derived_denied_network_is_non_compensable(self):
        evidence = EvidenceBundle(
            run_id="r",
            exit_code=0,
            assertions={"ok": True},
            network=[{"action": "Denied", "dst_endpoint": {"domain": "exfil.test"}}],
        )
        result = score_evidence([evidence])
        self.assertEqual(result.security_gate, "fail")
        self.assertEqual(result.aggregate_score, 0.0)
        self.assertEqual(result.raw_metrics["least_privilege"], 0.0)

    def test_inference_cost_latency_tokens_and_reproducibility_are_raw_dimensions(self):
        receipt = InferenceReceipt(
            provider="local",
            model="m",
            request_hash="abc",
            quota_class=QuotaClass.LOCAL,
            input_tokens=10,
            output_tokens=5,
            latency_ms=25,
            price_usd=0.0,
        )
        evidence = EvidenceBundle(
            run_id="r",
            exit_code=0,
            assertions={"ok": True, "recovery_success": True},
            inference=[receipt],
        )
        result = score_evidence([evidence, evidence, evidence])
        self.assertEqual(result.raw_metrics["reproducibility_rate"], 1.0)
        self.assertEqual(result.raw_metrics["least_privilege"], 1.0)
        self.assertEqual(result.raw_metrics["latency_ms_p50"], 25.0)
        self.assertEqual(result.raw_metrics["input_tokens"], 30)
        self.assertEqual(result.raw_metrics["output_tokens"], 15)
        self.assertEqual(result.raw_metrics["recovery_success"], 1.0)
        self.assertLess(result.raw_metrics["task_success_ci95_low"], 1.0)
        self.assertEqual(result.raw_metrics["task_success_ci95_high"], 1.0)

    def test_score_artifact_is_digest_addressed(self):
        evidence = EvidenceBundle(run_id="r", exit_code=0, assertions={"ok": True})
        policy = ScorePolicy()
        result = score_evidence([evidence, evidence, evidence], policy)
        with tempfile.TemporaryDirectory() as td:
            digest, path = persist_score_artifact(result, policy, td)
            self.assertEqual(len(digest), 64)
            self.assertTrue(path.is_file())
            payload = json.loads(path.read_text())
            self.assertEqual(payload["policy"]["version"], "v0.4")
            self.assertEqual(payload["result"]["sample_count"], 3)

    def test_confidence_thresholds(self):
        evidence = EvidenceBundle(run_id="r", exit_code=0, assertions={"ok": True})
        self.assertEqual(score_evidence([evidence] * 3).confidence, "candidate")
        self.assertEqual(score_evidence([evidence] * 10).confidence, "verified")


if __name__ == "__main__":
    unittest.main()
