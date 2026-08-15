from __future__ import annotations

import importlib.metadata
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, sentinel

from skill_native.browser_adapter import BrowserPlaywrightAdapter
from skill_native.evidence import EvidenceStore
from skill_native.harness_kernel import (
    HarnessKernel,
    HarnessVerdictStore,
    _HarnessKernel,
)


class PackagingEntrypointTests(unittest.TestCase):
    def test_browser_runner_console_script_matches_stdin_adapter_contract(self) -> None:
        scripts = {
            entry.name: entry.value
            for entry in importlib.metadata.entry_points(group="console_scripts")
        }
        self.assertEqual(
            BrowserPlaywrightAdapter.runner_binary,
            "skill-native-browser-runner",
        )
        self.assertEqual(
            scripts.get(BrowserPlaywrightAdapter.runner_binary),
            "skill_native.browser_entrypoint:main",
        )

    def test_harness_kernel_preserves_legacy_registry_alias(self) -> None:
        kernel = HarnessKernel()
        self.assertIs(kernel.adapters, kernel.registry)

    def test_harness_kernel_translates_legacy_output_directories(self) -> None:
        kernel = HarnessKernel()
        with tempfile.TemporaryDirectory(prefix="skill-native-kernel-compat-") as temp:
            root = Path(temp)
            with patch.object(
                _HarnessKernel,
                "run",
                return_value=sentinel.result,
            ) as core_run:
                result = kernel.run(
                    sentinel.manifest,
                    sentinel.spec,
                    sentinel.runtime,
                    evidence_dir=root / "evidence",
                    verdict_dir=root / "verdicts",
                )
        self.assertIs(result, sentinel.result)
        kwargs = core_run.call_args.kwargs
        self.assertIsInstance(kwargs["evidence_store"], EvidenceStore)
        self.assertEqual(kwargs["evidence_store"].root, root / "evidence")
        self.assertIsInstance(kwargs["verdict_store"], HarnessVerdictStore)
        self.assertEqual(kwargs["verdict_store"].root, root / "verdicts")

    def test_harness_kernel_rejects_ambiguous_store_arguments(self) -> None:
        kernel = HarnessKernel()
        with tempfile.TemporaryDirectory(prefix="skill-native-kernel-compat-") as temp:
            root = Path(temp)
            with self.assertRaisesRegex(TypeError, "either evidence_dir or evidence_store"):
                kernel.run(
                    sentinel.manifest,
                    sentinel.spec,
                    sentinel.runtime,
                    evidence_dir=root / "legacy",
                    evidence_store=EvidenceStore(root / "current"),
                )


if __name__ == "__main__":
    unittest.main()
