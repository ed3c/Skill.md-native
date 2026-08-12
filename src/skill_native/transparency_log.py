from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .attestation_contract import (
    AttestationError,
    AttestationVerificationReceipt,
    DSSEEnvelope,
)
from .attestation_crypto import envelope_digest, parse_statement, statement_digest
from .run_artifact_common import canonical_digest

try:
    import fcntl
except ImportError:  # pragma: no cover - local append is declared unsupported.
    fcntl = None

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TransparencyLogEntry(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    log_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    sequence: int = Field(ge=0)
    previous_entry_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    envelope_digest: str = Field(pattern=_DIGEST_PATTERN)
    statement_digest: str = Field(pattern=_DIGEST_PATTERN)
    bundle_digest: str = Field(pattern=_DIGEST_PATTERN)
    key_ids: list[str] = Field(min_length=1)
    verification_receipt_digest: str = Field(pattern=_DIGEST_PATTERN)
    entry_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_entry(self) -> "TransparencyLogEntry":
        if self.sequence == 0 and self.previous_entry_digest is not None:
            raise ValueError("first transparency entry must not have a previous digest")
        if self.sequence > 0 and self.previous_entry_digest is None:
            raise ValueError("non-first transparency entry requires a previous digest")
        if self.key_ids != sorted(set(self.key_ids)):
            raise ValueError("transparency entry key IDs must be sorted and unique")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"entry_digest"})
        )
        if expected != self.entry_digest:
            raise ValueError("transparency entry digest does not match entry payload")
        return self


class MerklePathNode(_StrictModel):
    side: Literal["left", "right"]
    digest: str = Field(pattern=_DIGEST_PATTERN)


class TransparencyCheckpoint(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    log_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    tree_size: int = Field(ge=0)
    root_hash: str = Field(pattern=_DIGEST_PATTERN)
    head_entry_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    checkpoint_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_checkpoint(self) -> "TransparencyCheckpoint":
        if self.tree_size == 0 and self.head_entry_digest is not None:
            raise ValueError("empty checkpoint must not have a head entry")
        if self.tree_size > 0 and self.head_entry_digest is None:
            raise ValueError("non-empty checkpoint requires a head entry")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"checkpoint_digest"})
        )
        if expected != self.checkpoint_digest:
            raise ValueError("checkpoint digest does not match checkpoint payload")
        return self


class TransparencyInclusionReceipt(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    log_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    leaf_index: int = Field(ge=0)
    entry_digest: str = Field(pattern=_DIGEST_PATTERN)
    leaf_hash: str = Field(pattern=_DIGEST_PATTERN)
    path: list[MerklePathNode]
    checkpoint: TransparencyCheckpoint
    receipt_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_receipt(self) -> "TransparencyInclusionReceipt":
        if self.log_id != self.checkpoint.log_id:
            raise ValueError("receipt log ID does not match checkpoint")
        if self.leaf_index >= self.checkpoint.tree_size:
            raise ValueError("receipt leaf index is outside the checkpoint tree")
        expected_leaf = _leaf_hash(self.entry_digest)
        if self.leaf_hash != expected_leaf:
            raise ValueError("receipt leaf hash does not match entry digest")
        root = self.leaf_hash
        for node in self.path:
            root = (
                _node_hash(node.digest, root)
                if node.side == "left"
                else _node_hash(root, node.digest)
            )
        if root != self.checkpoint.root_hash:
            raise ValueError("receipt path does not reach checkpoint root")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"receipt_digest"})
        )
        if expected != self.receipt_digest:
            raise ValueError("inclusion receipt digest does not match receipt payload")
        return self


@dataclass(frozen=True)
class TransparencyLogVerification:
    log_id: str
    tree_size: int
    root_hash: str
    head_entry_digest: str | None
    checkpoint_digest: str


