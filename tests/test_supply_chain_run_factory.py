import tempfile
import unittest
from pathlib import Path

from skill_native.models import AgentRef, ModelRef, RuntimeRef, Scenario
from skill_native.provenance import SourceAttestation, build_provenance, provenance_digest
from skill_native.run_factory import run_spec_from_provenance
from skill_native.supply_chain import build_supply_chain_evidence


class SupplyChainRunFactoryTests(unittest.TestCase):
    def test_provenance_digest_is_injected_into_run_spec_and_sbom(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "SKILL.md").write_text("---\nname: demo\n---\nDo it.\n")
            (root / "requirements.txt").write_text("httpx==0.28.1\n")
            provenance = build_provenance(
                root,
                entrypoint="SKILL.md",
                attestation=SourceAttestation(
                    registry="github",
                    source_url="https://github.com/example/demo",
                    immutable_ref="a" * 40,
                    publisher="example",
                ),
            )
            spec = run_spec_from_provenance(
                provenance,
                source_url="https://github.com/example/demo",
                run_id="r1",
                agent=AgentRef(harness="codex", version="1"),
                model=ModelRef(provider="local", model="m", quota_class="local"),
                runtime=RuntimeRef(backend="fake", version="1", image_digest="sha256:x"),
                scenario=Scenario(id="s", task="t"),
            )
            self.assertEqual(spec.skill.provenance_digest, provenance_digest(provenance))
            self.assertEqual(spec.skill.commit_or_digest, "a" * 40)
            supply = build_supply_chain_evidence(root, provenance)
            self.assertEqual(supply.publisher_evidence, "consistent")
            self.assertEqual(supply.publisher, "example")
            self.assertEqual(supply.sbom_format, "CycloneDX-1.6")
            self.assertEqual(len(supply.sbom_sha256), 64)
            self.assertEqual(supply.sbom["components"][0]["name"], "requirements.txt")


if __name__ == "__main__":
    unittest.main()
