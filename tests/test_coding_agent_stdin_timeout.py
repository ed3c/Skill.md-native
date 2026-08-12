from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from skill_native.coding_agent import _run_process


class CodingAgentStdinTimeoutTests(unittest.TestCase):
    def test_timeout_covers_child_that_never_reads_large_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            started = time.monotonic()
            result = _run_process(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=Path(td),
                input_text="x" * (2 * 1024 * 1024),
                timeout_seconds=1,
                max_capture_bytes=1024,
            )
            elapsed = time.monotonic() - started

        self.assertTrue(result.timed_out)
        self.assertLess(elapsed, 8.0)

    def test_normal_stdin_delivery_remains_successful(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = _run_process(
                [
                    sys.executable,
                    "-c",
                    "import sys; data=sys.stdin.buffer.read(); print(len(data))",
                ],
                cwd=Path(td),
                input_text="hello",
                timeout_seconds=5,
                max_capture_bytes=1024,
            )

        self.assertFalse(result.timed_out)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout.strip(), "5")
        self.assertTrue(result.process_tree_terminated)


if __name__ == "__main__":
    unittest.main()
