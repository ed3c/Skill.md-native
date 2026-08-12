from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .attestation_contract import (
    AttestationError,
    AttestationIdentity,
    AttestationTrustPolicy,
    DSSEEnvelope,
    build_trust_policy,
    export_attestation_schemas,
)
from .attestation_crypto import (
    generate_keypair,
    key_id_for_public_key,
    load_private_key,
    load_public_key,
    sign_bundle,
    verify_attestation,
)
from .run_artifact_bundle import RunArtifactBundle
from .transparency_log import TransparencyInclusionReceipt, TransparencyLog


def main() -> None:
    parser = argparse.ArgumentParser(prog="skill-native-attest")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate-key")
    generate.add_argument("--private-key", type=Path, required=True)
    generate.add_argument("--public-key", type=Path, required=True)
    generate.add_argument("--overwrite", action="store_true")

    policy = sub.add_parser("create-policy")
    policy.add_argument("--policy-id", required=True)
    policy.add_argument("--public-key", type=Path, action="append", required=True)
    policy.add_argument("--expected-issuer", default=None)
    policy.add_argument("--expected-subject", default=None)
    policy.add_argument("--expected-repository", default=None)
    policy.add_argument("--expected-workflow-ref", default=None)
    policy.add_argument("--expected-commit-sha", default=None)
    policy.add_argument("--require-rank-eligible", action="store_true")
    policy.add_argument("--output", type=Path, required=True)

    sign = sub.add_parser("sign")
    sign.add_argument("--bundle", type=Path, required=True)
    sign.add_argument("--identity", type=Path, required=True)
    sign.add_argument("--private-key", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--envelope", type=Path, required=True)
    verify.add_argument("--public-key", type=Path, required=True)
    verify.add_argument("--policy", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)

    append = sub.add_parser("log-append")
    append.add_argument("--bundle", type=Path, required=True)
    append.add_argument("--envelope", type=Path, required=True)
    append.add_argument("--public-key", type=Path, required=True)
    append.add_argument("--policy", type=Path, required=True)
    append.add_argument("--log", type=Path, required=True)
    append.add_argument("--log-id", default="skill-native.local")
    append.add_argument("--receipt-output", type=Path, required=True)

    verify_log = sub.add_parser("log-verify")
    verify_log.add_argument("--log", type=Path, required=True)
    verify_log.add_argument("--log-id", default="skill-native.local")

    verify_receipt = sub.add_parser("receipt-verify")
    verify_receipt.add_argument("--log", type=Path, required=True)
    verify_receipt.add_argument("--log-id", default="skill-native.local")
    verify_receipt.add_argument("--receipt", type=Path, required=True)

    schemas = sub.add_parser("export-schemas")
    schemas.add_argument("output", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "generate-key":
            key_id = generate_keypair(
                args.private_key,
                args.public_key,
                overwrite=args.overwrite,
            )
            print(json.dumps({"key_id": key_id}, indent=2))
            return
        if args.command == "create-policy":
            key_ids = [
                key_id_for_public_key(load_public_key(path))
                for path in args.public_key
            ]
            value = build_trust_policy(
                policy_id=args.policy_id,
                allowed_key_ids=key_ids,
                expected_issuer=args.expected_issuer,
                expected_subject=args.expected_subject,
                expected_repository=args.expected_repository,
                expected_workflow_ref=args.expected_workflow_ref,
                expected_commit_sha=args.expected_commit_sha,
                require_rank_eligible=args.require_rank_eligible,
            )
            _write_json(args.output, value.model_dump(mode="json"))
            print(args.output)
            return
        if args.command == "export-schemas":
            paths = export_attestation_schemas(args.output)
            print(
                json.dumps(
                    {name: str(path) for name, path in sorted(paths.items())},
                    indent=2,
                )
            )
            return
        if args.command == "log-verify":
            result = TransparencyLog(args.log, log_id=args.log_id).verify()
            print(
                json.dumps(
                    {
                        "log_id": result.log_id,
                        "tree_size": result.tree_size,
                        "root_hash": result.root_hash,
                        "head_entry_digest": result.head_entry_digest,
                        "checkpoint_digest": result.checkpoint_digest,
                    },
                    indent=2,
                )
            )
            return
        if args.command == "receipt-verify":
            receipt = TransparencyInclusionReceipt.model_validate(
                _load_json(args.receipt)
            )
            TransparencyLog(args.log, log_id=args.log_id).verify_receipt(receipt)
            print(json.dumps({"valid": True, "receipt_digest": receipt.receipt_digest}, indent=2))
            return

        bundle = RunArtifactBundle.model_validate(_load_json(args.bundle))
        if args.command == "sign":
            identity = AttestationIdentity.model_validate(_load_json(args.identity))
            envelope = sign_bundle(
                bundle,
                identity,
                load_private_key(args.private_key),
            )
            _write_json(
                args.output,
                envelope.model_dump(mode="json", by_alias=True),
            )
            print(args.output)
            return

        envelope = DSSEEnvelope.model_validate(_load_json(args.envelope))
        policy_model = AttestationTrustPolicy.model_validate(_load_json(args.policy))
        verification = verify_attestation(
            bundle,
            envelope,
            load_public_key(args.public_key),
            policy_model,
        )
        if args.command == "verify":
            _write_json(args.output, verification.model_dump(mode="json"))
            print(args.output)
            return
        if args.command == "log-append":
            receipt = TransparencyLog(args.log, log_id=args.log_id).append(
                envelope,
                verification,
            )
            _write_json(args.receipt_output, receipt.model_dump(mode="json"))
            print(args.receipt_output)
            return
        raise AttestationError(f"unsupported command: {args.command}")
    except (AttestationError, ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"skill-native-attest: {exc}\n")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AttestationError(f"{path} must contain a JSON object")
    return {str(key): child for key, child in value.items()}


def _write_json(path: Path, value: MappingLike) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


MappingLike = dict[str, Any]


if __name__ == "__main__":
    main()
