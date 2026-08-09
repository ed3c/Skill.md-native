from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .adversarial import materialize_all
from .cloudflare_runtime import CloudflareHttpClient
from .evidence import EvidenceStore, attach_run_receipts
from .gateway import serve
from .github_ingest import GitHubIngestor, GitHubSkillSource
from .models import EvidenceBundle, RunSpec
from .openshell import OpenShellPolicyCompiler
from .policy import ProviderPolicy, ReceiptLedger
from .providers import ProviderConfig, ProviderKind, ProviderRouter
from .registries import SkillsShAdapter
from .reporting import VerificationPolicy, build_report
from .runtime import CloudflareRuntime, FakeRuntime, OpenShellRuntime, RuntimeAdapter
from .compatibility import CompatibilityKey


def load_spec(path: Path) -> RunSpec:
    return RunSpec.model_validate(yaml.safe_load(path.read_text()))


def load_providers(path: Path) -> list[ProviderConfig]:
    raw = yaml.safe_load(path.read_text()) or {}
    result: list[ProviderConfig] = []
    for item in raw.get("providers", []):
        item = dict(item)
        item["kind"] = ProviderKind(item["kind"])
        result.append(ProviderConfig(**item))
    return result


def run_runtime(
    runtime: RuntimeAdapter,
    spec: RunSpec,
    command: list[str],
    *,
    ledger: ReceiptLedger | None = None,
    evidence_dir: Path | None = None,
) -> dict:
    sandbox_id = runtime.prepare(spec)
    try:
        execution_id = runtime.execute(sandbox_id, command)
        evidence = attach_run_receipts(runtime.collect(spec.run_id, execution_id), ledger)
        result = evidence.model_dump(mode="json")
        if evidence_dir:
            digest, path = EvidenceStore(evidence_dir).persist(evidence)
            result["evidence_digest"] = digest
            result["evidence_path"] = str(path)
        return result
    finally:
        runtime.destroy(sandbox_id)


