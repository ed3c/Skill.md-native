import unittest

from skill_native.harness import HarnessKernel, VerdictStatus
from skill_native.runtime import FakeRuntime
from tests.test_harness_kernel import make_manifest, make_spec


class LegacyFakeRuntime(FakeRuntime):
    """Represents a pre-stdin third-party RuntimeAdapter implementation."""

    def execute(self, sandbox_id: str, command: list[str]) -> str:
        return super().execute(sandbox_id, command)


class RuntimeAdapterCompatibilityTests(unittest.TestCase):
    def test_command_adapter_preserves_legacy_execute_signature(self):
        result = HarnessKernel().run(
            make_manifest(),
            make_spec(),
            LegacyFakeRuntime(),
        )
        self.assertEqual(result.verdict.status, VerdictStatus.PASS)


if __name__ == "__main__":
    unittest.main()
