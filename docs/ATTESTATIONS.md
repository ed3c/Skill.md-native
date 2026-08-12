# Run Artifact Attestations and Local Transparency Log v0.1

## Status

This increment adds cryptographic identity and publication evidence above the existing content-addressed `RunArtifactBundle`:

```text
RunArtifactBundle
      │ validate every nested digest and continuity edge
      ▼
in-toto-style RunArtifactStatement
      │ DSSE pre-authentication encoding
      ▼
Ed25519 DSSEEnvelope
      │ verifier-owned AttestationTrustPolicy
      ▼
AttestationVerificationReceipt
      │ append under an exclusive local file lock
      ▼
TransparencyLogEntry + Merkle inclusion receipt
```

The implementation provides local Ed25519 signing, policy verification, a hash-chained JSONL log, RFC 6962-style domain-separated Merkle hashing, checkpoints, and inclusion receipts. It does **not** claim Sigstore keyless identity, Fulcio/Rekor integration, hardware-backed keys, or a globally witnessed public transparency service.

## Trust states

These states are deliberately separate:

```text
content-addressed
  The bytes and nested relationships validate against their digests.

cryptographically signed
  An authorized Ed25519 key signed the exact DSSE payload.

policy verified
  The signer key and signed identity claims match verifier-owned policy.

transparency published
  The verified envelope digest was appended to a particular log prefix and has an inclusion receipt.

integration verified / runtime verified
  External source or isolated runtime evidence independently satisfies the repository's existing verification contract.
```

A signature or log entry never changes `HarnessVerdict`, `security_gate`, `rank_eligible`, or diagnostic score. A failed run remains failed after signing.

## Signed statement

The DSSE payload is an in-toto-style statement:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "run-artifact-bundle",
      "digest": {"sha256": "<bundle-digest>"}
    }
  ],
  "predicateType": "https://skill-native.dev/attestation/run-artifact/v1",
  "predicate": {
    "bundle_digest": "...",
    "authority_digest": "...",
    "plan_digest": "...",
    "evidence_digest": "...",
    "verdict_digest": "...",
    "graph_digest": "...",
    "replay_digest": "...",
    "trace_digest": "...",
    "scorecard_digest": "...",
    "rank_eligible": true,
    "outcome_status": "pass",
    "security_gate": "pass",
    "identity": {
      "issuer": "https://token.actions.githubusercontent.com",
      "subject": "repo:ed3c/Skill.md-native:ref:refs/heads/main",
      "repository": "ed3c/Skill.md-native",
      "workflow_ref": "ed3c/Skill.md-native/.github/workflows/unit.yml@<commit>",
      "commit_sha": "<commit>",
      "environment": "github-hosted"
    }
  }
}
```

Before signing, `RunArtifactBundle` is reconstructed through its strict Pydantic model. This revalidates every nested self-digest and cross-artifact continuity rule. A caller cannot sign a stale or internally inconsistent bundle by supplying a new top-level digest.

## DSSE and Ed25519

The envelope uses the standard DSSE shape:

```json
{
  "payloadType": "application/vnd.in-toto+json",
  "payload": "<canonical-base64>",
  "signatures": [
    {"keyid": "<sha256-raw-public-key>", "sig": "<base64-ed25519>"}
  ]
}
```

The signed bytes are:

```text
PAE(payloadType, payload)
= "DSSEv1 "
  + len(payloadType) + " " + payloadType + " "
  + len(payload) + " " + payload
