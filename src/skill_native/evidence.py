from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .models import EvidenceBundle, InferenceReceipt
from .policy import ReceiptLedger


_EVIDENCE_CONTRACT_KEY = "evidence_contract"


def canonical_digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(data).hexdigest()


def evidence_object(kind: str, value: dict[str, Any]) -> dict[str, Any]:
    payload = {"kind": kind, "value": value}
    return {"evidence_id": canonical_digest(payload), **payload}


def index_evidence(bundle: EvidenceBundle) -> dict[str, dict[str, Any]]:
    objects: dict[str, dict[str, Any]] = {}
    groups: list[tuple[str, Iterable[dict[str, Any]]]] = [
        ("command", bundle.commands),
        ("process", bundle.processes),
        ("network", bundle.network),
        ("finding", bundle.findings),
        ("ocsf", bundle.ocsf_events),
    ]
    for kind, values in groups:
        for value in values:
            obj = evidence_object(kind, value)
            objects[obj["evidence_id"]] = obj
    if bundle.filesystem_before:
        obj = evidence_object("filesystem_before", bundle.filesystem_before)
        objects[obj["evidence_id"]] = obj
    if bundle.filesystem_after:
        obj = evidence_object("filesystem_after", bundle.filesystem_after)
        objects[obj["evidence_id"]] = obj
    return objects


def captured_evidence(bundle: EvidenceBundle) -> frozenset[str]:
    """Return evidence kinds explicitly attested as collected by the trusted adapter.

    Empty values such as a clean ``stderr`` or an empty network event stream are still
    valid evidence when the adapter records that the collector ran. The attestation is
    nested in runtime metadata so older EvidenceBundle payloads remain schema- and
    digest-compatible when loaded by newer code.
    """

    contract = bundle.runtime_metadata.get(_EVIDENCE_CONTRACT_KEY, {})
    values = contract.get("captured", []) if isinstance(contract, dict) else []
    if not isinstance(values, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(str(value) for value in values)


def mark_evidence_captured(
    bundle: EvidenceBundle,
    kinds: Iterable[str],
    *,
    runtime_backend: str | None = None,
) -> EvidenceBundle:
    metadata = dict(bundle.runtime_metadata)
    existing = captured_evidence(bundle)
    raw_contract = metadata.get(_EVIDENCE_CONTRACT_KEY)
    contract = dict(raw_contract) if isinstance(raw_contract, dict) else {}
    contract.update(
        {
            "schema_version": "1.0",
            "captured": sorted(existing.union(str(kind) for kind in kinds)),
        }
    )
    metadata[_EVIDENCE_CONTRACT_KEY] = contract
    if runtime_backend is not None:
        metadata["runtime_backend"] = runtime_backend
    return bundle.model_copy(update={"runtime_metadata": metadata})


def attach_run_receipts(bundle: EvidenceBundle, ledger: ReceiptLedger | None) -> EvidenceBundle:
    if ledger is None:
        return bundle
    receipts = [InferenceReceipt.model_validate(r) for r in ledger.read(run_id=bundle.run_id)]
    updated = bundle.model_copy(update={"inference": receipts})
    if receipts:
        updated = mark_evidence_captured(updated, ["inference"])
    return updated


@dataclass(frozen=True)
class EvidenceStore:
    root: Path

    def persist(self, bundle: EvidenceBundle) -> tuple[str, Path]:
        payload = bundle.model_dump(mode="json")
        digest = canonical_digest(payload)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{digest}.json"
        if not path.exists():
            path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return digest, path
