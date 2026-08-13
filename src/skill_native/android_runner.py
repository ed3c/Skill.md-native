from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .android_adb import (
    AdbBinaryIdentity,
    AdbDevice,
    AndroidAdbError,
    attest_adb_binary,
    compile_adb_action_argv,
    parse_adb_devices,
    select_online_device,
)
from .android_contract import AndroidAction, AndroidContract, WaitAction


class AndroidRunnerError(RuntimeError):
    """Raised when the trusted Android process boundary cannot complete safely."""


class AndroidCommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argv: list[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    duration_ms: int = Field(ge=0)
    timed_out: bool = False


class AndroidRunnerIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adb: AdbBinaryIdentity
    device: AdbDevice


class TrustedAndroidRunner:
    """Minimal trusted ADB subprocess boundary.

    The runner constructs every local argv itself, never invokes a local shell,
    bounds output and time, and requires ADB/device identity before actions.
    Receipt/evidence normalization belongs to later Android slices.
    """

    def __init__(
        self,
        *,
        adb_path: Path,
        max_stdout_bytes: int = 2_000_000,
        max_stderr_bytes: int = 1_000_000,
        process_timeout_seconds: float = 30.0,
    ) -> None:
        if not adb_path.is_absolute():
            raise AndroidRunnerError("ADB path must be absolute")
        if max_stdout_bytes < 1 or max_stderr_bytes < 1:
            raise AndroidRunnerError("process output budgets must be positive")
        if process_timeout_seconds <= 0 or process_timeout_seconds > 180:
            raise AndroidRunnerError("process timeout must be within (0, 180] seconds")
        self.adb_path = adb_path
        self.max_stdout_bytes = max_stdout_bytes
        self.max_stderr_bytes = max_stderr_bytes
        self.process_timeout_seconds = process_timeout_seconds

    def verify_identity(self, contract: AndroidContract) -> AndroidRunnerIdentity:
        version_result = self._run([str(self.adb_path), "version"])
        if version_result.returncode != 0:
            raise AndroidRunnerError("ADB version command failed")
        reported_version = version_result.stdout.decode("utf-8", errors="replace").strip()
        identity = attest_adb_binary(self.adb_path, reported_version=reported_version)
        if identity.sha256 != contract.adb_sha256:
            raise AndroidRunnerError("ADB executable digest does not match Android contract")
        if contract.adb_version not in identity.version:
            raise AndroidRunnerError("ADB version does not match Android contract")

        devices_result = self._run([str(self.adb_path), "devices", "-l"])
        if devices_result.returncode != 0:
            raise AndroidRunnerError("ADB device enumeration failed")
        try:
            devices = parse_adb_devices(
                devices_result.stdout.decode("utf-8", errors="strict")
            )
            selected = select_online_device(
                devices,
                expected_serial=contract.device.serial,
            )
        except (UnicodeDecodeError, AndroidAdbError) as exc:
            raise AndroidRunnerError(str(exc)) from exc
        return AndroidRunnerIdentity(adb=identity, device=selected)

    def execute_action(
        self,
        *,
        identity: AndroidRunnerIdentity,
        action: AndroidAction,
    ) -> AndroidCommandResult | None:
        if action.kind == "wait":
            if not isinstance(action, WaitAction):
                raise AndroidRunnerError("wait action type mismatch")
            time.sleep(action.duration_ms / 1000.0)
            return None
        try:
            argv = compile_adb_action_argv(
                adb_path=identity.adb.path,
                serial=identity.device.serial,
                action=action,
            )
        except AndroidAdbError as exc:
            raise AndroidRunnerError(str(exc)) from exc
        result = self._run(argv)
        if result.timed_out:
            raise AndroidRunnerError(f"Android action timed out: {action.kind}")
        if result.returncode != 0:
            raise AndroidRunnerError(
                f"Android action failed with exit code {result.returncode}: {action.kind}"
            )
        return result

    def _run(self, argv: list[str]) -> AndroidCommandResult:
        if not argv or argv[0] != str(self.adb_path):
            raise AndroidRunnerError("trusted runner may execute only the pinned ADB path")
        if any("\x00" in token for token in argv):
            raise AndroidRunnerError("argv contains a NUL byte")

        started = time.monotonic()
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            start_new_session=True,
            env={"LANG": "C", "LC_ALL": "C"},
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=self.process_timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate_process_group(process)
            stdout, stderr = process.communicate()

        duration_ms = max(0, int((time.monotonic() - started) * 1000))
        if len(stdout) > self.max_stdout_bytes:
            raise AndroidRunnerError("ADB stdout exceeded configured byte budget")
        if len(stderr) > self.max_stderr_bytes:
            raise AndroidRunnerError("ADB stderr exceeded configured byte budget")

        return AndroidCommandResult(
            argv=argv,
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
            return
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


__all__ = [
    "AndroidCommandResult",
    "AndroidRunnerError",
    "AndroidRunnerIdentity",
    "TrustedAndroidRunner",
]
