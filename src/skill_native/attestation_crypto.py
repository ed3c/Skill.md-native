from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .attestation_contract import (
    _DSSE_PAYLOAD_TYPE,
    AttestationError,
    AttestationIdentity,
    AttestationTrustPolicy,
    AttestationVerificationReceipt,
    DSSEEnvelope,
    DSSESignature,
    RunArtifactPredicate,
    RunArtifactStatement,
    StatementSubject,
)
from .run_artifact_bundle import RunArtifactBundle
from .run_artifact_common import canonical_digest


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return b" ".join(
        [
            b"DSSEv1",
            str(len(type_bytes)).encode("ascii"),
            type_bytes,
            str(len(payload)).encode("ascii"),
            payload,
        ]
    )


def canonical_statement_bytes(statement: RunArtifactStatement) -> bytes:
    return json.dumps(
        statement.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def envelope_digest(envelope: DSSEEnvelope) -> str:
    return canonical_digest(envelope.model_dump(mode="json", by_alias=True))


def statement_digest(statement: RunArtifactStatement) -> str:
    return hashlib.sha256(canonical_statement_bytes(statement)).hexdigest()


def key_id_for_public_key(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()


def generate_keypair(
    private_key_path: Path,
    public_key_path: Path,
    *,
    overwrite: bool = False,
) -> str:
    if private_key_path.resolve() == public_key_path.resolve():
        raise AttestationError("private and public key paths must be different")
    if not overwrite and (private_key_path.exists() or public_key_path.exists()):
        raise AttestationError("refusing to overwrite an existing key file")
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _write_key(
        private_key_path,
        private_bytes,
        mode=0o600,
        overwrite=overwrite,
    )
    _write_key(
        public_key_path,
        public_bytes,
        mode=0o644,
        overwrite=overwrite,
    )
    return key_id_for_public_key(public_key)


def load_private_key(path: Path) -> Ed25519PrivateKey:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise AttestationError(f"cannot open Ed25519 private key: {path}") from exc
    try:
        stat = os.fstat(descriptor)
        if os.name == "posix" and stat.st_mode & 0o077:
            raise AttestationError(
                "private key permissions must not grant group or other access"
            )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            payload = handle.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        value = serialization.load_pem_private_key(payload, password=None)
    except (ValueError, TypeError) as exc:
        raise AttestationError(f"cannot load Ed25519 private key: {path}") from exc
    if not isinstance(value, Ed25519PrivateKey):
        raise AttestationError("private key is not Ed25519")
    return value


def load_public_key(path: Path) -> Ed25519PublicKey:
    try:
        value = serialization.load_pem_public_key(path.read_bytes())
    except (OSError, ValueError, TypeError) as exc:
        raise AttestationError(f"cannot load Ed25519 public key: {path}") from exc
    if not isinstance(value, Ed25519PublicKey):
        raise AttestationError("public key is not Ed25519")
    return value


def build_statement(
    bundle: RunArtifactBundle | Mapping[str, Any],
    identity: AttestationIdentity | Mapping[str, Any],
) -> RunArtifactStatement:
    validated_bundle = _validate_bundle(bundle)
    identity_model = (
        identity
        if isinstance(identity, AttestationIdentity)
        else AttestationIdentity.model_validate(identity)
    )
    predicate = RunArtifactPredicate(
        bundle_digest=validated_bundle.bundle_digest,
        authority_digest=validated_bundle.authority.authority_digest,
        plan_digest=validated_bundle.plan_digest,
        evidence_digest=validated_bundle.evidence_digest,
        verdict_digest=validated_bundle.verdict_digest,
        graph_digest=validated_bundle.evidence_graph.graph_digest,
        replay_digest=validated_bundle.replay_manifest.replay_digest,
        trace_digest=validated_bundle.logical_trace.trace_digest,
        scorecard_digest=validated_bundle.scorecard.scorecard_digest,
        rank_eligible=validated_bundle.scorecard.rank_eligible,
        outcome_status=validated_bundle.scorecard.outcome_status,
        security_gate=validated_bundle.scorecard.security_gate,
        identity=identity_model,
    )
    return RunArtifactStatement(
        subject=[
            StatementSubject(
                digest={"sha256": validated_bundle.bundle_digest},
            )
        ],
        predicate=predicate,
    )


def sign_bundle(
    bundle: RunArtifactBundle | Mapping[str, Any],
    identity: AttestationIdentity | Mapping[str, Any],
    private_key: Ed25519PrivateKey,
) -> DSSEEnvelope:
    statement = build_statement(bundle, identity)
    payload = canonical_statement_bytes(statement)
    signature = private_key.sign(dsse_pae(_DSSE_PAYLOAD_TYPE, payload))
    return DSSEEnvelope(
        payload=base64.b64encode(payload).decode("ascii"),
        signatures=[
            DSSESignature(
                keyid=key_id_for_public_key(private_key.public_key()),
                sig=base64.b64encode(signature).decode("ascii"),
            )
        ],
    )


def parse_statement(envelope: DSSEEnvelope | Mapping[str, Any]) -> RunArtifactStatement:
    envelope_model = (
        envelope if isinstance(envelope, DSSEEnvelope) else DSSEEnvelope.model_validate(envelope)
    )
    payload = base64.b64decode(envelope_model.payload.encode("ascii"), validate=True)
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttestationError("DSSE payload is not a valid statement") from exc
    return RunArtifactStatement.model_validate(raw)


def verify_attestation(
    bundle: RunArtifactBundle | Mapping[str, Any],
    envelope: DSSEEnvelope | Mapping[str, Any],
    public_key: Ed25519PublicKey,
    policy: AttestationTrustPolicy | Mapping[str, Any],
) -> AttestationVerificationReceipt:
    validated_bundle = _validate_bundle(bundle)
    envelope_model = (
        envelope if isinstance(envelope, DSSEEnvelope) else DSSEEnvelope.model_validate(envelope)
    )
    policy_model = (
        policy
        if isinstance(policy, AttestationTrustPolicy)
        else AttestationTrustPolicy.model_validate(policy)
    )
    statement = parse_statement(envelope_model)
    _validate_statement_bundle_continuity(statement, validated_bundle)

    key_id = key_id_for_public_key(public_key)
    signature = envelope_model.signatures[0]
    if signature.keyid != key_id:
        raise AttestationError("DSSE signature key ID does not match the public key")
    if key_id not in policy_model.allowed_key_ids:
        raise AttestationError("signing key is not authorized by the trust policy")

    payload = base64.b64decode(envelope_model.payload.encode("ascii"), validate=True)
    signature_bytes = base64.b64decode(signature.sig.encode("ascii"), validate=True)
    try:
        public_key.verify(
            signature_bytes,
            dsse_pae(envelope_model.payload_type, payload),
        )
    except InvalidSignature as exc:
        raise AttestationError("DSSE signature verification failed") from exc

    identity = statement.predicate.identity
    checks = [
        "bundle-continuity",
        "dsse-signature",
        "key-id-derived",
        "policy-key-authorized",
        "statement-predicate-continuity",
    ]
    identity_fields = {
        "issuer": policy_model.expected_issuer,
        "subject": policy_model.expected_subject,
        "repository": policy_model.expected_repository,
        "workflow_ref": policy_model.expected_workflow_ref,
        "commit_sha": policy_model.expected_commit_sha,
    }
    for field, expected in identity_fields.items():
        if expected is None:
            continue
        observed = getattr(identity, field)
        if observed != expected:
            raise AttestationError(
                f"signed identity {field} does not match trust policy"
            )
        checks.append(f"identity:{field}")
    if policy_model.require_rank_eligible:
        if not statement.predicate.rank_eligible:
            raise AttestationError("trust policy requires a rank-eligible bundle")
        checks.append("rank-eligible-required")

    statement_hash = statement_digest(statement)
    envelope_hash = envelope_digest(envelope_model)
    receipt_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "bundle_digest": validated_bundle.bundle_digest,
        "statement_digest": statement_hash,
        "envelope_digest": envelope_hash,
        "key_id": key_id,
        "policy_digest": policy_model.policy_digest,
        "identity": identity,
        "rank_eligible": statement.predicate.rank_eligible,
        "outcome_status": statement.predicate.outcome_status,
        "security_gate": statement.predicate.security_gate,
        "checks": sorted(set(checks)),
        "passed": True,
    }
    normalized = _json_payload(receipt_payload)
    return AttestationVerificationReceipt.model_validate(
        {**normalized, "receipt_digest": canonical_digest(normalized)}
    )


def _validate_statement_bundle_continuity(
    statement: RunArtifactStatement,
    bundle: RunArtifactBundle,
) -> None:
    predicate = statement.predicate
    expected = {
        "bundle_digest": bundle.bundle_digest,
        "authority_digest": bundle.authority.authority_digest,
        "plan_digest": bundle.plan_digest,
        "evidence_digest": bundle.evidence_digest,
        "verdict_digest": bundle.verdict_digest,
        "graph_digest": bundle.evidence_graph.graph_digest,
        "replay_digest": bundle.replay_manifest.replay_digest,
        "trace_digest": bundle.logical_trace.trace_digest,
        "scorecard_digest": bundle.scorecard.scorecard_digest,
        "rank_eligible": bundle.scorecard.rank_eligible,
        "outcome_status": bundle.scorecard.outcome_status,
        "security_gate": bundle.scorecard.security_gate,
    }
    for field, value in expected.items():
        if getattr(predicate, field) != value:
            raise AttestationError(
                f"statement predicate {field} does not match Run Artifact Bundle"
            )
    if statement.subject[0].digest["sha256"] != bundle.bundle_digest:
        raise AttestationError("statement subject does not match Run Artifact Bundle")


def _validate_bundle(
    bundle: RunArtifactBundle | Mapping[str, Any],
) -> RunArtifactBundle:
    try:
        if isinstance(bundle, RunArtifactBundle):
            return RunArtifactBundle.model_validate(bundle.model_dump(mode="json"))
        return RunArtifactBundle.model_validate(bundle)
    except Exception as exc:  # Pydantic raises a structured ValidationError.
        raise AttestationError("Run Artifact Bundle failed digest/continuity validation") from exc


def _write_key(
    path: Path,
    payload: bytes,
    *,
    mode: int,
    overwrite: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise AttestationError("refusing to write a key through a symlink")
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if overwrite else os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, mode)
    except OSError as exc:
        raise AttestationError(f"cannot create key file: {path}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        try:
            os.chmod(path, mode)
        except OSError:
            pass


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseException):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_payload(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_payload(child) for child in value]
    return value


__all__ = [
    "build_statement",
    "canonical_statement_bytes",
    "dsse_pae",
    "envelope_digest",
    "generate_keypair",
    "key_id_for_public_key",
    "load_private_key",
    "load_public_key",
    "parse_statement",
    "sign_bundle",
    "statement_digest",
    "verify_attestation",
]
