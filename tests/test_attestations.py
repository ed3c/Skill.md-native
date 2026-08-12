import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from skill_native.attestations import (
    AttestationError,
    AttestationIdentity,
    DSSEEnvelope,
    TransparencyInclusionReceipt,
    TransparencyLog,
    build_trust_policy,
    dsse_pae,
    export_attestation_schemas,
    generate_keypair,
    key_id_for_public_key,
    load_private_key,
    load_public_key,
    parse_statement,
    sign_bundle,
    verify_attestation,
)
from skill_native.run_artifact_builder import RunArtifactBuilder
from skill_native.run_artifact_common import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "run-artifacts"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_bundle(*, remove_captured_stderr: bool = False):
    authority = _load(FIXTURE / "authority.json")
    plan = _load(FIXTURE / "plan.json")
    evidence = _load(FIXTURE / "evidence.json")
    verdict = _load(FIXTURE / "verdict.json")
    if remove_captured_stderr:
        captured = evidence["runtime_metadata"]["evidence_contract"]["captured"]
        evidence["runtime_metadata"]["evidence_contract"]["captured"] = [
            value for value in captured if value != "stderr"
        ]
        verdict["evidence_digest"] = canonical_digest(evidence)
        verdict["verdict_digest"] = canonical_digest(
            {
                key: value
                for key, value in verdict.items()
                if key != "verdict_digest"
            }
        )
    return RunArtifactBuilder().build(authority, plan, evidence, verdict)


def fixture_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes(range(32)))


def fixture_identity(*, suffix: str = "") -> AttestationIdentity:
    return AttestationIdentity(
        issuer="https://token.actions.githubusercontent.com",
        subject="repo:ed3c/Skill.md-native:ref:refs/heads/main" + suffix,
        repository="ed3c/Skill.md-native",
        workflow_ref=(
            "ed3c/Skill.md-native/.github/workflows/unit.yml@" + "a" * 40
        ),
        commit_sha="a" * 40,
        environment="github-hosted",
    )


def fixture_policy(public_key, identity, *, require_rank_eligible=False):
    return build_trust_policy(
        policy_id="skill-native.fixture-policy",
        allowed_key_ids=[key_id_for_public_key(public_key)],
        expected_issuer=identity.issuer,
        expected_subject=identity.subject,
        expected_repository=identity.repository,
        expected_workflow_ref=identity.workflow_ref,
        expected_commit_sha=identity.commit_sha,
        require_rank_eligible=require_rank_eligible,
    )


