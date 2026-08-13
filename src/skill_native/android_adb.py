from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .android_contract import (
    AndroidAction,
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


class AndroidAdbError(ValueError):
    """Raised when ADB identity, device selection, or argv construction fails closed."""


class AdbBinaryIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    version: str = Field(min_length=1, max_length=256)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdbDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serial: str = Field(min_length=1, max_length=128)
    state: str = Field(min_length=1, max_length=64)
    attributes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_duplicate_or_unsafe_attribute_keys(self) -> "AdbDevice":
        for key, value in self.attributes.items():
            if not key or any(ch.isspace() for ch in key) or ":" in key:
                raise ValueError("ADB device attribute keys must be simple tokens")
            if len(value) > 512:
                raise ValueError("ADB device attribute values are too long")
        return self


def attest_adb_binary(path: Path, *, reported_version: str) -> AdbBinaryIdentity:
    """Attest a local ADB executable without following a symlink substitution."""

    if not reported_version or len(reported_version) > 256:
        raise AndroidAdbError("ADB reported version is missing or too long")
    if path.is_symlink():
        raise AndroidAdbError("ADB executable must not be a symlink")
    try:
        stat = path.stat()
    except FileNotFoundError as exc:
        raise AndroidAdbError("ADB executable does not exist") from exc
    if not path.is_file():
        raise AndroidAdbError("ADB executable must be a regular file")
    if not os.access(path, os.X_OK):
        raise AndroidAdbError("ADB executable is not executable")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)

    # Re-stat after hashing so a replacement during the read is detectable.
    after = path.stat()
    if (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise AndroidAdbError("ADB executable changed while being attested")

    return AdbBinaryIdentity(
        path=str(path.resolve()),
        version=reported_version.strip(),
        sha256=digest.hexdigest(),
    )


def parse_adb_devices(output: str) -> list[AdbDevice]:
    """Parse `adb devices -l` output without trusting arbitrary trailing text."""

    lines = output.replace("\r\n", "\n").split("\n")
    devices: list[AdbDevice] = []
    seen: set[str] = set()

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("List of devices attached") or line.startswith("* daemon"):
            continue
        parts = line.split()
        if len(parts) < 2:
            raise AndroidAdbError(f"malformed adb device line: {line!r}")
        serial, state, *tokens = parts
        if serial in seen:
            raise AndroidAdbError(f"duplicate ADB serial: {serial}")
        seen.add(serial)
        attributes: dict[str, str] = {}
        for token in tokens:
            if ":" not in token:
                raise AndroidAdbError(f"malformed ADB device attribute: {token!r}")
            key, value = token.split(":", 1)
            if not key or not value or key in attributes:
                raise AndroidAdbError(f"invalid ADB device attribute: {token!r}")
            attributes[key] = value
        devices.append(AdbDevice(serial=serial, state=state, attributes=attributes))
    return devices


def select_online_device(devices: Iterable[AdbDevice], *, expected_serial: str | None) -> AdbDevice:
    candidates = list(devices)
    if expected_serial is not None:
        matches = [device for device in candidates if device.serial == expected_serial]
        if len(matches) != 1:
            raise AndroidAdbError("expected Android device serial is not uniquely present")
        selected = matches[0]
        if selected.state != "device":
            raise AndroidAdbError(
                f"expected Android device is not online: {selected.state}"
            )
        return selected

    online = [device for device in candidates if device.state == "device"]
    if len(online) != 1:
        raise AndroidAdbError(
            f"exactly one online Android device is required; found {len(online)}"
        )
    return online[0]


def compile_adb_action_argv(*, adb_path: str, serial: str, action: AndroidAction) -> list[str]:
    """Compile a bounded Android action into argv. No generic shell primitive exists."""

    prefix = [adb_path, "-s", serial]

    if isinstance(action, StartActivityAction):
        return prefix + [
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            f"{action.package}/{action.activity}",
        ]
    if isinstance(action, KeyEventAction):
        return prefix + ["shell", "input", "keyevent", str(action.keycode)]
    if isinstance(action, TapAction):
        return prefix + ["shell", "input", "tap", str(action.x), str(action.y)]
    if isinstance(action, SwipeAction):
        return prefix + [
            "shell",
            "input",
            "swipe",
            str(action.start_x),
            str(action.start_y),
            str(action.end_x),
            str(action.end_y),
            str(action.duration_ms),
        ]
    if isinstance(action, WaitAction):
        # Wait is owned by the trusted runner and must never become a device-shell command.
        raise AndroidAdbError("wait actions are runner-local and have no ADB argv")
    if isinstance(action, WaitForPackageAction):
        return prefix + ["shell", "dumpsys", "window", "windows"]
    if isinstance(action, WaitForActivityAction):
        return prefix + ["shell", "dumpsys", "activity", "activities"]
    if isinstance(action, WaitForUiTextAction):
        return prefix + ["shell", "uiautomator", "dump", "/sdcard/window.xml"]
    if isinstance(action, CaptureUiHierarchyAction):
        return prefix + ["exec-out", "uiautomator", "dump", "/dev/tty"]
    if isinstance(action, CaptureScreenshotAction):
        return prefix + ["exec-out", "screencap", "-p"]
    raise AndroidAdbError(f"unsupported Android action type: {type(action).__name__}")


__all__ = [
    "AdbBinaryIdentity",
    "AdbDevice",
    "AndroidAdbError",
    "attest_adb_binary",
    "compile_adb_action_argv",
    "parse_adb_devices",
    "select_online_device",
]
