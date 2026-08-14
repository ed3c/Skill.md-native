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
    "adb_version": "1.0.41",
    "adb_sha256": "a" * 64,
    "device": {"serial": "emulator-5554", "allowed_abis": ["x86_64"]},
    "actions": [
        {"kind": "start_activity", "package": "com.android.settings", "activity": ".Settings"},
        {"kind": "capture_ui_hierarchy", "name": "settings-ui"},
        {"kind": "capture_screenshot", "name": "settings-screen"},
    ],
    "final_assertions": [
        {"id": "package", "kind": "package", "value": "com.android.settings"}
    ],
}


def contract() -> AndroidContract:
    return AndroidContract.model_validate(deepcopy(_BASE))


class AndroidCompileTests(unittest.TestCase):
    def test_runner_argv_contains_no_contract_payload(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=contract())
        command = android_runner_command()
        rendered = json.dumps(command)
        self.assertEqual(command, ["skill-native-android-runner", "--config-stdin"])
        self.assertNotIn("com.android.settings", rendered)
        self.assertNotIn("emulator-5554", rendered)
        self.assertNotIn(config.contract_digest, rendered)

    def test_stdin_is_canonical_and_digest_matches_kernel_bytes(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=contract())
        stdin = encode_android_runner_stdin(config)
        self.assertEqual(stdin, json.dumps(json.loads(stdin), sort_keys=True, separators=(",", ":")))
        self.assertEqual(android_runner_stdin_digest(config), hashlib.sha256(stdin.encode("utf-8")).hexdigest())

    def test_config_digest_binds_run_contract_and_action_plan(self) -> None:
        first = build_android_runner_config(run_id="run-a", contract=contract())
        changed_payload = deepcopy(_BASE)
        changed_payload["actions"][0]["activity"] = ".SubSettings"
        changed = build_android_runner_config(run_id="run-a", contract=AndroidContract.model_validate(changed_payload))
        changed_run = build_android_runner_config(run_id="run-b", contract=contract())
        self.assertNotEqual(first.action_plan_digest, changed.action_plan_digest)
        self.assertNotEqual(first.contract_digest, changed.contract_digest)
        self.assertNotEqual(first.config_digest, changed.config_digest)
        self.assertNotEqual(first.config_digest, changed_run.config_digest)

    def test_tampered_nested_contract_is_rejected(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=contract())
        value = config.model_dump(mode="json")
        value["contract"]["device"]["serial"] = "emulator-5556"
        with self.assertRaises(ValidationError):
            AndroidRunnerConfig.model_validate(value)

    def test_tampered_action_plan_digest_is_rejected(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=contract())
        value = config.model_dump(mode="json")
        value["action_plan_digest"] = "f" * 64
        with self.assertRaises(ValidationError):
            AndroidRunnerConfig.model_validate(value)

    def test_extra_config_fields_fail_closed(self) -> None:
        config = build_android_runner_config(run_id="android-compile", contract=contract())
        value = config.model_dump(mode="json")
        value["unexpected"] = True
        with self.assertRaises(ValidationError):
            AndroidRunnerConfig.model_validate(value)


if __name__ == "__main__":
    unittest.main()
