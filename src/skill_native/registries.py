from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .provenance import ProvenanceRecord, SourceAttestation, build_provenance


@dataclass(frozen=True)
class RegistrySkill:
    registry: str
    stable_id: str
    source_url: str
    content_hash: str | None
    files: tuple[tuple[str, str], ...]
    metadata: dict[str, Any]

    def materialize(self, destination: str | Path | None = None) -> Path:
        root = Path(destination) if destination else Path(tempfile.mkdtemp(prefix="skill-native-registry-"))
        root.mkdir(parents=True, exist_ok=True)
        for rel, contents in self.files:
            path = root / rel
            resolved = path.resolve()
            if root.resolve() not in resolved.parents and resolved != root.resolve():
                raise ValueError("registry file path escapes destination")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
        return root


class SkillsShAdapter:
    """Authenticated adapter for the documented skills.sh v1 API."""

    def __init__(self, client: httpx.Client | None = None, token_env: str = "VERCEL_OIDC_TOKEN") -> None:
        self.client = client or httpx.Client(timeout=30.0)
        self.token_env = token_env
        self.base_url = "https://skills.sh/api/v1"

    def _headers(self) -> dict[str, str]:
        token = os.getenv(self.token_env)
        if not token:
            raise RuntimeError(f"missing {self.token_env}; skills.sh API requires Vercel OIDC")
        return {"authorization": f"Bearer {token}"}

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.base_url}/skills/search",
            params={"q": query, "limit": limit},
            headers=self._headers(),
        )
        response.raise_for_status()
        body = response.json()
        return list(body.get("data", []))

    def fetch(self, stable_id: str) -> RegistrySkill:
        response = self.client.get(f"{self.base_url}/skills/{stable_id}", headers=self._headers())
        response.raise_for_status()
        body = response.json()
        files = tuple((str(f["path"]), str(f["contents"])) for f in body.get("files") or [])
        if not files:
            raise RuntimeError("skills.sh detail has no materialized files")
        return RegistrySkill(
            registry="skills.sh",
            stable_id=stable_id,
            source_url=str(body.get("source", stable_id)),
            content_hash=body.get("hash"),
            files=files,
            metadata={k: v for k, v in body.items() if k != "files"},
        )

    def audit(self, stable_id: str) -> dict[str, Any]:
        response = self.client.get(f"{self.base_url}/skills/audit/{stable_id}", headers=self._headers())
        response.raise_for_status()
        return dict(response.json())

    def provenance(self, skill: RegistrySkill, destination: str | Path | None = None) -> ProvenanceRecord:
        root = skill.materialize(destination)
        immutable = skill.content_hash
        if not immutable:
            raise RuntimeError("skills.sh snapshot lacks immutable content hash")
        attestation = SourceAttestation(
            registry="skills.sh",
            source_url=skill.source_url,
            immutable_ref=immutable,
            publisher=skill.metadata.get("source"),
        )
        return build_provenance(root, entrypoint="SKILL.md", attestation=attestation)


@dataclass(frozen=True)
class ExternalMetadataRecord:
    registry: str
    stable_id: str
    metadata_url: str
    metadata: dict[str, Any]
    immutable_digest: str


class JsonMetadataAdapter:
    """Generic metadata ingestion for registries without a documented public catalog API.

    It never scrapes authenticated UI. The caller supplies an accessible JSON export
    or first-party manifest URL, which is fetched and digest-pinned as evidence.
    This is the supported path for OpenAI Plugin metadata until OpenAI documents a
    public Plugin Directory catalog API.
    """

    def __init__(self, registry: str, client: httpx.Client | None = None) -> None:
        self.registry = registry
        self.client = client or httpx.Client(timeout=30.0, follow_redirects=True)

    def fetch(self, stable_id: str, metadata_url: str) -> ExternalMetadataRecord:
        response = self.client.get(metadata_url)
        response.raise_for_status()
        body = response.json()
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        import hashlib
        digest = hashlib.sha256(canonical).hexdigest()
        return ExternalMetadataRecord(
            registry=self.registry,
            stable_id=stable_id,
            metadata_url=metadata_url,
            metadata=dict(body),
            immutable_digest=digest,
        )