class TransparencyLog:
    def __init__(self, path: Path, *, log_id: str = "skill-native.local") -> None:
        self.path = path
        self.log_id = log_id
        self.checkpoint_path = Path(f"{path}.checkpoint.json")
        self.lock_path = Path(f"{path}.lock")

    def append(
        self,
        envelope: DSSEEnvelope | Mapping[str, Any],
        verification_receipt: AttestationVerificationReceipt | Mapping[str, Any],
    ) -> TransparencyInclusionReceipt:
        if fcntl is None:
            raise AttestationError(
                "atomic transparency append requires fcntl on this platform"
            )
        envelope_model = (
            envelope
            if isinstance(envelope, DSSEEnvelope)
            else DSSEEnvelope.model_validate(envelope)
        )
        verification = (
            verification_receipt
            if isinstance(verification_receipt, AttestationVerificationReceipt)
            else AttestationVerificationReceipt.model_validate(verification_receipt)
        )
        envelope_hash = envelope_digest(envelope_model)
        statement = parse_statement(envelope_model)
        statement_hash = statement_digest(statement)
        if verification.envelope_digest != envelope_hash:
            raise AttestationError("verification receipt does not match DSSE envelope")
        if verification.statement_digest != statement_hash:
            raise AttestationError("verification receipt does not match statement")
        if verification.bundle_digest != statement.predicate.bundle_digest:
            raise AttestationError("verification receipt does not match bundle predicate")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            entries, _ = self._verify_unlocked(allow_missing_empty_checkpoint=True)
            if any(entry.envelope_digest == envelope_hash for entry in entries):
                raise AttestationError("duplicate DSSE envelope publication is rejected")
            previous = entries[-1].entry_digest if entries else None
            entry_payload: dict[str, Any] = {
                "schema_version": "1.0",
                "log_id": self.log_id,
                "sequence": len(entries),
                "previous_entry_digest": previous,
                "envelope_digest": envelope_hash,
                "statement_digest": statement_hash,
                "bundle_digest": verification.bundle_digest,
                "key_ids": sorted(
                    signature.keyid for signature in envelope_model.signatures
                ),
                "verification_receipt_digest": verification.receipt_digest,
            }
            entry = TransparencyLogEntry.model_validate(
                {
                    **entry_payload,
                    "entry_digest": canonical_digest(entry_payload),
                }
            )
            encoded = _canonical_line(entry)
            with self.path.open("ab") as log_handle:
                log_handle.write(encoded)
                log_handle.flush()
                os.fsync(log_handle.fileno())
            entries.append(entry)
            checkpoint = _build_checkpoint(self.log_id, entries)
            _atomic_write_json(self.checkpoint_path, checkpoint.model_dump(mode="json"))
            _fsync_directory(self.path.parent)
            receipt = _build_inclusion_receipt(entries, entry.sequence, checkpoint)
            return receipt

    def verify(self) -> TransparencyLogVerification:
        if fcntl is None:
            raise AttestationError(
                "atomic transparency verification requires fcntl on this platform"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_SH)
            entries, checkpoint = self._verify_unlocked()
            return TransparencyLogVerification(
                log_id=self.log_id,
                tree_size=len(entries),
                root_hash=checkpoint.root_hash,
                head_entry_digest=checkpoint.head_entry_digest,
                checkpoint_digest=checkpoint.checkpoint_digest,
            )

    def verify_receipt(
        self,
        receipt: TransparencyInclusionReceipt | Mapping[str, Any],
    ) -> bool:
        receipt_model = (
            receipt
            if isinstance(receipt, TransparencyInclusionReceipt)
            else TransparencyInclusionReceipt.model_validate(receipt)
        )
        if receipt_model.log_id != self.log_id:
            raise AttestationError("inclusion receipt belongs to a different log")
        if fcntl is None:
            raise AttestationError(
                "atomic transparency verification requires fcntl on this platform"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_SH)
            entries = self._read_entries()
            if receipt_model.checkpoint.tree_size > len(entries):
                raise AttestationError("receipt checkpoint exceeds available log entries")
            prefix = entries[: receipt_model.checkpoint.tree_size]
            _validate_entry_chain(self.log_id, prefix)
            expected_checkpoint = _build_checkpoint(self.log_id, prefix)
            if expected_checkpoint != receipt_model.checkpoint:
                raise AttestationError("receipt checkpoint does not match log prefix")
            entry = prefix[receipt_model.leaf_index]
            if entry.entry_digest != receipt_model.entry_digest:
                raise AttestationError("receipt entry digest does not match log entry")
            expected = _build_inclusion_receipt(
                prefix,
                receipt_model.leaf_index,
                expected_checkpoint,
            )
            if expected != receipt_model:
                raise AttestationError("receipt Merkle path does not match log prefix")
            return True

    def _verify_unlocked(
        self,
        *,
        allow_missing_empty_checkpoint: bool = False,
    ) -> tuple[list[TransparencyLogEntry], TransparencyCheckpoint]:
        entries = self._read_entries()
        _validate_entry_chain(self.log_id, entries)
        expected = _build_checkpoint(self.log_id, entries)
        if not self.checkpoint_path.exists():
            if entries or not allow_missing_empty_checkpoint:
                raise AttestationError("transparency checkpoint is missing")
            return entries, expected
        try:
            raw = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            observed = TransparencyCheckpoint.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise AttestationError("transparency checkpoint is invalid") from exc
        if observed != expected:
            raise AttestationError(
                "transparency log does not match checkpoint; mutation or truncation detected"
            )
        return entries, observed

    def _read_entries(self) -> list[TransparencyLogEntry]:
        if not self.path.exists():
            return []
        entries: list[TransparencyLogEntry] = []
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.endswith("\n"):
                        raise AttestationError(
                            f"transparency line {line_number} is truncated"
                        )
                    if not line.strip():
                        raise AttestationError(
                            f"transparency line {line_number} is empty"
                        )
                    raw = json.loads(line)
                    entries.append(TransparencyLogEntry.model_validate(raw))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            if isinstance(exc, AttestationError):
                raise
            raise AttestationError("transparency log contains an invalid entry") from exc
        return entries


