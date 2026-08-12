from __future__ import annotations

import argparse
import json
import sys

from .browser_contract import BrowserContractError, BrowserRunnerConfig
from .browser_runner import execute_browser


def main() -> None:
    parser = argparse.ArgumentParser(prog="skill-native-browser-runner")
    parser.add_argument("--config-stdin", action="store_true", required=True)
    parser.parse_args()
    try:
        raw = sys.stdin.read()
        if not raw:
            raise BrowserContractError("browser runner config stdin is empty")
        parsed = json.loads(raw)
        config = BrowserRunnerConfig.model_validate(parsed)
        canonical = json.dumps(
            config.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        if raw != canonical:
            raise BrowserContractError(
                "browser runner config stdin must use canonical JSON encoding"
            )
        receipt = execute_browser(config)
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed
        parser.exit(2, f"skill-native-browser-runner: {type(exc).__name__}: {exc}\n")
    print(
        json.dumps(
            receipt.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    raise SystemExit(0 if receipt.outcome == "pass" else 1)


if __name__ == "__main__":
    main()
