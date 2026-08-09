from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .models import EvidenceBundle, InferenceReceipt
from .policy import ReceiptLedger


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


def attach_run_receipts(bundle: EvidenceBundle, ledger: ReceiptLedger | None) -> EvidenceBundle:
    if ledger is None:
        return bundle
    receipts = [InferenceReceipt.model_validate(r) for r in ledger.for_run(bundle.run_id)]
    return bundle.model_copy(update={"inference": receipts})


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
