from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

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


def main() -> None:
    manifest = load_harness_manifest(ROOT / "harness.yaml")
    spec = RunSpec.model_validate(
        yaml.safe_load((ROOT / "run.fake.yaml").read_text(encoding="utf-8"))
    )
    server = make_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="skill-native-browser-") as td:
            workspace = Path(td)
            result = HarnessKernel().run(
                manifest,
                spec,
                LocalBrowserFixtureRuntime(workspace),
                evidence_store=EvidenceStore(workspace / "evidence"),
                verdict_store=HarnessVerdictStore(workspace / "verdicts"),
            )
            print(json.dumps(result.model_dump(mode="json"), indent=2))
            if result.verdict.status is VerdictStatus.FAIL:
                raise SystemExit(2)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
