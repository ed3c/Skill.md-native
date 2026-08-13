from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from .evidence import mark_evidence_captured
from .models import EvidenceBundle, RunSpec, RuntimeBackend
from .runtime import RuntimeAdapter, RuntimeCapabilities


class LocalBrowserFixtureRuntime(RuntimeAdapter):
    """Non-isolated subprocess runtime for deterministic browser integration only.

    The backend intentionally remains ``fake`` so evidence can never be confused with
    OpenShell or Cloudflare isolation. The runtime executes the trusted browser runner
    in an operator-owned temporary workspace and labels every result accordingly.
    """

    backend = RuntimeBackend.FAKE
    evidence_kinds = frozenset(
        {"exit_code", "stdout", "stderr", "commands", "assertions", "runtime_metadata"}
    )
    capabilities = RuntimeCapabilities(
        kernel_or_vm_isolation=False,
        network_deny_by_default=False,
        l7_http_policy=False,
        filesystem_policy=False,
        brokered_secrets=False,
        process_telemetry=False,
        snapshot_restore=False,
        persistent_filesystem=False,
        gpu=False,
        network_telemetry=False,
        stdin_stream=False,
    )

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self._runs: dict[str, dict[str, Any]] = {}

    def prepare(self, spec: RunSpec) -> str:
        self.workspace.mkdir(parents=True, exist_ok=True)
        sandbox_id = f"browser-fixture:{spec.run_id}"
        self._runs[sandbox_id] = {"spec": spec, "executions": {}}
        return sandbox_id

    def execute(
        self,
        sandbox_id: str,
        command: list[str],
        *,
        stdin: str | None = None,
    ) -> str:
        if stdin is not None:
            raise ValueError("local browser fixture runtime does not accept stdin")
        record = self._runs[sandbox_id]
        spec: RunSpec = record["spec"]
        execution_id = f"{sandbox_id}:exec:{len(record['executions'])}"
        process = subprocess.run(
            command,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=spec.limits.timeout_seconds,
            check=False,
        )
        record["executions"][execution_id] = {
            "argv": list(command),
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
        return execution_id

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        sandbox_id = execution_id.rsplit(":exec:", 1)[0]
        record = self._runs[sandbox_id]
        spec: RunSpec = record["spec"]
        execution = record["executions"][execution_id]
        bundle = EvidenceBundle(
            run_id=run_id,
            provenance_digest=spec.skill.provenance_digest,
            exit_code=execution["returncode"],
            stdout=execution["stdout"],
            stderr=execution["stderr"],
            commands=[
                {
                    "execution_id": execution_id,
                    "argv": execution["argv"],
                    "requested_argv": execution["argv"],
                    "stdin_digest": None,
                    "exit_code": execution["returncode"],
                }
            ],
            assertions={"runtime_completed": True},
            runtime_metadata={
                "backend": "local-browser-fixture",
                "runtime_backend": self.backend.value,
                "verification_state": "deterministic-local-browser-integration",
                "isolation": "none",
                "workspace_root": str(self.workspace),
                "command_digest": hashlib.sha256(
                    "\0".join(execution["argv"]).encode("utf-8")
                ).hexdigest(),
            },
        )
        return mark_evidence_captured(
            bundle,
            self.evidence_kinds,
            runtime_backend=self.backend.value,
        )

    def destroy(self, sandbox_id: str) -> None:
        self._runs.pop(sandbox_id, None)


__all__ = ["LocalBrowserFixtureRuntime"]
