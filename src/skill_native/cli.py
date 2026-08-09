from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .models import RunSpec
from .runtime import FakeRuntime


def load_spec(path: Path) -> RunSpec:
    return RunSpec.model_validate(yaml.safe_load(path.read_text()))


def run_fake(spec: RunSpec) -> dict:
    runtime = FakeRuntime()
    sandbox_id = runtime.prepare(spec)
    try:
        execution_id = runtime.execute(sandbox_id, ["skill", "run", spec.skill.entrypoint])
        evidence = runtime.collect(spec.run_id, execution_id)
        return evidence.model_dump(mode="json")
    finally:
        runtime.destroy(sandbox_id)


def main() -> None:
    parser = argparse.ArgumentParser(prog="skill-native")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a run specification")
    validate.add_argument("spec", type=Path)

    fake = sub.add_parser("run-fake", help="exercise the evidence pipeline")
    fake.add_argument("spec", type=Path)

    args = parser.parse_args()
    spec = load_spec(args.spec)

    if args.command == "validate":
        print(json.dumps(spec.model_dump(mode="json"), indent=2))
    elif args.command == "run-fake":
        print(json.dumps(run_fake(spec), indent=2))


if __name__ == "__main__":
    main()
