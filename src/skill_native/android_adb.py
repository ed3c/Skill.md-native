from __future__ import annotations

import hashlib
import os
import re
import stat as stat_module
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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

_SAFE_SERIAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_DEVICES_OUTPUT_BYTES = 1_000_000
_MAX_DEVICES = 128


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
    def validate_untrusted_device_line(self) -> "AdbDevice":
        if not _SAFE_SERIAL.fullmatch(self.serial):
            raise ValueError("ADB device serial contains unsafe characters")
        if any(ch.isspace() for ch in self.state) or len(self.state) > 64:
            raise ValueError("ADB device state must be a simple token")
        for key, value in self.attributes.items():
            if not key or any(ch.isspace() for ch in key) or ":" in key:
                raise ValueError("ADB device attribute keys must be simple tokens")
            if len(value) > 512:
                raise ValueError("ADB device attribute values are too long")
        return self


def attest_adb_binary(path: Path, *, reported_version: str) -> AdbBinaryIdentity:
    """Attest one opened executable object and refuse symlink substitution."""

    version = reported_version.strip()
    if not version or len(version) > 256:
        raise AndroidAdbError("ADB reported version is missing or too long")

    flags = os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise AndroidAdbError("platform cannot enforce O_NOFOLLOW for ADB attestation")
    flags |= nofollow

    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise AndroidAdbError("ADB executable does not exist") from exc
    except OSError as exc:
        raise AndroidAdbError(
            "ADB executable could not be opened without following links"
        ) from exc

    try:
        opened = os.fstat(fd)
        if not stat_module.S_ISREG(opened.st_mode):
            raise AndroidAdbError("ADB executable must be a regular file")
        if opened.st_mode & 0o111 == 0:
            raise AndroidAdbError("ADB executable is not executable")

        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

        after = os.fstat(fd)
        if (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise AndroidAdbError("ADB executable changed while being attested")
    finally:
        os.close(fd)

    # The digest is the identity authority. A future runner must bind execution
    # to this attestation instead of trusting a path string alone.
    resolved = path.resolve(strict=True)
    return AdbBinaryIdentity(
        path=str(resolved), version=version, sha256=digest.hexdigest()
    )


def parse_adb_devices(output: str) -> list[AdbDevice]:
    """Parse bounded `adb devices -l` output and reject unstructured text."""

    if len(output.encode("utf-8")) > _MAX_DEVICES_OUTPUT_BYTES:
        raise AndroidAdbError("ADB device listing exceeds the byte budget")

    lines = output.replace("\r\n", "\n").split("\n")
    devices: list[AdbDevice] = []
    seen: set[str] = set()

    for raw in lines:
        line = raw.strip()
        if (
            not line
            or line.startswith("List of devices attached")
            or line.startswith("* daemon")
        ):
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
                raise AndroidAdbError(
                    f"malformed ADB device attribute: {token!r}"
                )
            key, value = token.split(":", 1)
            if not key or not value or key in attributes:
                raise AndroidAdbError(f"invalid ADB device attribute: {token!r}")
            attributes[key] = value
        try:
            device = AdbDevice(
                serial=serial,
                state=state,
                attributes=attributes,
            )
        except ValidationError as exc:
            raise AndroidAdbError(
                f"invalid ADB device entry for serial {serial!r}"
            ) from exc
        devices.append(device)
        if len(devices) > _MAX_DEVICES:
            raise AndroidAdbError("ADB device listing exceeds the device budget")
    return devices


def select_online_device(
    devices: Iterable[AdbDevice], *, expected_serial: str | None
) -> AdbDevice:
    candidates = list(devices)
    if expected_serial is not None:
        if not _SAFE_SERIAL.fullmatch(expected_serial):
            raise AndroidAdbError(
                "expected Android device serial contains unsafe characters"
            )
        matches = [
            device for device in candidates if device.serial == expected_serial
        ]
        if len(matches) != 1:
            raise AndroidAdbError(
                "expected Android device serial is not uniquely present"
            )
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


def compile_adb_action_argv(
    *, adb_path: str, serial: str, action: AndroidAction
) -> list[str]:
    """Compile a bounded Android action into argv. No generic command exists."""

    if not adb_path or not Path(adb_path).is_absolute() or "\x00" in adb_path:
        raise AndroidAdbError("ADB path must be a non-empty absolute path")
    if not _SAFE_SERIAL.fullmatch(serial):
        raise AndroidAdbError("Android device serial contains unsafe characters")
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
        raise AndroidAdbError("wait actions are runner-local and have no ADB argv")
    if isinstance(action, WaitForPackageAction):
        return prefix + ["shell", "dumpsys", "window", "windows"]
    if isinstance(action, WaitForActivityAction):
        return prefix + ["shell", "dumpsys", "activity", "activities"]
    if isinstance(action, WaitForUiTextAction):
        return prefix + [
            "shell",
            "uiautomator",
            "dump",
            "/sdcard/window.xml",
        ]
    if isinstance(action, CaptureUiHierarchyAction):
        return prefix + [
            "exec-out",
            "uiautomator",
            "dump",
            "/dev/tty",
        ]
    if isinstance(action, CaptureScreenshotAction):
        return prefix + ["exec-out", "screencap", "-p"]
    raise AndroidAdbError(
        f"unsupported Android action type: {type(action).__name__}"
    )


__all__ = [
    "AdbBinaryIdentity",
    "AdbDevice",
    "AndroidAdbError",
    "attest_adb_binary",
    "compile_adb_action_argv",
    "parse_adb_devices",
    "select_online_device",
]
