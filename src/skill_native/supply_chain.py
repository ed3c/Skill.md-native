from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .provenance import ProvenanceRecord


@dataclass(frozen=True)
class SupplyChainEvidence:
    publisher: str | None
    publisher_evidence: str
    signature_status: str
    signature_subject: str | None
    sbom_format: str
    sbom_sha256: str
    sbom: dict[str, Any]


def build_cyclonedx_sbom(root: str | Path, provenance: ProvenanceRecord) -> dict[str, Any]:
    components = []
    for dependency_file in provenance.dependency_files:
        path = Path(root) / dependency_file
        components.append({
            "type": "file",
            "name": dependency_file,
            "hashes": [{"alg": "SHA-256", "content": hashlib.sha256(path.read_bytes()).hexdigest()}],
        })
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": provenance.entrypoint, "version": provenance.content_sha256}},
        "components": components,
    }


def build_supply_chain_evidence(
    root: str | Path,
    provenance: ProvenanceRecord,
    *,
    signature_status: str = "not_provided",
    signature_subject: str | None = None,
) -> SupplyChainEvidence:
    publishers = sorted({a.publisher for a in provenance.attestations if a.publisher})
    publisher = publishers[0] if len(publishers) == 1 else None
    publisher_evidence = "consistent" if len(publishers) == 1 else "missing" if not publishers else "conflicting"
    sbom = build_cyclonedx_sbom(root, provenance)
    encoded = json.dumps(sbom, sort_keys=True, separators=(",", ":")).encode()
    return SupplyChainEvidence(
        publisher=publisher,
        publisher_evidence=publisher_evidence,
        signature_status=signature_status,
        signature_subject=signature_subject,
        sbom_format="CycloneDX-1.6",
        sbom_sha256=hashlib.sha256(encoded).hexdigest(),
        sbom=sbom,
    )


def persist_supply_chain(evidence: SupplyChainEvidence, directory: str | Path) -> Path:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{evidence.sbom_sha256}.supply-chain.json"
    if not path.exists():
        path.write_text(json.dumps(asdict(evidence), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path
