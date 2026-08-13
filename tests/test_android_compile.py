from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy

from pydantic import ValidationError

from skill_native.android_compile import (
    AndroidRunnerConfig,
    android_runner_command,
    android_runner_stdin_digest,
    build_android_runner_config,
    encode_android_runner_stdin,
)
from skill_native.android_contract import AndroidContract


_BASE = {
    "schema_version": "1.0",
    "driver": "adb",
    "adb_version": "1.0.41",
    "adb_sha256": "a" * 64,
    "device": {
        "serial": "emulator-5554",
        "min_api_level": 35,
        "max_api_level": 35,
        "allowed_abis": ["x86_64"],
    },
    "actions": [
        {
            "kind": "start_activity",
            "package": "com.android.settings",
            "activity": ".Settings",
        },
        {"kind": "capture_ui_hierarchy", "name": "settings-ui"},
        {"kind": "capture_screenshot", "name": "settings-screen"},
    ],
    "final_assertions": [
        {
            "id": "package",
            "kind": "package",
            "value": "com.android.settings",
            "match": "exact",
        }
    ],
}


def _contract() -> AndroidContract:
    return AndroidContract.model_validate(deepcopy(_BASE))


class AndroidCompileTests(unittest.TestCase):
    def test_runner_argv_never_contains_contract_payload(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=_contract())
        command = android_runner_command()
        rendered = json.dumps(command)
        self.assertEqual(command, ["skill-native-android-runner", "--config-stdin"])
        self.assertNotIn("com.android.settings", rendered)
        self.assertNotIn("emulator-5554", rendered)
        self.assertNotIn(config.contract_digest, rendered)

    def test_stdin_is_canonical_and_digest_matches_harness_kernel_semantics(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=_contract())
        stdin = encode_android_runner_stdin(config)
        self.assertEqual(
            stdin,
            json.dumps(
                json.loads(stdin),
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        self.assertEqual(
            android_runner_stdin_digest(config),
            hashlib.sha256(stdin.encode("utf-8")).hexdigest(),
        )

    def test_config_digest_binds_run_contract_and_action_plan(self) -> None:
        first = build_android_runner_config(run_id="run-a", contract=_contract())

        changed_action_payload = deepcopy(_BASE)
        changed_action_payload["actions"][0]["activity"] = ".SubSettings"
        changed_action = build_android_runner_config(
            run_id="run-a",
            contract=AndroidContract.model_validate(changed_action_payload),
        )

        changed_run = build_android_runner_config(run_id="run-b", contract=_contract())

        self.assertNotEqual(first.action_plan_digest, changed_action.action_plan_digest)
        self.assertNotEqual(first.contract_digest, changed_action.contract_digest)
        self.assertNotEqual(first.config_digest, changed_action.config_digest)
        self.assertNotEqual(first.config_digest, changed_run.config_digest)

    def test_tampered_nested_contract_is_rejected_even_with_old_digests(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=_contract())
        payload = config.model_dump(mode="json")
        payload["contract"]["device"]["serial"] = "emulator-5556"
        with self.assertRaises(ValidationError):
            AndroidRunnerConfig.model_validate(payload)

    def test_tampered_action_plan_digest_is_rejected(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=_contract())
        payload = config.model_dump(mode="json")
        payload["action_plan_digest"] = "f" * 64
        with self.assertRaises(ValidationError):
            AndroidRunnerConfig.model_validate(payload)

    def test_extra_config_fields_fail_closed(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=_contract())
        payload = config.model_dump(mode="json")
        payload["shell"] = "id"
        with self.assertRaises(ValidationError):
            AndroidRunnerConfig.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
