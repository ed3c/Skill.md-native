from __future__ import annotations

import argparse
import json
import tempfile
import threading
from contextlib import nullcontext
from pathlib import Path
from typing import ContextManager

import yaml

from fixture_server import make_server
from skill_native.browser_fixture_runtime import LocalBrowserFixtureRuntime
from skill_native.evidence import EvidenceStore
from skill_native.harness import (
    HarnessKernel,
    HarnessVerdictStore,
    VerdictStatus,
    load_harness_manifest,
)
from skill_native.models import RunSpec


ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic Playwright loopback fixture."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Persist the workspace, EvidenceBundle, HarnessVerdict, browser artifacts, "
            "and result JSON. Without this option the fixture uses a temporary directory."
        ),
    )
    return parser.parse_args()


def workspace_context(output_dir: Path | None) -> ContextManager[Path | str]:
    if output_dir is None:
        return tempfile.TemporaryDirectory(prefix="skill-native-browser-")
    workspace = output_dir.resolve()
    if workspace.exists() and any(workspace.iterdir()):
        raise SystemExit(f"refusing non-empty output directory: {workspace}")
    workspace.mkdir(parents=True, exist_ok=True)
    return nullcontext(workspace)


def main() -> None:
    args = parse_args()
    manifest = load_harness_manifest(ROOT / "harness.yaml")
    spec = RunSpec.model_validate(
        yaml.safe_load((ROOT / "run.fake.yaml").read_text(encoding="utf-8"))
    )
    server = make_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with workspace_context(args.output_dir) as workspace_value:
            workspace = Path(workspace_value)
            result = HarnessKernel().run(
                manifest,
                spec,
                LocalBrowserFixtureRuntime(workspace),
                evidence_store=EvidenceStore(workspace / "evidence"),
                verdict_store=HarnessVerdictStore(workspace / "verdicts"),
            )
            rendered = json.dumps(result.model_dump(mode="json"), indent=2)
            if args.output_dir is not None:
                (workspace / "result.json").write_text(
                    rendered + "\n", encoding="utf-8"
                )
            print(rendered)
            if result.verdict.status is VerdictStatus.FAIL:
                raise SystemExit(2)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
