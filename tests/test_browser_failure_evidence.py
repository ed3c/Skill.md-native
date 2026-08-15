from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from skill_native.browser_contract import (
    BrowserReceipt,
    build_browser_runner_config,
)
from skill_native.browser_fixture_runtime import LocalBrowserFixtureRuntime
from skill_native.evidence import canonical_digest, captured_evidence
from skill_native.harness import HarnessKernel, load_harness_manifest
from skill_native.models import EvidenceBundle, RunSpec
from skill_native.security import evaluate_security


ROOT = Path(__file__).resolve().parents[1]


class BrowserFailureEvidenceTests(unittest.TestCase):
    def test_bound_failure_receipt_preserves_denied_network_evidence(self) -> None:
        manifest = load_harness_manifest(
            ROOT / "examples/harnesses/browser/harness.yaml"
        )
        spec = RunSpec.model_validate(
            yaml.safe_load(
                (
                    ROOT / "examples/harnesses/browser/run.fake.yaml"
                ).read_text(encoding="utf-8")
            )
        )
        self.assertIsNotNone(manifest.browser)
        contract = manifest.browser
        assert contract is not None

        with tempfile.TemporaryDirectory(
            prefix="skill-native-browser-failure-"
        ) as temp:
            workspace = Path(temp)
            artifact_root = workspace / contract.artifact_root / spec.run_id
            artifact_root.mkdir(parents=True)
            runtime = LocalBrowserFixtureRuntime(workspace)
            kernel = HarnessKernel()
            plan = kernel.compile(
                manifest,
                spec,
                capabilities=runtime.capabilities,
                available_evidence=runtime.evidence_kinds,
            )
            config = build_browser_runner_config(
                run_id=spec.run_id,
                contract=contract,
            )
            denied = {
                "phase": "request",
                "method": "GET",
                "url": "http://localhost:8765/external",
                "origin": "http://localhost:8765",
                "resource_type": "document",
                "action": "Denied",
            }
            payload = {
                "schema_version": "1.0",
                "runner_version": "0.1.0",
                "run_id": spec.run_id,
                "config_digest": config.config_digest,
                "contract_digest": config.contract_digest,
                "action_plan_digest": config.action_plan_digest,
                "driver": contract.driver,
                "driver_version": contract.driver_version,
                "browser": contract.browser,
                "browser_version": "fixture",
                "headless": contract.headless,
                "outcome": "fail",
                "final_url": contract.allowed_origins[0] + "/",
                "title": "Browser Fixture",
                "page_count": 1,
                "events": [],
                "network_events": [denied],
                "console_events": [],
                "page_errors": [],
                "artifacts": [],
                "assertions": {
                    "action:0:goto": True,
                    "action:1:click": False,
                },
                "policy_checks": {
                    "driver_version": True,
                    "allowed_origins": False,
                    "page_budget": True,
                    "event_budget": True,
                    "network_budget": True,
                    "console_budget": True,
                    "artifact_budget": True,
                    "side_effects": True,
                    "assertions": False,
                },
                "violations": [
                    "unexpected origin: http://localhost:8765"
                ],
                "error": "BrowserRunnerError: blocked by origin policy",
            }
            receipt = BrowserReceipt.model_validate(
                {**payload, "receipt_digest": canonical_digest(payload)}
            )
            stdout = json.dumps(
                receipt.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
            evidence = EvidenceBundle(
                run_id=spec.run_id,
                exit_code=1,
                stdout=stdout,
                stderr="",
                runtime_metadata={"workspace_root": str(workspace)},
            )
            adapter = kernel.adapters.require(plan.adapter)
            normalized = adapter.normalize_evidence(
                manifest,
                plan,
                evidence,
            )

        self.assertTrue(normalized.assertions["browser_receipt_valid"])
        self.assertFalse(normalized.assertions["browser_outcome_pass"])
        self.assertFalse(normalized.assertions["browser_policy_pass"])
        self.assertTrue(normalized.assertions["browser_artifacts_valid"])
        self.assertEqual(normalized.network[0]["action"], "Denied")
        self.assertIn("network", captured_evidence(normalized))
        self.assertNotIn("dom_snapshot", captured_evidence(normalized))

        security = evaluate_security(normalized)
        self.assertEqual(security.security_gate, "fail")
        self.assertEqual(security.findings[-1]["rule"], "undeclared_network")
        self.assertEqual(
            security.findings[-1]["rule_id"],
            "runtime.network.denied",
        )


if __name__ == "__main__":
    unittest.main()
