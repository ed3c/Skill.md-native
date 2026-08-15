from __future__ import annotations

import unittest

from pydantic import ValidationError

from skill_native.android_contract import (
    AndroidContract,
    android_action_plan_digest,
    android_contract_digest,
)


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
        "model": "sdk_gphone64_x86_64",
    },
    "actions": [
        {
            "kind": "start_activity",
            "package": "com.android.settings",
            "activity": ".Settings",
        },
        {"kind": "keyevent", "keycode": 4},
        {"kind": "tap", "x": 100, "y": 200},
        {
            "kind": "swipe",
            "start_x": 100,
            "start_y": 500,
            "end_x": 100,
            "end_y": 100,
            "duration_ms": 300,
        },
        {"kind": "wait", "duration_ms": 250},
        {
            "kind": "wait_for_package",
            "package": "com.android.settings",
            "timeout_ms": 5000,
        },
        {
            "kind": "wait_for_activity",
            "package": "com.android.settings",
            "activity": ".Settings",
            "timeout_ms": 5000,
        },
        {
            "kind": "wait_for_ui_text",
            "value": "Settings",
            "match": "contains",
            "timeout_ms": 5000,
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
        },
        {
            "id": "title-visible",
            "kind": "ui_text",
            "value": "Settings",
            "match": "contains",
        },
    ],
}


def _payload() -> dict:
    import copy

    return copy.deepcopy(_BASE)


class AndroidContractTests(unittest.TestCase):
    def test_valid_contract_has_stable_digests(self) -> None:
        contract = AndroidContract.model_validate(_payload())
        self.assertEqual(android_contract_digest(contract), android_contract_digest(contract))
        self.assertEqual(
            android_action_plan_digest(contract.actions),
            android_action_plan_digest(contract.actions),
        )

    def test_plan_digest_changes_when_action_changes(self) -> None:
        first = AndroidContract.model_validate(_payload())
        changed = _payload()
        changed["actions"][2]["x"] = 101
        second = AndroidContract.model_validate(changed)
        self.assertNotEqual(
            android_action_plan_digest(first.actions),
            android_action_plan_digest(second.actions),
        )
        self.assertNotEqual(android_contract_digest(first), android_contract_digest(second))

    def test_contract_digest_changes_when_device_identity_changes(self) -> None:
        first = AndroidContract.model_validate(_payload())
        changed = _payload()
        changed["device"]["serial"] = "emulator-5556"
        second = AndroidContract.model_validate(changed)
        self.assertNotEqual(android_contract_digest(first), android_contract_digest(second))

    def test_rejects_shell_metacharacters_in_package(self) -> None:
        payload = _payload()
        payload["actions"][0]["package"] = "com.android.settings;id"
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_rejects_shell_metacharacters_in_serial(self) -> None:
        payload = _payload()
        payload["device"]["serial"] = "emulator-5554;id"
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_arbitrary_shell_action_is_not_part_of_grammar(self) -> None:
        payload = _payload()
        payload["actions"] = [{"kind": "shell", "command": "id"}]
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_text_input_action_is_not_part_of_grammar(self) -> None:
        payload = _payload()
        payload["actions"] = [{"kind": "input_text", "value": "secret"}]
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_rejects_path_traversal_artifact_root(self) -> None:
        payload = _payload()
        payload["artifact_root"] = "../android"
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_rejects_duplicate_artifact_names(self) -> None:
        payload = _payload()
        payload["actions"].append(
            {"kind": "capture_screenshot", "name": "settings-screen"}
        )
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_rejects_duplicate_assertion_ids(self) -> None:
        payload = _payload()
        payload["final_assertions"].append(
            {
                "id": "package",
                "kind": "ui_text",
                "value": "Settings",
                "match": "contains",
            }
        )
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_rejects_unsorted_or_duplicate_abis(self) -> None:
        for values in (["x86_64", "arm64-v8a"], ["x86_64", "x86_64"]):
            payload = _payload()
            payload["device"]["allowed_abis"] = values
            with self.assertRaises(ValidationError):
                AndroidContract.model_validate(payload)

    def test_rejects_inverted_api_range(self) -> None:
        payload = _payload()
        payload["device"]["min_api_level"] = 36
        payload["device"]["max_api_level"] = 35
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_rejects_unbounded_wait(self) -> None:
        payload = _payload()
        payload["actions"] = [{"kind": "wait", "duration_ms": 30001}]
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)

    def test_rejects_extra_fields(self) -> None:
        payload = _payload()
        payload["root"] = True
        with self.assertRaises(ValidationError):
            AndroidContract.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
