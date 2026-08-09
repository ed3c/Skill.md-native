from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .gateway import serve
from .models import RunSpec
from .openshell import OpenShellPolicyCompiler
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

    args = parser.parse_args()

    if args.command == "serve-gateway":
        serve(ProviderRouter(load_providers(args.config)), host=args.host, port=args.port)
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
