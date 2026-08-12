from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_NODE_ID_PATTERN = r"^sha256:[0-9a-f]{64}$"
_TRACE_ID_PATTERN = r"^[0-9a-f]{32}$"
_SPAN_ID_PATTERN = r"^[0-9a-f]{16}$"
_MUTABLE_REFS = frozenset({"main", "master", "head", "latest", "*", "unknown", "none", "pin_me"})
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_REF = re.compile(r"^git:[0-9a-f]{40}$")


class RunArtifactError(ValueError):
    """Raised when run artifacts cannot be derived without weakening trust."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def canonical_digest(value: Any) -> str:
    """Match the repository's canonical SHA-256 JSON encoding."""

    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _digest_ref(digest: str) -> str:
    return f"sha256:{digest}"


def _is_immutable_reference(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized or normalized in _MUTABLE_REFS:
        return False
    return bool(
        _HEX_40.fullmatch(normalized)
        or _HEX_64.fullmatch(normalized)
        or _SHA256_REF.fullmatch(normalized)
        or _GIT_REF.fullmatch(normalized)
    )


def _is_sha256_reference(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    return bool(_HEX_64.fullmatch(normalized) or _SHA256_REF.fullmatch(normalized))


def _json_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RunArtifactError(f"{name} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _require_str(value: Mapping[str, Any], key: str, name: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise RunArtifactError(f"{name}.{key} must be a non-empty string")
    return result


def _validate_content_digest(payload: Mapping[str, Any], field: str, name: str) -> str:
    observed = _require_str(payload, field, name)
    if not _HEX_64.fullmatch(observed):
        raise RunArtifactError(f"{name}.{field} must be a lowercase SHA-256 digest")
    expected = canonical_digest({key: value for key, value in payload.items() if key != field})
    if expected != observed:
        raise RunArtifactError(f"{name}.{field} does not match the payload")
    return observed


class AuthorityKind(str, Enum):
    OPERATOR = "operator"
    REPOSITORY = "repository"
    REGISTRY = "registry"


class TrustBasis(str, Enum):
    OPERATOR_APPROVED = "operator-approved"
    REPOSITORY_PINNED = "repository-pinned"
    REGISTRY_ATTESTED = "registry-attested"


class EvaluatorAuthority(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    authority_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    kind: AuthorityKind
    trust_basis: TrustBasis
    source_url: str = Field(min_length=1)
    commit_or_digest: str = Field(min_length=1)
    manifest_digest: str = Field(pattern=_DIGEST_PATTERN)
    evaluator_digest: str = Field(pattern=_DIGEST_PATTERN)
    authority_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_authority(self) -> "EvaluatorAuthority":
        if not _is_immutable_reference(self.commit_or_digest):
            raise ValueError("evaluator authority requires an immutable commit or digest")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"authority_digest"})
        )
        if expected != self.authority_digest:
            raise ValueError("authority digest does not match authority payload")
        return self


def build_evaluator_authority(
    *,
    authority_id: str,
    kind: AuthorityKind | str,
    trust_basis: TrustBasis | str,
    source_url: str,
    commit_or_digest: str,
    manifest_digest: str,
    evaluator_digest: str,
) -> EvaluatorAuthority:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "authority_id": authority_id,
        "kind": AuthorityKind(kind),
        "trust_basis": TrustBasis(trust_basis),
        "source_url": source_url,
        "commit_or_digest": commit_or_digest,
        "manifest_digest": manifest_digest,
        "evaluator_digest": evaluator_digest,
    }
    normalized = _json_payload(payload)
    return EvaluatorAuthority.model_validate(
        {**normalized, "authority_digest": canonical_digest(normalized)}
    )


class EvidenceGraphNode(_StrictModel):
    id: str = Field(pattern=_NODE_ID_PATTERN)
    kind: str = Field(min_length=1)
    payload_digest: str = Field(pattern=_DIGEST_PATTERN)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_node_id(self) -> "EvidenceGraphNode":
        expected = _digest_ref(
            canonical_digest(
                {
                    "kind": self.kind,
                    "payload_digest": self.payload_digest,
                    "attributes": self.attributes,
                }
            )
        )
        if expected != self.id:
            raise ValueError("evidence graph node id does not match node payload")
        return self


class EvidenceGraphEdge(_StrictModel):
    id: str = Field(pattern=_NODE_ID_PATTERN)
    source: str = Field(pattern=_NODE_ID_PATTERN)
    target: str = Field(pattern=_NODE_ID_PATTERN)
    relation: str = Field(min_length=1)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_edge_id(self) -> "EvidenceGraphEdge":
        expected = _digest_ref(
            canonical_digest(
                {
                    "source": self.source,
                    "target": self.target,
                    "relation": self.relation,
                    "attributes": self.attributes,
                }
            )
        )
        if expected != self.id:
            raise ValueError("evidence graph edge id does not match edge payload")
        return self


class EvidenceGraph(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    nodes: list[EvidenceGraphNode]
    edges: list[EvidenceGraphEdge]
    graph_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_graph(self) -> "EvidenceGraph":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("evidence graph node ids must be unique")
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("evidence graph edge ids must be unique")
        known = set(node_ids)
        dangling = [
            edge.id
            for edge in self.edges
            if edge.source not in known or edge.target not in known
        ]
        if dangling:
            raise ValueError("evidence graph contains dangling edges")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"graph_digest"})
        )
        if expected != self.graph_digest:
            raise ValueError("evidence graph digest does not match graph payload")
        return self


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_payload(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value
