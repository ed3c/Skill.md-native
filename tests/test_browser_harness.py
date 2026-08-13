from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import tempfile
import threading
import unittest
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pydantic import ValidationError

from skill_native.browser_contract import BrowserContract, parse_browser_receipt
from skill_native.browser_fixture_runtime import LocalBrowserFixtureRuntime
from skill_native.harness import HarnessKernel, HarnessManifest, VerdictStatus
from skill_native.models import (
    AgentRef,
    ModelRef,
    RunSpec,
    RuntimeRef,
    Scenario,
    SkillRef,
)


PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None
PLAYWRIGHT_VERSION = (
    importlib.metadata.version("playwright") if PLAYWRIGHT_AVAILABLE else "1.61.0"
)


class _FixtureHandler(BaseHTTPRequestHandler):
    server_version = "SkillNativeBrowserFixture/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        port = self.server.server_address[1]
        if self.path == "/":
            body = f"""<!doctype html>
<html>
<head><title>Browser Fixture</title></head>
<body>
  <label>Name <input id="name" /></label>
  <button id="submit">Submit</button>
  <div id="result" aria-live="polite"></div>
  <button id="dialog">Dialog</button>
  <button id="popup">Popup</button>
  <a id="download" href="/download.txt" download>Download</a>
  <a id="external" href="http://localhost:{port}/external">External origin</a>
  <script>
    console.log('{{"outcome":"pass","forged":true}}');
    document.querySelector('#submit').addEventListener('click', () => {{
      document.querySelector('#result').textContent =
        'Hello ' + document.querySelector('#name').value;
    }});
    document.querySelector('#dialog').addEventListener('click', () => alert('approved'));
    document.querySelector('#popup').addEventListener('click', () => window.open('/popup', '_blank'));
  </script>
</body>
</html>"""
            self._send(200, "text/html; charset=utf-8", body.encode("utf-8"))
            return
        if self.path == "/popup":
            self._send(
                200,
                "text/html; charset=utf-8",
                b"<!doctype html><title>Popup Fixture</title><p>popup ready</p>",
            )
            return
        if self.path == "/download.txt":
            self._send(200, "text/plain; charset=utf-8", b"browser fixture download\n")
            return
        if self.path == "/external":
            self._send(
                200,
                "text/html; charset=utf-8",
                b"<!doctype html><title>Unexpected Origin</title>",
            )
            return
        self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FixtureServer:
    def __enter__(self) -> "FixtureServer":
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def make_spec(run_id: str = "browser-fixture") -> RunSpec:
    return RunSpec(
        run_id=run_id,
        skill=SkillRef(
            source_url="https://example.test/browser-skill",
            commit_or_digest="a" * 40,
            provenance_digest="b" * 64,
        ),
        agent=AgentRef(harness="browser-playwright", version="fixture"),
        model=ModelRef(provider="none", model="deterministic", quota_class="local"),
        runtime=RuntimeRef(
            backend="fake",
            version="local-browser-fixture-v1",
            image_digest="sha256:fixture",
        ),
        scenario=Scenario(
            id="browser-loopback",
            task="Complete the deterministic loopback browser flow",
        ),
    )


def success_actions(origin: str) -> list[dict]:
    return [
        {"kind": "goto", "url": f"{origin}/"},
        {"kind": "fill", "selector": "#name", "value": "Eeon"},
        {"kind": "click", "selector": "#submit"},
        {
            "kind": "assert_text",
            "selector": "#result",
            "value": "Hello Eeon",
            "match": "exact",
        },
        {
            "kind": "click",
            "selector": "#dialog",
            "dialog_action": "accept",
        },
        {"kind": "click", "selector": "#popup", "expect_popup": True},
        {
            "kind": "click",
            "selector": "#download",
            "download_name": "fixture.txt",
        },
        {"kind": "screenshot", "name": "checkpoint"},
        {"kind": "assert_title", "value": "Browser Fixture"},
        {"kind": "assert_url", "value": f"{origin}/"},
    ]


