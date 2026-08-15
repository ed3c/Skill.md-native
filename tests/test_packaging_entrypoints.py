from __future__ import annotations

import importlib.metadata
import unittest

from skill_native.browser_adapter import BrowserPlaywrightAdapter


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


if __name__ == "__main__":
    unittest.main()
