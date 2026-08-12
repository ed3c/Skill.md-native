# Deterministic attestation fixture

`identity.json` is a signed identity **claim** used by the no-network CI fixture. The placeholder commit is immutable-shaped but does not represent a live GitHub OIDC verification.

The workflow generates an ephemeral Ed25519 development key, derives its key ID, creates a verifier-owned trust policy, signs the deterministic Run Artifact Bundle fixture, verifies the DSSE envelope, appends it to a local hash-chained Merkle log, and verifies the inclusion receipt.

No private key is committed. No runtime or model verification is inferred from the signature.