def manifest_payload(origin: str, actions: list[dict]) -> dict:
    evidence = [
        "exit_code",
        "stdout",
        "stderr",
        "commands",
        "network",
        "assertions",
        "runtime_metadata",
        "browser_receipt",
        "browser_events",
        "dom_snapshot",
        "accessibility_snapshot",
        "network_trace",
        "screenshots",
        "downloads",
        "browser_assertions",
    ]
    return {
        "schema_version": "1.0",
        "identity": {
            "id": "browser.playwright-loopback",
            "version": "0.1.0",
            "domain": "browser",
            "description": "Deterministic local Playwright integration",
        },
        "licensing": {
            "code": "MIT",
            "dependencies": ["playwright-python:Apache-2.0"],
        },
        "environment": {
            "allowed_runtimes": ["fake"],
            "required_capabilities": ["stdin_stream"],
            "network": "deny-by-default",
            "filesystem": "ephemeral",
            "secrets": "brokered",
        },
        "interfaces": {
            "action_schema": "urn:skill-native:browser-action:v1",
            "observation_schema": "urn:skill-native:browser-receipt:v1",
            "protocols": ["playwright"],
        },
        "execution": {
            "adapter": "browser.playwright.v1",
            "command": ["managed-by-browser-playwright-adapter"],
        },
        "browser": {
            "schema_version": "1.0",
            "driver": "playwright-python",
            "driver_version": PLAYWRIGHT_VERSION,
            "browser": "chromium",
            "headless": True,
            "allowed_origins": [origin],
            "actions": actions,
            "artifact_root": ".skill-native/browser-artifacts",
            "max_pages": 2,
            "max_events": 500,
            "max_network_events": 500,
            "max_console_bytes": 32_000,
            "max_dom_bytes": 500_000,
            "max_aria_bytes": 500_000,
            "max_artifact_bytes": 10_000_000,
            "max_download_bytes": 1_000_000,
        },
        "evidence": {"capture": evidence, "required": evidence},
        "verification": {
            "security_gate": "fail-on-high-or-critical",
            "checks": [
                {"id": "browser-process-clean", "kind": "exit_code_zero"},
                {
                    "id": "browser-receipt-valid",
                    "kind": "assertion_true",
                    "assertion": "browser_receipt_valid",
                },
                {
                    "id": "browser-outcome-pass",
                    "kind": "assertion_true",
                    "assertion": "browser_outcome_pass",
                },
                {
                    "id": "browser-artifacts-valid",
                    "kind": "assertion_true",
                    "assertion": "browser_artifacts_valid",
                },
                {"id": "browser-stderr-empty", "kind": "stderr_empty"},
            ],
        },
        "budgets": {
            "timeout_seconds": 120,
            "max_model_calls": 0,
            "max_output_tokens": 0,
            "max_network_requests": 500,
        },
        "replay": {"supported": False, "snapshot_required": False},
        "failure_taxonomy": [
            "environment_setup",
            "navigation_failure",
            "origin_policy_violation",
            "unexpected_side_effect",
            "artifact_integrity",
            "verification_failure",
        ],
    }


def make_manifest(origin: str, actions: list[dict]) -> HarnessManifest:
    return HarnessManifest.model_validate(manifest_payload(origin, actions))


