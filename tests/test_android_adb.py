from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from skill_native.android_adb import (
    AdbDevice,
    AndroidAdbError,
    attest_adb_binary,
    compile_adb_action_argv,
    parse_adb_devices,
    select_online_device,
)
from skill_native.android_contract import (
    CaptureScreenshotAction,
    CaptureUiHierarchyAction,
    KeyEventAction,
    StartActivityAction,
    SwipeAction,
    TapAction,
    WaitAction,
    WaitForActivityAction,
    WaitForPackageAction,
    WaitForUiTextAction,
)


class AndroidAdbPrimitiveTests(unittest.TestCase):
    def test_parses_structured_devices_and_attributes(self) -> None:
        devices = parse_adb_devices(
            "List of devices attached\n"
            "emulator-5554 device product:sdk model:sdk_gphone transport_id:1\n"
            "physical-1 unauthorized usb:1-1\n"
        )
        self.assertEqual(
            [device.serial for device in devices],
            ["emulator-5554", "physical-1"],
        )
        self.assertEqual(devices[0].attributes["model"], "sdk_gphone")
        self.assertEqual(devices[1].state, "unauthorized")

    def test_rejects_duplicate_malformed_and_unsafe_device_lines(self) -> None:
        invalid_outputs = (
            "List of devices attached\nemulator-5554\n",
            "List of devices attached\nemulator-5554 device malformed\n",
            (
                "List of devices attached\n"
                "emulator-5554 device\n"
                "emulator-5554 device\n"
            ),
            "List of devices attached\nemulator-5554;id device\n",
        )
        for output in invalid_outputs:
            with self.subTest(output=output):
                with self.assertRaises(AndroidAdbError):
                    parse_adb_devices(output)

    def test_rejects_unbounded_device_output(self) -> None:
        with self.assertRaises(AndroidAdbError):
            parse_adb_devices("x" * 1_000_001)

    def test_selects_exact_online_device_and_fails_closed(self) -> None:
        devices = [
            AdbDevice(serial="emulator-5554", state="device"),
            AdbDevice(serial="physical-1", state="unauthorized"),
        ]
        self.assertEqual(
            select_online_device(
                devices, expected_serial="emulator-5554"
            ).serial,
            "emulator-5554",
        )
        self.assertEqual(
            select_online_device(devices, expected_serial=None).serial,
            "emulator-5554",
        )

        with self.assertRaises(AndroidAdbError):
            select_online_device(devices, expected_serial="physical-1")
        with self.assertRaises(AndroidAdbError):
            select_online_device(devices, expected_serial="missing")
        with self.assertRaises(AndroidAdbError):
            select_online_device(
                devices + [AdbDevice(serial="emulator-5556", state="device")],
                expected_serial=None,
            )
        with self.assertRaises(AndroidAdbError):
            select_online_device(devices, expected_serial="bad;serial")

    def test_compiles_only_typed_argv(self) -> None:
        adb = "/opt/android-sdk/platform-tools/adb"
        serial = "emulator-5554"
        cases = (
            (
                StartActivityAction(
                    package="com.android.settings",
                    activity=".Settings",
                ),
                [
                    adb,
                    "-s",
                    serial,
                    "shell",
                    "am",
                    "start",
                    "-W",
                    "-n",
                    "com.android.settings/.Settings",
                ],
            ),
            (
                KeyEventAction(keycode=4),
                [adb, "-s", serial, "shell", "input", "keyevent", "4"],
            ),
            (
                TapAction(x=100, y=200),
                [adb, "-s", serial, "shell", "input", "tap", "100", "200"],
            ),
            (
                SwipeAction(
                    start_x=1,
                    start_y=2,
                    end_x=3,
                    end_y=4,
                    duration_ms=500,
                ),
                [
                    adb,
                    "-s",
                    serial,
                    "shell",
                    "input",
                    "swipe",
                    "1",
                    "2",
                    "3",
                    "4",
                    "500",
                ],
            ),
            (
                WaitForPackageAction(package="com.android.settings"),
                [adb, "-s", serial, "shell", "dumpsys", "window", "windows"],
            ),
            (
                WaitForActivityAction(
                    package="com.android.settings",
                    activity=".Settings",
                ),
                [
                    adb,
                    "-s",
                    serial,
                    "shell",
                    "dumpsys",
                    "activity",
                    "activities",
                ],
            ),
            (
                WaitForUiTextAction(value="Settings"),
                [
                    adb,
                    "-s",
                    serial,
                    "shell",
                    "uiautomator",
                    "dump",
                    "/sdcard/window.xml",
                ],
            ),
            (
                CaptureUiHierarchyAction(name="ui"),
                [
                    adb,
                    "-s",
                    serial,
                    "exec-out",
                    "uiautomator",
                    "dump",
                    "/dev/tty",
                ],
            ),
            (
                CaptureScreenshotAction(name="screen"),
                [adb, "-s", serial, "exec-out", "screencap", "-p"],
            ),
        )
        for action, expected in cases:
            with self.subTest(action=type(action).__name__):
                self.assertEqual(
                    compile_adb_action_argv(
                        adb_path=adb,
                        serial=serial,
                        action=action,
                    ),
                    expected,
                )

    def test_rejects_local_wait_relative_path_and_unsafe_serial(self) -> None:
        with self.assertRaises(AndroidAdbError):
            compile_adb_action_argv(
                adb_path="/opt/android-sdk/platform-tools/adb",
                serial="emulator-5554",
                action=WaitAction(duration_ms=1),
            )
        with self.assertRaises(AndroidAdbError):
            compile_adb_action_argv(
                adb_path="adb",
                serial="emulator-5554",
                action=TapAction(x=1, y=2),
            )
        with self.assertRaises(AndroidAdbError):
            compile_adb_action_argv(
                adb_path="/usr/bin/adb",
                serial="emulator-5554;id",
                action=TapAction(x=1, y=2),
            )

    @unittest.skipUnless(
        bool(getattr(os, "O_NOFOLLOW", 0)),
        "platform cannot enforce no-follow attestation",
    )
    def test_attests_regular_executable_and_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "adb"
            payload = b"fixture-adb-binary"
            executable.write_bytes(payload)
            executable.chmod(0o755)

            identity = attest_adb_binary(
                executable,
                reported_version="Android Debug Bridge version 1.0.41",
            )
            self.assertEqual(identity.path, str(executable.resolve()))
            self.assertEqual(identity.sha256, hashlib.sha256(payload).hexdigest())
            self.assertEqual(
                identity.version,
                "Android Debug Bridge version 1.0.41",
            )

            symlink = root / "adb-link"
            symlink.symlink_to(executable)
            with self.assertRaises(AndroidAdbError):
                attest_adb_binary(
                    symlink,
                    reported_version="Android Debug Bridge version 1.0.41",
                )

    @unittest.skipUnless(
        bool(getattr(os, "O_NOFOLLOW", 0)),
        "platform cannot enforce no-follow attestation",
    )
    def test_rejects_non_executable_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "adb"
            executable.write_bytes(b"fixture")
            executable.chmod(0o644)
            with self.assertRaises(AndroidAdbError):
                attest_adb_binary(
                    executable,
                    reported_version="Android Debug Bridge version 1.0.41",
                )


if __name__ == "__main__":
    unittest.main()