```

Contract v1 accepts exactly one Ed25519 signature. `keyid` is derived from SHA-256 of the 32-byte raw Ed25519 public key; callers cannot choose an unrelated key label.

Development private keys are written with mode `0600` on POSIX systems. Loading a private key through a symlink or with group/other permissions fails closed. Private keys must remain in the trusted control plane and must never be mounted into an evaluated sandbox or copied into `EvidenceBundle`.

## Verifier-owned trust policy

Signed identity strings are claims, not independently verified workload identity. Trust comes from matching those signed claims and the derived key ID against a policy supplied by the verifier:

```json
{
  "schema_version": "1.0",
  "policy_id": "skill-native.ci",
  "allowed_key_ids": ["<derived-key-id>"],
  "expected_issuer": "https://token.actions.githubusercontent.com",
  "expected_subject": "repo:ed3c/Skill.md-native:ref:refs/heads/main",
  "expected_repository": "ed3c/Skill.md-native",
  "expected_workflow_ref": "ed3c/Skill.md-native/.github/workflows/unit.yml@<commit>",
  "expected_commit_sha": "<commit>",
  "require_rank_eligible": true,
  "policy_digest": "..."
}
```

Verification rejects:

- a public key whose derived ID differs from the envelope key ID;
- a key ID absent from `allowed_key_ids`;
- an invalid Ed25519 signature;
- a payload whose bundle, authority, plan, evidence, verdict, graph, replay, trace, or scorecard digest differs from the supplied bundle;
- an issuer, subject, repository, workflow reference, or commit that differs from policy;
- a non-rank-eligible bundle when policy explicitly requires rank eligibility.

Successful verification emits a self-validating `AttestationVerificationReceipt`. Failure raises an error rather than producing a provisional success receipt.

## Local transparency log

The log stores one canonical JSON object per line:

```text
sequence
previous_entry_digest
envelope_digest
statement_digest
bundle_digest
key_ids
verification_receipt_digest
entry_digest
```

Each entry commits to the previous entry. Sequence gaps, reorderings, duplicate envelope publication, changed fields, and invalid entry digests fail verification.

### Checkpoint

The adjacent checkpoint records:

```text
log_id
tree_size
Merkle root
head entry digest
checkpoint digest
```

Append holds an exclusive `fcntl` lock, verifies the existing log and checkpoint, writes and `fsync`s the new line, atomically replaces the checkpoint, and `fsync`s the parent directory where supported. Readers use a shared lock.

A missing or mismatched checkpoint detects ordinary mutation or truncation. The checkpoint is content-addressed, not signed or externally witnessed. An attacker able to rewrite the entire log and checkpoint can create a different internally consistent history. Production deployment must anchor checkpoints in an independent signed store, public transparency service, release artifact, or other witness.

## Merkle inclusion receipts

Leaves and internal nodes use domain separation:

```text
leaf = SHA256(0x00 || entry_digest_bytes)
node = SHA256(0x01 || left_hash || right_hash)
```

Tree splitting follows the largest-power-of-two recursive construction. An inclusion receipt contains the entry digest, leaf index, ordered left/right audit path, and checkpoint. Receipts for older prefixes remain verifiable after later appends because verification reconstructs the exact prefix named by the embedded checkpoint.

## CLI

### Generate a development key pair

```bash
skill-native-attest generate-key \
  --private-key /tmp/skill-native-signing.pem \
  --public-key /tmp/skill-native-signing.pub.pem
```

This command is for local and deterministic CI fixtures. It is not a substitute for workload identity, KMS, or HSM-backed production signing.

### Build a trust policy from public keys

```bash
skill-native-attest create-policy \
  --policy-id skill-native.ci \
  --public-key /tmp/skill-native-signing.pub.pem \
  --expected-issuer https://token.actions.githubusercontent.com \
  --expected-subject repo:ed3c/Skill.md-native:ref:refs/heads/main \
  --expected-repository ed3c/Skill.md-native \
  --expected-workflow-ref ed3c/Skill.md-native/.github/workflows/unit.yml@<commit> \
  --expected-commit-sha <commit> \
  --require-rank-eligible \
  --output /tmp/attestation-policy.json
```

### Sign and verify

```bash
skill-native-attest sign \
  --bundle /tmp/run-artifacts/<digest>/run-artifact-bundle.json \
  --identity examples/attestations/identity.json \
  --private-key /tmp/skill-native-signing.pem \
  --output /tmp/run-artifact.dsse.json

skill-native-attest verify \
  --bundle /tmp/run-artifacts/<digest>/run-artifact-bundle.json \
  --envelope /tmp/run-artifact.dsse.json \
  --public-key /tmp/skill-native-signing.pub.pem \
  --policy /tmp/attestation-policy.json \
  --output /tmp/attestation-verification.json
```

### Append and verify publication

```bash
skill-native-attest log-append \
  --bundle /tmp/run-artifacts/<digest>/run-artifact-bundle.json \
  --envelope /tmp/run-artifact.dsse.json \
  --public-key /tmp/skill-native-signing.pub.pem \
  --policy /tmp/attestation-policy.json \
  --log /tmp/run-artifacts-transparency.jsonl \
  --log-id skill-native.local \
  --receipt-output /tmp/inclusion-receipt.json

skill-native-attest log-verify \
  --log /tmp/run-artifacts-transparency.jsonl \
  --log-id skill-native.local

skill-native-attest receipt-verify \
  --log /tmp/run-artifacts-transparency.jsonl \
  --log-id skill-native.local \
  --receipt /tmp/inclusion-receipt.json
```

### Export schemas

```bash
skill-native-attest export-schemas /tmp/attestation-schemas
```

## Verification coverage

The focused suite covers:

- DSSE PAE and deterministic Ed25519 signatures for a fixed key/message;
- raw-public-key-derived key IDs;
- statement/bundle digest continuity;
- payload, signature, wrong-key, identity-policy, and nested-bundle tampering;
- preservation of a non-rank-eligible state after signing;
- private-key file mode and overwrite protection;
- hash-chain and Merkle inclusion verification;
- duplicate envelope rejection;
- line mutation, truncation, reordering, and receipt mismatch;
- deterministic schema export.

## Follow-on work

1. Replace development keys with Sigstore keyless or KMS/HSM-backed workload identity.
2. Sign and independently witness transparency checkpoints.
3. Publish checkpoints and inclusion evidence to a public append-only service.
4. Add provenance for public-key rotation, revocation, and trust-policy versions.
5. Export real OpenTelemetry/OpenInference spans while preserving the existing logical trace identity.
