from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .run_artifact_common import canonical_digest

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_COMMIT_PATTERN = r"^[0-9a-f]{40}$"
_IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
_RUN_ARTIFACT_PREDICATE_TYPE = (
    "https://skill-native.dev/attestation/run-artifact/v1"
)
_DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"


class AttestationError(ValueError):
    """Raised when an attestation cannot be trusted or verified."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AttestationIdentity(_StrictModel):
    issuer: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    repository: str = Field(
        min_length=3,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    )
    workflow_ref: str = Field(
        min_length=1,
        pattern=(
            r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
            r"[A-Za-z0-9_./-]+@[0-9a-f]{40}$"
        ),
    )
    commit_sha: str = Field(pattern=_COMMIT_PATTERN)
    environment: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_workflow_repository(self) -> "AttestationIdentity":
        expected_prefix = f"{self.repository}/.github/workflows/"
        if not self.workflow_ref.startswith(expected_prefix):
            raise ValueError(
                "workflow_ref must name an immutable workflow in identity.repository"
            )
        workflow_commit = self.workflow_ref.rsplit("@", 1)[1]
        if workflow_commit != self.commit_sha:
            raise ValueError("workflow_ref commit must match identity.commit_sha")
        return self


class StatementSubject(_StrictModel):
    name: Literal["run-artifact-bundle"] = "run-artifact-bundle"
    digest: dict[str, str]

    @model_validator(mode="after")
    def validate_digest(self) -> "StatementSubject":
        if set(self.digest) != {"sha256"}:
            raise ValueError("statement subject must contain exactly one sha256 digest")
        value = self.digest["sha256"]
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("statement subject digest must be lowercase SHA-256")
        return self


class RunArtifactPredicate(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    bundle_digest: str = Field(pattern=_DIGEST_PATTERN)
    authority_digest: str = Field(pattern=_DIGEST_PATTERN)
    plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    evidence_digest: str = Field(pattern=_DIGEST_PATTERN)
    verdict_digest: str = Field(pattern=_DIGEST_PATTERN)
    graph_digest: str = Field(pattern=_DIGEST_PATTERN)
    replay_digest: str = Field(pattern=_DIGEST_PATTERN)
    trace_digest: str = Field(pattern=_DIGEST_PATTERN)
    scorecard_digest: str = Field(pattern=_DIGEST_PATTERN)
    rank_eligible: bool
    outcome_status: Literal["pass", "fail"]
    security_gate: Literal["pass", "fail"]
    identity: AttestationIdentity

    @model_validator(mode="after")
    def preserve_failure_state(self) -> "RunArtifactPredicate":
        if self.rank_eligible and (
            self.outcome_status != "pass" or self.security_gate != "pass"
        ):
            raise ValueError("rank-eligible predicate must preserve a passing bundle state")
        return self


class RunArtifactStatement(_StrictModel):
    statement_type: Literal[_IN_TOTO_STATEMENT_TYPE] = Field(
        default=_IN_TOTO_STATEMENT_TYPE,
        alias="_type",
    )
    subject: list[StatementSubject] = Field(min_length=1, max_length=1)
    predicate_type: Literal[_RUN_ARTIFACT_PREDICATE_TYPE] = Field(
        default=_RUN_ARTIFACT_PREDICATE_TYPE,
        alias="predicateType",
    )
    predicate: RunArtifactPredicate

    @model_validator(mode="after")
    def validate_subject_continuity(self) -> "RunArtifactStatement":
        if self.subject[0].digest["sha256"] != self.predicate.bundle_digest:
            raise ValueError("statement subject does not match predicate bundle digest")
        return self


class DSSESignature(_StrictModel):
    keyid: str = Field(pattern=_DIGEST_PATTERN)
    sig: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_signature_encoding(self) -> "DSSESignature":
        raw = _decode_canonical_base64(self.sig, "signature")
        if len(raw) != 64:
            raise ValueError("Ed25519 signature must be exactly 64 bytes")
        return self


class DSSEEnvelope(_StrictModel):
    payload_type: Literal[_DSSE_PAYLOAD_TYPE] = Field(
        default=_DSSE_PAYLOAD_TYPE,
        alias="payloadType",
    )
    payload: str = Field(min_length=1)
    signatures: list[DSSESignature] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def validate_payload(self) -> "DSSEEnvelope":
        raw = _decode_canonical_base64(self.payload, "payload")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("DSSE payload must be UTF-8 JSON") from exc
        statement = RunArtifactStatement.model_validate(value)
        canonical = json.dumps(
            statement.model_dump(mode="json", by_alias=True),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if raw != canonical:
            raise ValueError("DSSE statement payload must use canonical JSON encoding")
        return self


class AttestationTrustPolicy(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    allowed_key_ids: list[str] = Field(min_length=1)
    expected_issuer: str | None = Field(default=None, min_length=1)
    expected_subject: str | None = Field(default=None, min_length=1)
    expected_repository: str | None = Field(default=None, min_length=3)
    expected_workflow_ref: str | None = Field(default=None, min_length=1)
    expected_commit_sha: str | None = Field(default=None, pattern=_COMMIT_PATTERN)
    require_rank_eligible: bool = False
    policy_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_policy(self) -> "AttestationTrustPolicy":
        if self.allowed_key_ids != sorted(set(self.allowed_key_ids)):
            raise ValueError("allowed_key_ids must be sorted and unique")
        for key_id in self.allowed_key_ids:
            if len(key_id) != 64 or any(
                char not in "0123456789abcdef" for char in key_id
            ):
                raise ValueError("allowed key IDs must be lowercase SHA-256 digests")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"policy_digest"})
        )
        if expected != self.policy_digest:
            raise ValueError("policy digest does not match policy payload")
        return self


class AttestationVerificationReceipt(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    bundle_digest: str = Field(pattern=_DIGEST_PATTERN)
    statement_digest: str = Field(pattern=_DIGEST_PATTERN)
    envelope_digest: str = Field(pattern=_DIGEST_PATTERN)
    key_id: str = Field(pattern=_DIGEST_PATTERN)
    policy_digest: str = Field(pattern=_DIGEST_PATTERN)
    identity: AttestationIdentity
    rank_eligible: bool
    outcome_status: Literal["pass", "fail"]
    security_gate: Literal["pass", "fail"]
    checks: list[str] = Field(min_length=1)
    passed: Literal[True] = True
    receipt_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_receipt(self) -> "AttestationVerificationReceipt":
        if self.checks != sorted(set(self.checks)):
            raise ValueError("verification checks must be sorted and unique")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"receipt_digest"})
        )
        if expected != self.receipt_digest:
            raise ValueError("verification receipt digest does not match receipt payload")
        return self


def build_trust_policy(
    *,
    policy_id: str,
    allowed_key_ids: list[str],
    expected_issuer: str | None = None,
    expected_subject: str | None = None,
    expected_repository: str | None = None,
    expected_workflow_ref: str | None = None,
    expected_commit_sha: str | None = None,
    require_rank_eligible: bool = False,
) -> AttestationTrustPolicy:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "policy_id": policy_id,
        "allowed_key_ids": sorted(set(allowed_key_ids)),
        "expected_issuer": expected_issuer,
        "expected_subject": expected_subject,
        "expected_repository": expected_repository,
        "expected_workflow_ref": expected_workflow_ref,
        "expected_commit_sha": expected_commit_sha,
        "require_rank_eligible": require_rank_eligible,
    }
    return AttestationTrustPolicy.model_validate(
        {**payload, "policy_digest": canonical_digest(payload)}
    )


def export_attestation_schemas(output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    from .transparency_log import (
        TransparencyCheckpoint,
        TransparencyInclusionReceipt,
        TransparencyLogEntry,
    )

    schemas: dict[str, dict[str, Any]] = {
        "run-artifact-statement.schema.json": RunArtifactStatement.model_json_schema(
            by_alias=True
        ),
        "dsse-envelope.schema.json": DSSEEnvelope.model_json_schema(by_alias=True),
        "attestation-trust-policy.schema.json": AttestationTrustPolicy.model_json_schema(),
        "attestation-verification-receipt.schema.json": (
            AttestationVerificationReceipt.model_json_schema()
        ),
        "transparency-log-entry.schema.json": TransparencyLogEntry.model_json_schema(),
        "transparency-checkpoint.schema.json": TransparencyCheckpoint.model_json_schema(),
        "transparency-inclusion-receipt.schema.json": (
            TransparencyInclusionReceipt.model_json_schema()
        ),
    }
    result: dict[str, Path] = {}
    for name, schema in schemas.items():
        path = output / name
        path.write_text(
            json.dumps(schema, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        result[name] = path
    return result


def _decode_canonical_base64(value: str, name: str) -> bytes:
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(f"{name} must be canonical base64") from exc
    if base64.b64encode(raw).decode("ascii") != value:
        raise ValueError(f"{name} must use canonical padded base64")
    return raw


__all__ = [
    "_DSSE_PAYLOAD_TYPE",
    "AttestationError",
    "AttestationIdentity",
    "AttestationTrustPolicy",
    "AttestationVerificationReceipt",
    "DSSEEnvelope",
    "DSSESignature",
    "RunArtifactPredicate",
    "RunArtifactStatement",
    "StatementSubject",
    "build_trust_policy",
    "export_attestation_schemas",
]
