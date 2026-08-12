from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .run_artifact_builder import RunArtifactBuilder
from .run_artifact_common import (
    AuthorityKind,
    EvaluatorAuthority,
    EvidenceGraph,
    RunArtifactError,
    TrustBasis,
    build_evaluator_authority,
    canonical_digest,
)
from .run_artifact_bundle import RunArtifactBundle
from .run_artifact_contract import (
    LogicalTrace,
    OutcomeScorecard,
    ReplayClass,
    ReplayManifest,
    RunArtifactStore,
    ScorecardTier,
    export_run_artifact_schemas,
)

__all__ = [
    "AuthorityKind",
    "EvaluatorAuthority",
    "EvidenceGraph",
    "LogicalTrace",
    "OutcomeScorecard",
    "ReplayClass",
    "ReplayManifest",
    "RunArtifactBuilder",
    "RunArtifactBundle",
    "RunArtifactError",
    "RunArtifactStore",
    "ScorecardTier",
    "TrustBasis",
    "build_evaluator_authority",
    "canonical_digest",
    "export_run_artifact_schemas",
]


def _json_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RunArtifactError(f"{name} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunArtifactError(f"cannot load JSON from {path}: {exc}") from exc
    return _json_mapping(value, str(path))


def main() -> None:
    parser = argparse.ArgumentParser(prog="skill-native-run-artifacts")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--authority", type=Path, required=True)
    build.add_argument("--plan", type=Path, required=True)
    build.add_argument("--evidence", type=Path, required=True)
    build.add_argument("--verdict", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)

    authority = sub.add_parser("create-authority")
    authority.add_argument("--authority-id", required=True)
    authority.add_argument(
        "--kind",
        choices=[value.value for value in AuthorityKind],
        required=True,
    )
    authority.add_argument(
        "--trust-basis",
        choices=[value.value for value in TrustBasis],
        required=True,
    )
    authority.add_argument("--source-url", required=True)
    authority.add_argument("--commit-or-digest", required=True)
    authority.add_argument("--manifest-digest", required=True)
    authority.add_argument("--evaluator-digest", required=True)
    authority.add_argument("--output", type=Path, required=True)

    schemas = sub.add_parser("export-schemas")
    schemas.add_argument("output", type=Path)

    args = parser.parse_args()
    if args.command == "create-authority":
        result = build_evaluator_authority(
            authority_id=args.authority_id,
            kind=args.kind,
            trust_basis=args.trust_basis,
            source_url=args.source_url,
            commit_or_digest=args.commit_or_digest,
            manifest_digest=args.manifest_digest,
            evaluator_digest=args.evaluator_digest,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                result.model_dump(mode="json"),
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(args.output)
        return
    if args.command == "export-schemas":
        paths = export_run_artifact_schemas(args.output)
        print(
            json.dumps(
                {name: str(path) for name, path in sorted(paths.items())},
                indent=2,
            )
        )
        return

    bundle = RunArtifactBuilder().build(
        _load_json(args.authority),
        _load_json(args.plan),
        _load_json(args.evidence),
        _load_json(args.verdict),
    )
    digest, path = RunArtifactStore(args.output).persist(bundle)
    print(
        json.dumps(
            {"bundle_digest": digest, "bundle_path": str(path)},
            indent=2,
        )
    )
    if not bundle.scorecard.rank_eligible:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
