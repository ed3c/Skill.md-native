import unittest
from pathlib import Path

import yaml
from pydantic import ValidationError

from skill_native.coding_contract import CodingAgentContract
from skill_native.harness_contract import HarnessContractError, HarnessManifest
from skill_native.harness_kernel import HarnessKernel
from skill_native.models import RunSpec


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "harnesses" / "coding-agent"


def base_contract(**overrides):
    values = {
        "driver": "generic",
        "driver_version": "1.0.0",
        "version_command": ["agent", "--version"],
        "test_commands": [["python3", "-m", "unittest"]],
    }
    values.update(overrides)
    return CodingAgentContract.model_validate(values)


class CodingContractSecurityTests(unittest.TestCase):
    def test_manifest_cannot_weaken_protected_or_ignored_paths(self):
        with self.assertRaises(ValidationError):
            base_contract(protected_change_globs=[])
        with self.assertRaises(ValidationError):
            base_contract(ignored_globs=["**"])

    def test_manifest_cannot_enable_raw_agent_output_retention(self):
        with self.assertRaises(ValidationError):
            base_contract(capture_agent_output_excerpts=True)

    def test_domain_evidence_is_not_globally_advertised(self):
        raw = yaml.safe_load((EXAMPLE / "harness.yaml").read_text(encoding="utf-8"))
        raw["execution"] = {"adapter": "coding.command.v1", "command": ["true"]}
        raw.pop("coding")
        manifest = HarnessManifest.model_validate(raw)
        spec = RunSpec.model_validate(
            yaml.safe_load((EXAMPLE / "run.fake.yaml").read_text(encoding="utf-8"))
        )
        with self.assertRaises(HarnessContractError):
            HarnessKernel().compile(manifest, spec)

    def test_task_placeholder_is_rejected_for_coding_agent(self):
        raw = yaml.safe_load((EXAMPLE / "harness.yaml").read_text(encoding="utf-8"))
        raw["execution"]["command"] = ["agent", "{task}"]
        manifest = HarnessManifest.model_validate(raw)
        spec = RunSpec.model_validate(
            yaml.safe_load((EXAMPLE / "run.fake.yaml").read_text(encoding="utf-8"))
        )
        with self.assertRaises(HarnessContractError):
            HarnessKernel().compile(manifest, spec)


if __name__ == "__main__":
    unittest.main()