class AttestationTests(unittest.TestCase):
    def test_dsse_pae_and_ed25519_attestation_are_deterministic(self):
        bundle = make_bundle()
        private_key = fixture_private_key()
        identity = fixture_identity()
        public_key = private_key.public_key()

        first = sign_bundle(bundle, identity, private_key)
        second = sign_bundle(bundle, identity, private_key)
        self.assertEqual(first, second)

        payload = base64.b64decode(first.payload)
        expected_pae = (
            b"DSSEv1 "
            + str(len(first.payload_type.encode("utf-8"))).encode("ascii")
            + b" "
            + first.payload_type.encode("utf-8")
            + b" "
            + str(len(payload)).encode("ascii")
            + b" "
            + payload
        )
        self.assertEqual(dsse_pae(first.payload_type, payload), expected_pae)

        raw_public = public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        self.assertEqual(
            first.signatures[0].keyid,
            hashlib.sha256(raw_public).hexdigest(),
        )
        receipt = verify_attestation(
            bundle,
            first,
            public_key,
            fixture_policy(public_key, identity, require_rank_eligible=True),
        )
        self.assertTrue(receipt.passed)
        self.assertTrue(receipt.rank_eligible)
        self.assertEqual(parse_statement(first).predicate.bundle_digest, bundle.bundle_digest)

    def test_payload_signature_key_and_identity_tampering_fail_closed(self):
        bundle = make_bundle()
        private_key = fixture_private_key()
        public_key = private_key.public_key()
        identity = fixture_identity()
        envelope = sign_bundle(bundle, identity, private_key)
        policy = fixture_policy(public_key, identity)

        raw = envelope.model_dump(mode="json", by_alias=True)
        payload = json.loads(base64.b64decode(raw["payload"]).decode("utf-8"))
        payload["subject"][0]["digest"]["sha256"] = "0" * 64
        payload["predicate"]["bundle_digest"] = "0" * 64
        raw["payload"] = base64.b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).decode()
        tampered_payload = DSSEEnvelope.model_validate(raw)
        with self.assertRaises(AttestationError):
            verify_attestation(bundle, tampered_payload, public_key, policy)

        raw = envelope.model_dump(mode="json", by_alias=True)
        signature = bytearray(base64.b64decode(raw["signatures"][0]["sig"]))
        signature[0] ^= 1
        raw["signatures"][0]["sig"] = base64.b64encode(signature).decode()
        with self.assertRaisesRegex(AttestationError, "signature verification failed"):
            verify_attestation(
                bundle,
                DSSEEnvelope.model_validate(raw),
                public_key,
                policy,
            )

        with self.assertRaises(AttestationError):
            verify_attestation(
                bundle,
                envelope,
                Ed25519PrivateKey.generate().public_key(),
                policy,
            )

        wrong_identity_policy = build_trust_policy(
            policy_id="wrong-identity",
            allowed_key_ids=[key_id_for_public_key(public_key)],
            expected_subject="repo:other/project:ref:refs/heads/main",
        )
        with self.assertRaisesRegex(AttestationError, "identity subject"):
            verify_attestation(
                bundle,
                envelope,
                public_key,
                wrong_identity_policy,
            )

    def test_nested_bundle_tampering_is_rejected_before_signing(self):
        bundle = make_bundle()
        raw = bundle.model_dump(mode="json")
        raw["scorecard"]["diagnostic_score"] = 100.0
        with self.assertRaises(AttestationError):
            sign_bundle(raw, fixture_identity(), fixture_private_key())

    def test_signing_preserves_non_rank_eligible_state(self):
        bundle = make_bundle(remove_captured_stderr=True)
        self.assertFalse(bundle.scorecard.rank_eligible)
        private_key = fixture_private_key()
        public_key = private_key.public_key()
        identity = fixture_identity()
        envelope = sign_bundle(bundle, identity, private_key)
        receipt = verify_attestation(
            bundle,
            envelope,
            public_key,
            fixture_policy(public_key, identity),
        )
        self.assertFalse(receipt.rank_eligible)

        with self.assertRaisesRegex(AttestationError, "rank-eligible"):
            verify_attestation(
                bundle,
                envelope,
                public_key,
                fixture_policy(
                    public_key,
                    identity,
                    require_rank_eligible=True,
                ),
            )

    def test_key_generation_uses_derived_id_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private_path = root / "signing-key.pem"
            public_path = root / "signing-key.pub.pem"
            key_id = generate_keypair(private_path, public_path)
            private_key = load_private_key(private_path)
            public_key = load_public_key(public_path)
            self.assertEqual(key_id, key_id_for_public_key(public_key))
            self.assertEqual(
                key_id_for_public_key(private_key.public_key()),
                key_id,
            )
            if os.name == "posix":
                self.assertEqual(private_path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(AttestationError):
                generate_keypair(private_path, public_path)

    def test_transparency_chain_merkle_receipts_and_duplicates(self):
        bundle = make_bundle()
        private_key = fixture_private_key()
        public_key = private_key.public_key()
        identity = fixture_identity()
        envelope = sign_bundle(bundle, identity, private_key)
        verification = verify_attestation(
            bundle,
            envelope,
            public_key,
            fixture_policy(public_key, identity),
        )

        with tempfile.TemporaryDirectory() as td:
            log = TransparencyLog(Path(td) / "run-artifacts.jsonl", log_id="fixture.log")
            first = log.append(envelope, verification)
            self.assertEqual(log.verify().tree_size, 1)
            self.assertTrue(log.verify_receipt(first))
            with self.assertRaisesRegex(AttestationError, "duplicate"):
                log.append(envelope, verification)

            second_identity = fixture_identity(suffix=":second")
            second_envelope = sign_bundle(bundle, second_identity, private_key)
            second_verification = verify_attestation(
                bundle,
                second_envelope,
                public_key,
                build_trust_policy(
                    policy_id="second-policy",
                    allowed_key_ids=[key_id_for_public_key(public_key)],
                ),
            )
            second = log.append(second_envelope, second_verification)
            state = log.verify()
            self.assertEqual(state.tree_size, 2)
            self.assertNotEqual(first.checkpoint.root_hash, second.checkpoint.root_hash)
            self.assertTrue(log.verify_receipt(first))
            self.assertTrue(log.verify_receipt(second))

    def test_transparency_mutation_truncation_reordering_and_receipt_mismatch(self):
        bundle = make_bundle()
        private_key = fixture_private_key()
        public_key = private_key.public_key()
        identity = fixture_identity()
        policy = fixture_policy(public_key, identity)
        envelope = sign_bundle(bundle, identity, private_key)
        verification = verify_attestation(bundle, envelope, public_key, policy)

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run-artifacts.jsonl"
            log = TransparencyLog(path, log_id="fixture.log")
            first = log.append(envelope, verification)
            second_identity = fixture_identity(suffix=":second")
            second_envelope = sign_bundle(bundle, second_identity, private_key)
            second_verification = verify_attestation(
                bundle,
                second_envelope,
                public_key,
                build_trust_policy(
                    policy_id="second-policy",
                    allowed_key_ids=[key_id_for_public_key(public_key)],
                ),
            )
            log.append(second_envelope, second_verification)
            original_log = path.read_text(encoding="utf-8")
            original_checkpoint = log.checkpoint_path.read_text(encoding="utf-8")
            lines = original_log.splitlines(keepends=True)

            mutated = json.loads(lines[0])
            mutated["bundle_digest"] = "0" * 64
            lines[0] = json.dumps(mutated, sort_keys=True, separators=(",", ":")) + "\n"
            path.write_text("".join(lines), encoding="utf-8")
            with self.assertRaises(AttestationError):
                log.verify()

            path.write_text(original_log.splitlines(keepends=True)[0], encoding="utf-8")
            log.checkpoint_path.write_text(original_checkpoint, encoding="utf-8")
            with self.assertRaisesRegex(AttestationError, "mutation or truncation"):
                log.verify()

            original_lines = original_log.splitlines(keepends=True)
            path.write_text("".join(reversed(original_lines)), encoding="utf-8")
            log.checkpoint_path.write_text(original_checkpoint, encoding="utf-8")
            with self.assertRaises(AttestationError):
                log.verify()

            path.write_text(original_log, encoding="utf-8")
            log.checkpoint_path.write_text(original_checkpoint, encoding="utf-8")
            raw_receipt = first.model_dump(mode="json")
            raw_receipt["entry_digest"] = "f" * 64
            with self.assertRaises(ValidationError):
                TransparencyInclusionReceipt.model_validate(raw_receipt)

    def test_schema_export_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            first = export_attestation_schemas(Path(td) / "first")
            second = export_attestation_schemas(Path(td) / "second")
            self.assertEqual(set(first), set(second))
            self.assertEqual(len(first), 7)
            for name in first:
                self.assertEqual(
                    first[name].read_text(encoding="utf-8"),
                    second[name].read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