def _runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("spec", type=Path)
    parser.add_argument("--receipt-ledger", type=Path, default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("argv", nargs=argparse.REMAINDER)


def main() -> None:
    parser = argparse.ArgumentParser(prog="skill-native")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("spec", type=Path)

    compile_policy = sub.add_parser("compile-openshell-policy")
    compile_policy.add_argument("spec", type=Path)

    fake = sub.add_parser("run-fake")
    fake.add_argument("spec", type=Path)
    fake.add_argument("--receipt-ledger", type=Path, default=None)
    fake.add_argument("--evidence-dir", type=Path, default=None)

    openshell = sub.add_parser("run-openshell")
    _runtime_args(openshell)

    cloudflare = sub.add_parser("run-cloudflare")
    _runtime_args(cloudflare)
    cloudflare.add_argument("--bridge-url", required=True)
    cloudflare.add_argument("--bridge-token", default=None)

    probe = sub.add_parser("probe-provider")
    probe.add_argument("config", type=Path)
    probe.add_argument("prompt")
    probe.add_argument("--provider", default=None)
    probe.add_argument("--max-tokens", type=int, default=128)

    gateway = sub.add_parser("serve-gateway")
    gateway.add_argument("config", type=Path)
    gateway.add_argument("--host", default="127.0.0.1")
    gateway.add_argument("--port", type=int, default=8787)
    gateway.add_argument("--local-only", action="store_true")
    gateway.add_argument("--receipt-ledger", type=Path, default=None)
    gateway.add_argument("--max-daily-requests", type=int, default=None)
    gateway.add_argument("--max-daily-tokens", type=int, default=None)
    gateway.add_argument("--max-daily-cost-usd", type=float, default=None)

    ingest = sub.add_parser("ingest-github")
    ingest.add_argument("url")
    ingest.add_argument("--ref", default="main")
    ingest.add_argument("--skill-path", default=".")
    ingest.add_argument("--entrypoint", default="SKILL.md")
    ingest.add_argument("--output", type=Path, required=True)
    ingest.add_argument("--provenance-dir", type=Path, required=True)

    skills = sub.add_parser("ingest-skills-sh")
    skills.add_argument("stable_id")
    skills.add_argument("--output", type=Path, required=True)

    fixtures = sub.add_parser("materialize-fixtures")
    fixtures.add_argument("output", type=Path)

    report = sub.add_parser("build-report")
    report.add_argument("input", type=Path, help="JSONL rows with key/evidence")
    report.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "serve-gateway":
        policy = ProviderPolicy(
            local_only=args.local_only,
            max_daily_requests=args.max_daily_requests,
            max_daily_tokens=args.max_daily_tokens,
            max_daily_cost_usd=args.max_daily_cost_usd,
        )
        ledger = ReceiptLedger(args.receipt_ledger) if args.receipt_ledger else None
        serve(ProviderRouter(load_providers(args.config)), host=args.host, port=args.port, policy=policy, ledger=ledger)
        return

    if args.command == "ingest-github":
        source = GitHubSkillSource.from_url(args.url, ref=args.ref, skill_path=args.skill_path, entrypoint=args.entrypoint)
        result = GitHubIngestor().ingest(source, args.output, provenance_dir=args.provenance_dir)
        print(json.dumps({
            "root": str(result.root), "commit_sha": result.commit_sha,
            "content_sha256": result.provenance.content_sha256,
            "provenance_digest": result.provenance_digest,
            "provenance_path": str(result.provenance_path),
        }, indent=2))
        return

    if args.command == "ingest-skills-sh":
        skill = SkillsShAdapter().fetch(args.stable_id)
        provenance = SkillsShAdapter().provenance(skill, args.output)
        print(json.dumps({
            "stable_id": skill.stable_id,
            "registry_hash": skill.content_hash,
            "content_sha256": provenance.content_sha256,
            "license_status": provenance.license_status,
        }, indent=2))
        return

    if args.command == "materialize-fixtures":
        paths = materialize_all(args.output)
        print(json.dumps([str(p) for p in paths], indent=2))
        return

    if args.command == "build-report":
        rows = []
        for line in args.input.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            rows.append((CompatibilityKey(**value["key"]), EvidenceBundle.model_validate(value["evidence"])))
        payload = build_report(rows, VerificationPolicy())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(args.output)
        return

    if args.command == "probe-provider":
        router = ProviderRouter(load_providers(args.config))
        result = router.complete([{"role": "user", "content": args.prompt}], required_provider=args.provider, max_tokens=args.max_tokens)
        print(json.dumps({
            "text": result.text,
            "receipt": result.receipt.model_dump(mode="json"),
            "attempt_receipts": [r.model_dump(mode="json") for r in router.attempt_receipts],
        }, indent=2))
        return

    spec = load_spec(args.spec)
    ledger = ReceiptLedger(args.receipt_ledger) if getattr(args, "receipt_ledger", None) else None
    evidence_dir = getattr(args, "evidence_dir", None)
    if args.command == "validate":
        print(json.dumps(spec.model_dump(mode="json"), indent=2))
    elif args.command == "compile-openshell-policy":
        print(OpenShellPolicyCompiler().dump(spec), end="")
    elif args.command == "run-fake":
        print(json.dumps(run_runtime(FakeRuntime(), spec, ["skill", "run", spec.skill.entrypoint], ledger=ledger, evidence_dir=evidence_dir), indent=2))
    elif args.command in {"run-openshell", "run-cloudflare"}:
        command = list(args.argv)
        if command and command[0] == "--": command = command[1:]
        if not command: parser.error(f"{args.command} requires a command")
        runtime: RuntimeAdapter
        if args.command == "run-openshell":
            runtime = OpenShellRuntime()
        else:
            runtime = CloudflareRuntime(CloudflareHttpClient(args.bridge_url, args.bridge_token))
        print(json.dumps(run_runtime(runtime, spec, command, ledger=ledger, evidence_dir=evidence_dir), indent=2))


if __name__ == "__main__":
    main()
