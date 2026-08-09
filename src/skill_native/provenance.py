from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class SourceAttestation:
    registry: str
    source_url: str
    immutable_ref: str
    publisher: str | None = None
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class ProvenanceRecord:
    content_sha256: str
    entrypoint: str
    license_expression: str | None
    license_status: str
    dependency_files: tuple[str, ...]
    attestations: tuple[SourceAttestation, ...]


def digest_tree(root: str | Path) -> str:
    root_path = Path(root)
    hasher = hashlib.sha256()
    for path in sorted(p for p in root_path.rglob("*") if p.is_file()):
        rel = path.relative_to(root_path).as_posix().encode()
        data = path.read_bytes()
        hasher.update(len(rel).to_bytes(8, "big"))
        hasher.update(rel)
        hasher.update(len(data).to_bytes(8, "big"))
        hasher.update(data)
    return hasher.hexdigest()


def discover_dependencies(root: str | Path) -> tuple[str, ...]:
    candidates = {
        "requirements.txt", "pyproject.toml", "package.json", "package-lock.json",
        "pnpm-lock.yaml", "yarn.lock", "Cargo.toml", "go.mod", "uv.lock",
    }
    root_path = Path(root)
    return tuple(sorted(p.relative_to(root_path).as_posix() for p in root_path.rglob("*") if p.is_file() and p.name in candidates))


def infer_license_evidence(root: str | Path) -> tuple[str | None, str]:
    root_path = Path(root)
    files = [p for p in root_path.iterdir() if p.is_file() and p.name.lower().startswith(("license", "copying"))]
    if not files:
        return None, "missing"
    if len(files) > 1:
        return None, "ambiguous"
    text = files[0].read_text(encoding="utf-8", errors="replace").lower()
    known = (("mit license", "MIT"), ("apache license", "Apache-2.0"), ("bsd 3-clause", "BSD-3-Clause"))
    matches = [spdx for needle, spdx in known if needle in text]
    if len(matches) == 1:
        return matches[0], "detected"
    return None, "unclassified"


def build_provenance(root: str | Path, *, entrypoint: str, attestation: SourceAttestation) -> ProvenanceRecord:
    if not attestation.immutable_ref or attestation.immutable_ref in {"main", "master", "HEAD", "latest"}:
        raise ValueError("mutable source refs cannot be benchmark provenance")
    license_expression, license_status = infer_license_evidence(root)
    return ProvenanceRecord(
        content_sha256=digest_tree(root),
        entrypoint=entrypoint,
        license_expression=license_expression,
        license_status=license_status,
        dependency_files=discover_dependencies(root),
        attestations=(attestation,),
    )


def merge_equivalent(records: list[ProvenanceRecord]) -> list[ProvenanceRecord]:
    by_digest: dict[str, ProvenanceRecord] = {}
    for record in records:
        existing = by_digest.get(record.content_sha256)
        if existing is None:
            by_digest[record.content_sha256] = record
            continue
        attestations = tuple(dict.fromkeys(existing.attestations + record.attestations))
        by_digest[record.content_sha256] = ProvenanceRecord(
            content_sha256=record.content_sha256,
            entrypoint=existing.entrypoint,
            license_expression=existing.license_expression,
            license_status=existing.license_status,
            dependency_files=existing.dependency_files,
            attestations=attestations,
        )
    return list(by_digest.values())
