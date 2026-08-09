from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .gateway import serve
from .github_ingest import GitHubIngestor, GitHubSkillSource
from .models import RunSpec
from .openshell import OpenShellPolicyCompiler
from .policy import ProviderPolicy, ReceiptLedger
from .providers import ProviderConfig, ProviderKind, ProviderRouter
from .runtime import FakeRuntime, OpenShellRuntime, RuntimeAdapter


def load_spec(path: Path) -> RunSpec:
    return RunSpec.model_validate(yaml.safe_load(path.read_text()))


def load_providers(path: Path) -> list[ProviderConfig]:
    raw = yaml.safe_load(path.read_text()) or {}
    providers = raw.get("providers", [])
    result: list[ProviderConfig] = []
    for item in providers:
        item = dict(item)
        item["kind"] = ProviderKind(item["kind"])
        result.append(ProviderConfig(**item))
    return result


def run_runtime(runtime: RuntimeAdapter, spec: RunSpec, command: list[str]) -> dict:
    sandbox_id = runtime.prepare(spec)
    try:
        execution_id = runtime.execute(sandbox_id, command)
        evidence = runtime.collect(spec.run_id, execution_id)
        return evidence.model_dump(mode="json")
    finally:
        runtime.destroy(sandbox_id)


def main() -> None:
    parser = argparse.ArgumentParser(prog="skill-native")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a run specification")
    validate.add_argument("spec", type=Path)

    compile_policy = sub.add_parser(
        "compile-openshell-policy", help="compile a RunSpec policy to OpenShell policy schema v1"
    )
    compile_policy.add_argument("spec", type=Path)

    fake = sub.add_parser("run-fake", help="exercise the evidence pipeline")
    fake.add_argument("spec", type=Path)

    openshell = sub.add_parser(
        "run-openshell", help="execute one command in an OpenShell sandbox and emit evidence JSON"
    )
    openshell.add_argument("spec", type=Path)
    openshell.add_argument("argv", nargs=argparse.REMAINDER)

    probe = sub.add_parser(
        "probe-provider",
        help="send one auditable chat-completions request through the configured provider router",
    )
    probe.add_argument("config", type=Path)
    probe.add_argument("prompt")
    probe.add_argument("--provider", default=None)
    probe.add_argument("--max-tokens", type=int, default=128)

    gateway = sub.add_parser(
        "serve-gateway",
        help="serve a local OpenAI-compatible inference broker for sandboxed agents",
    )
    gateway.add_argument("config", type=Path)
    gateway.add_argument("--host", default="127.0.0.1")
    gateway.add_argument("--port", type=int, default=8787)
    gateway.add_argument("--local-only", action="store_true")
    gateway.add_argument("--receipt-ledger", type=Path, default=None)
    gateway.add_argument("--max-daily-requests", type=int, default=None)
    gateway.add_argument("--max-daily-tokens", type=int, default=None)
    gateway.add_argument("--max-daily-cost-usd", type=float, default=None)

    ingest = sub.add_parser(
        "ingest-github",
        help="resolve a GitHub Skill ref to an immutable commit and persist provenance",
    )
    ingest.add_argument("url")
    ingest.add_argument("--ref", default="main")
    ingest.add_argument("--skill-path", default=".")
    ingest.add_argument("--entrypoint", default="SKILL.md")
    ingest.add_argument("--output", type=Path, required=True)
    ingest.add_argument("--provenance-dir", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "serve-gateway":
        policy = ProviderPolicy(
            local_only=args.local_only,
            max_daily_requests=args.max_daily_requests,
            max_daily_tokens=args.max_daily_tokens,
            max_daily_cost_usd=args.max_daily_cost_usd,
        )
        ledger = ReceiptLedger(args.receipt_ledger) if args.receipt_ledger else None
        serve(
            ProviderRouter(load_providers(args.config)),
            host=args.host,
            port=args.port,
            policy=policy,
            ledger=ledger,
        )
        return

    if args.command == "ingest-github":
        source = GitHubSkillSource.from_url(
            args.url,
            ref=args.ref,
            skill_path=args.skill_path,
            entrypoint=args.entrypoint,
        )
        result = GitHubIngestor().ingest(
            source,
            args.output,
            provenance_dir=args.provenance_dir,
        )
        print(
            json.dumps(
                {
                    "root": str(result.root),
                    "commit_sha": result.commit_sha,
                    "content_sha256": result.provenance.content_sha256,
                    "provenance_digest": result.provenance_digest,
                    "provenance_path": str(result.provenance_path),
                },
                indent=2,
            )
        )
        return

    if args.command == "probe-provider":
        router = ProviderRouter(load_providers(args.config))
        result = router.complete(
            [{"role": "user", "content": args.prompt}],
            required_provider=args.provider,
            max_tokens=args.max_tokens,
        )
        print(
            json.dumps(
                {
                    "text": result.text,
                    "receipt": result.receipt.model_dump(mode="json"),
                    "attempt_receipts": [r.model_dump(mode="json") for r in router.attempt_receipts],
                },
                indent=2,
            )
        )
        return

    spec = load_spec(args.spec)
    if args.command == "validate":
        print(json.dumps(spec.model_dump(mode="json"), indent=2))
    elif args.command == "compile-openshell-policy":
        print(OpenShellPolicyCompiler().dump(spec), end="")
    elif args.command == "run-fake":
        evidence = run_runtime(FakeRuntime(), spec, ["skill", "run", spec.skill.entrypoint])
        print(json.dumps(evidence, indent=2))
    elif args.command == "run-openshell":
        command = list(args.argv)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            parser.error("run-openshell requires a command after the spec")
        evidence = run_runtime(OpenShellRuntime(), spec, command)
        print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