def _validate_entry_chain(log_id: str, entries: list[TransparencyLogEntry]) -> None:
    envelopes: set[str] = set()
    previous: str | None = None
    for index, entry in enumerate(entries):
        if entry.log_id != log_id:
            raise AttestationError("transparency entry belongs to a different log")
        if entry.sequence != index:
            raise AttestationError("transparency sequence is missing or reordered")
        if entry.previous_entry_digest != previous:
            raise AttestationError("transparency previous-entry chain is broken")
        if entry.envelope_digest in envelopes:
            raise AttestationError("transparency log contains a duplicate envelope")
        envelopes.add(entry.envelope_digest)
        previous = entry.entry_digest


def _build_checkpoint(
    log_id: str,
    entries: list[TransparencyLogEntry],
) -> TransparencyCheckpoint:
    entry_digests = [entry.entry_digest for entry in entries]
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "log_id": log_id,
        "tree_size": len(entries),
        "root_hash": _merkle_root(entry_digests),
        "head_entry_digest": entries[-1].entry_digest if entries else None,
    }
    return TransparencyCheckpoint.model_validate(
        {**payload, "checkpoint_digest": canonical_digest(payload)}
    )


def _build_inclusion_receipt(
    entries: list[TransparencyLogEntry],
    leaf_index: int,
    checkpoint: TransparencyCheckpoint,
) -> TransparencyInclusionReceipt:
    entry_digests = [entry.entry_digest for entry in entries]
    path = _merkle_path(entry_digests, leaf_index)
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "log_id": checkpoint.log_id,
        "leaf_index": leaf_index,
        "entry_digest": entries[leaf_index].entry_digest,
        "leaf_hash": _leaf_hash(entries[leaf_index].entry_digest),
        "path": [node.model_dump(mode="json") for node in path],
        "checkpoint": checkpoint.model_dump(mode="json"),
    }
    return TransparencyInclusionReceipt.model_validate(
        {**payload, "receipt_digest": canonical_digest(payload)}
    )


def _leaf_hash(entry_digest: str) -> str:
    return hashlib.sha256(b"\x00" + bytes.fromhex(entry_digest)).hexdigest()


def _node_hash(left: str, right: str) -> str:
    return hashlib.sha256(
        b"\x01" + bytes.fromhex(left) + bytes.fromhex(right)
    ).hexdigest()


def _merkle_root(entry_digests: list[str]) -> str:
    if not entry_digests:
        return hashlib.sha256(b"").hexdigest()
    if len(entry_digests) == 1:
        return _leaf_hash(entry_digests[0])
    split = _largest_power_of_two_less_than(len(entry_digests))
    return _node_hash(
        _merkle_root(entry_digests[:split]),
        _merkle_root(entry_digests[split:]),
    )


def _merkle_path(entry_digests: list[str], index: int) -> list[MerklePathNode]:
    if not 0 <= index < len(entry_digests):
        raise AttestationError("Merkle leaf index is outside the tree")
    if len(entry_digests) == 1:
        return []
    split = _largest_power_of_two_less_than(len(entry_digests))
    if index < split:
        return _merkle_path(entry_digests[:split], index) + [
            MerklePathNode(
                side="right",
                digest=_merkle_root(entry_digests[split:]),
            )
        ]
    return _merkle_path(entry_digests[split:], index - split) + [
        MerklePathNode(
            side="left",
            digest=_merkle_root(entry_digests[:split]),
        )
    ]


def _largest_power_of_two_less_than(value: int) -> int:
    if value <= 1:
        raise ValueError("Merkle split requires at least two leaves")
    return 1 << ((value - 1).bit_length() - 1)


def _canonical_line(entry: TransparencyLogEntry) -> bytes:
    return (
        json.dumps(
            entry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "MerklePathNode",
    "TransparencyCheckpoint",
    "TransparencyInclusionReceipt",
    "TransparencyLog",
    "TransparencyLogEntry",
    "TransparencyLogVerification",
]