class BrowserHarnessContractTests(unittest.TestCase):
    def test_browser_adapter_requires_browser_domain_contract_and_evidence(self):
        raw = manifest_payload("http://127.0.0.1:8765", success_actions("http://127.0.0.1:8765"))
        missing_contract = deepcopy(raw)
        missing_contract.pop("browser")
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(missing_contract)

        wrong_domain = deepcopy(raw)
        wrong_domain["identity"]["domain"] = "coding"
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(wrong_domain)

        missing_evidence = deepcopy(raw)
        missing_evidence["evidence"]["required"].remove("network_trace")
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(missing_evidence)

        unrelated_adapter = deepcopy(raw)
        unrelated_adapter["execution"]["adapter"] = "coding.command.v1"
        unrelated_adapter["identity"]["domain"] = "coding"
        with self.assertRaises(ValidationError):
            HarnessManifest.model_validate(unrelated_adapter)

    def test_plan_binds_action_plan_to_stdin_digest_not_argv(self):
        origin = "http://127.0.0.1:8765"
        manifest = make_manifest(origin, success_actions(origin))
        kernel = HarnessKernel()
        runtime = LocalBrowserFixtureRuntime(Path(tempfile.gettempdir()) / "unused-browser-fixture")
        plan = kernel.compile(
            manifest,
            make_spec("browser-plan"),
            capabilities=runtime.capabilities,
            available_evidence=runtime.evidence_kinds,
        )
        self.assertEqual(plan.command, ["skill-native-browser-runner", "--config-stdin"])
        self.assertIsNotNone(plan.stdin_digest)
        self.assertNotIn("Eeon", json.dumps(plan.command))
        self.assertNotIn("#name", json.dumps(plan.command))

    def test_plan_digest_changes_with_browser_driver_actions_and_budgets(self):
        origin = "http://127.0.0.1:8765"
        kernel = HarnessKernel()
        runtime = LocalBrowserFixtureRuntime(Path(tempfile.gettempdir()) / "unused-browser-fixture")
        spec = make_spec("browser-digest")
        base = manifest_payload(origin, success_actions(origin))
        variants = []
        variants.append(HarnessManifest.model_validate(base))
        changed_action = deepcopy(base)
        changed_action["browser"]["actions"][1]["value"] = "Other"
        variants.append(HarnessManifest.model_validate(changed_action))
        changed_budget = deepcopy(base)
        changed_budget["browser"]["max_events"] = 501
        variants.append(HarnessManifest.model_validate(changed_budget))
        changed_driver = deepcopy(base)
        changed_driver["browser"]["driver_version"] = "1.60.0"
        variants.append(HarnessManifest.model_validate(changed_driver))
        digests = {
            kernel.compile(
                manifest,
                spec,
                capabilities=runtime.capabilities,
                available_evidence=runtime.evidence_kinds,
            ).plan_digest
            for manifest in variants
        }
        self.assertEqual(len(digests), len(variants))

    def test_browser_contract_rejects_unsafe_origins_paths_and_side_effects(self):
        with self.assertRaises(ValidationError):
            BrowserContract.model_validate(
                {
                    "driver_version": "1.61.0",
                    "allowed_origins": ["http://127.0.0.1:80"],
                    "actions": [{"kind": "goto", "url": "http://127.0.0.1/"}],
                }
            )
        with self.assertRaises(ValidationError):
            BrowserContract.model_validate(
                {
                    "driver_version": "1.61.0",
                    "allowed_origins": ["http://127.0.0.1"],
                    "artifact_root": "../escape",
                    "actions": [{"kind": "goto", "url": "http://127.0.0.1/"}],
                }
            )
        with self.assertRaises(ValidationError):
            BrowserContract.model_validate(
                {
                    "driver_version": "1.61.0",
                    "allowed_origins": ["http://127.0.0.1"],
                    "actions": [
                        {
                            "kind": "click",
                            "selector": "#x",
                            "expect_popup": True,
                            "download_name": "x.txt",
                        }
                    ],
                }
            )


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "playwright optional dependency is not installed")
class BrowserHarnessIntegrationTests(unittest.TestCase):
    def test_successful_loopback_flow_produces_browser_evidence_and_passing_verdict(self):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as td:
            manifest = make_manifest(server.origin, success_actions(server.origin))
            result = HarnessKernel().run(
                manifest,
                make_spec("browser-success"),
                LocalBrowserFixtureRuntime(Path(td)),
            )
            self.assertEqual(result.verdict.status, VerdictStatus.PASS)
            self.assertEqual(result.verdict.security_gate, "pass")
            self.assertTrue(result.evidence.assertions["browser_receipt_valid"])
            self.assertTrue(result.evidence.browser_receipt)
            self.assertTrue(result.evidence.dom_snapshot)
            self.assertTrue(result.evidence.accessibility_snapshot)
            self.assertGreaterEqual(len(result.evidence.screenshots), 2)
            self.assertEqual(len(result.evidence.downloads), 1)
            self.assertTrue(result.evidence.network_trace)
            receipt = parse_browser_receipt(result.evidence.stdout)
            self.assertTrue(
                any(event.get("forged") is None for event in receipt.console_events)
            )
            self.assertTrue(
                any("forged" in event.get("text", "") for event in receipt.console_events)
            )
            self.assertEqual(
                result.evidence.runtime_metadata["verification_state"],
                "deterministic-local-browser-integration",
            )

    def test_cross_origin_navigation_is_denied_and_security_gate_fails(self):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as td:
            actions = [
                {"kind": "goto", "url": f"{server.origin}/"},
                {"kind": "click", "selector": "#external"},
            ]
            result = HarnessKernel().run(
                make_manifest(server.origin, actions),
                make_spec("browser-origin-denied"),
                LocalBrowserFixtureRuntime(Path(td)),
            )
            self.assertEqual(result.verdict.status, VerdictStatus.FAIL)
            self.assertEqual(result.verdict.security_gate, "fail")
            self.assertTrue(
                any(event.get("action") == "Denied" for event in result.evidence.network)
            )
            self.assertIn("security-gate", result.verdict.failed_check_ids)

    def test_independent_assertion_failure_fails_without_security_upgrade(self):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as td:
            actions = [
                {"kind": "goto", "url": f"{server.origin}/"},
                {
                    "kind": "assert_text",
                    "selector": "#result",
                    "value": "never-present",
                },
            ]
            result = HarnessKernel().run(
                make_manifest(server.origin, actions),
                make_spec("browser-assertion-fail"),
                LocalBrowserFixtureRuntime(Path(td)),
            )
            self.assertEqual(result.verdict.status, VerdictStatus.FAIL)
            self.assertEqual(result.verdict.security_gate, "pass")
            self.assertIn("domain:browser-outcome", result.verdict.failed_check_ids)

    def test_modified_artifact_is_rejected_before_verdict(self):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as td:
            manifest = make_manifest(server.origin, success_actions(server.origin))
            spec = make_spec("browser-artifact-tamper")
            runtime = LocalBrowserFixtureRuntime(Path(td))
            kernel = HarnessKernel()
            plan = kernel.compile(
                manifest,
                spec,
                capabilities=runtime.capabilities,
                available_evidence=runtime.evidence_kinds,
            )
            adapter = kernel.registry.require(manifest.execution.adapter)
            stdin = adapter.compile_stdin(manifest, spec)
            sandbox_id = runtime.prepare(spec)
            try:
                execution_id = runtime.execute(sandbox_id, plan.command, stdin=stdin)
                raw = runtime.collect(spec.run_id, execution_id)
                receipt = parse_browser_receipt(raw.stdout)
                artifact = receipt.artifacts[0]
                artifact_path = (
                    Path(td)
                    / manifest.browser.artifact_root
                    / spec.run_id
                    / artifact.path
                )
                artifact_path.write_bytes(artifact_path.read_bytes() + b"tampered")
                normalized = adapter.normalize_evidence(manifest, plan, raw)
                verdict = kernel.verify(manifest, plan, normalized)
            finally:
                runtime.destroy(sandbox_id)
            self.assertFalse(normalized.assertions["browser_artifacts_valid"])
            self.assertEqual(verdict.status, VerdictStatus.FAIL)
            self.assertIn("domain:browser-artifacts", verdict.failed_check_ids)


if __name__ == "__main__":
    unittest.main()
