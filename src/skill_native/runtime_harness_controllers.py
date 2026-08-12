from __future__ import annotations

import hashlib
import inspect
import subprocess
from typing import Any

from .cloudflare_runtime import CloudflareRuntimeController, CloudflareSandboxClient
from .models import EvidenceBundle
from .openshell import (
    CommandResult,
    CommandRunner,
    OpenShellController,
    OpenShellError,
    SubprocessRunner,
)


class _InputAwareRunner:
    """Add one-shot stdin support without changing the OpenShell controller API.

    The proxy is trusted harness code. It arms stdin for exactly one subsequent
    command, which is the ``sandbox exec`` call issued by ``OpenShellController``.
    """

    def __init__(self, delegate: CommandRunner) -> None:
        self.delegate = delegate
        self._armed = False
        self._input_text: str | None = None

    def arm(self, input_text: str) -> None:
        if self._armed:
            raise OpenShellError("OpenShell stdin runner is already armed")
        self._armed = True
        self._input_text = input_text

    def clear(self) -> None:
        self._armed = False
        self._input_text = None

    def run(self, argv: list[str], *, timeout: int | None = None) -> CommandResult:
        if not self._armed:
            return self.delegate.run(argv, timeout=timeout)
        input_text = self._input_text
        self.clear()
        parameters = inspect.signature(self.delegate.run).parameters
        if "input_text" in parameters:
            return self.delegate.run(  # type: ignore[call-arg]
                argv,
                timeout=timeout,
                input_text=input_text,
            )
        if isinstance(self.delegate, SubprocessRunner):
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                input=input_text,
            )
            return CommandResult(
                argv=argv,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        raise OpenShellError(
            "configured OpenShell command runner cannot stream stdin"
        )


class OpenShellHarnessController(OpenShellController):
    """OpenShell controller extension for task-input and command continuity."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        binary: str = "openshell",
    ) -> None:
        delegate = runner or SubprocessRunner()
        self._input_runner = _InputAwareRunner(delegate)
        self._harness_executions: dict[str, dict[str, Any]] = {}
        super().__init__(runner=self._input_runner, binary=binary)

    def execute(
        self,
        sandbox_id: str,
        command: list[str],
        *,
        stdin: str | None = None,
    ) -> str:
        if stdin is not None:
            self._input_runner.arm(stdin)
        try:
            execution_id = super().execute(sandbox_id, command)
        finally:
            self._input_runner.clear()
        self._harness_executions[execution_id] = {
            "requested_argv": list(command),
            "stdin_digest": (
                hashlib.sha256(stdin.encode("utf-8")).hexdigest()
                if stdin is not None
                else None
            ),
        }
        return execution_id

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        bundle = super().collect(run_id, execution_id)
        continuity = self._harness_executions.get(execution_id)
        if continuity is None:
            raise OpenShellError("OpenShell command continuity evidence unavailable")
        commands = [dict(value) for value in bundle.commands]
        if not commands:
            raise OpenShellError("OpenShell command evidence unavailable")
        commands[0].update(continuity)
        return bundle.model_copy(update={"commands": commands})

    def destroy(self, sandbox_id: str) -> None:
        try:
            super().destroy(sandbox_id)
        finally:
            prefix = f"{sandbox_id}:exec:"
            for execution_id in list(self._harness_executions):
                if execution_id.startswith(prefix):
                    self._harness_executions.pop(execution_id, None)


class CloudflareHarnessController(CloudflareRuntimeController):
    """Add argv continuity to the existing Cloudflare runtime controller."""

    def __init__(self, client: CloudflareSandboxClient) -> None:
        super().__init__(client)
        self._harness_commands: dict[str, list[str]] = {}

    def execute(self, sandbox_id: str, command: list[str]) -> str:
        execution_id = super().execute(sandbox_id, command)
        self._harness_commands[execution_id] = list(command)
        return execution_id

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        bundle = super().collect(run_id, execution_id)
        requested = self._harness_commands.get(execution_id)
        if requested is None:
            raise ValueError("Cloudflare command continuity evidence unavailable")
        commands = [dict(value) for value in bundle.commands]
        if not commands:
            raise ValueError("Cloudflare command evidence unavailable")
        commands[0].update(
            {"requested_argv": requested, "stdin_digest": None}
        )
        return bundle.model_copy(update={"commands": commands})

    def destroy(self, sandbox_id: str) -> None:
        try:
            super().destroy(sandbox_id)
        finally:
            prefix = f"{sandbox_id}:exec:"
            for execution_id in list(self._harness_commands):
                if execution_id.startswith(prefix):
                    self._harness_commands.pop(execution_id, None)
