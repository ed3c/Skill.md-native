from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .cloudflare_runtime import CloudflareSandboxClient
from .evidence import mark_evidence_captured
from .models import EvidenceBundle, RunSpec, RuntimeBackend
from .openshell import OpenShellController
from .runtime_harness_controllers import (
    CloudflareHarnessController,
    OpenShellHarnessController,
)


@dataclass(frozen=True)
class RuntimeCapabilities:
    kernel_or_vm_isolation: bool
    network_deny_by_default: bool
    l7_http_policy: bool
    filesystem_policy: bool
    brokered_secrets: bool
    process_telemetry: bool
    snapshot_restore: bool
    persistent_filesystem: bool
    gpu: bool
    network_telemetry: bool = False
    stdin_stream: bool = False


class RuntimeAdapter(ABC):
    backend: RuntimeBackend
    capabilities: RuntimeCapabilities
    evidence_kinds: frozenset[str]

    @abstractmethod
    def prepare(self, spec: RunSpec) -> str: ...

    @abstractmethod
    def execute(
        self,
        sandbox_id: str,
        command: list[str],
        *,
        stdin: str | None = None,
    ) -> str: ...

    @abstractmethod
    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle: ...

    @abstractmethod
    def destroy(self, sandbox_id: str) -> None: ...


class FakeRuntime(RuntimeAdapter):
    backend = RuntimeBackend.FAKE
    evidence_kinds = frozenset({
        "exit_code", "stdout", "stderr", "commands", "assertions", "runtime_metadata"
    })
    capabilities = RuntimeCapabilities(
        kernel_or_vm_isolation=False,
        network_deny_by_default=True,
        l7_http_policy=False,
        filesystem_policy=True,
        brokered_secrets=True,
        process_telemetry=False,
        snapshot_restore=False,
        persistent_filesystem=False,
        gpu=False,
        network_telemetry=False,
        stdin_stream=True,
    )

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    def prepare(self, spec: RunSpec) -> str:
        sandbox_id = f"fake:{spec.run_id}"
        self._runs[sandbox_id] = {"spec": spec, "commands": []}
        return sandbox_id

    def execute(
        self,
        sandbox_id: str,
        command: list[str],
        *,
        stdin: str | None = None,
    ) -> str:
        execution_id = f"{sandbox_id}:exec:{len(self._runs[sandbox_id]['commands'])}"
        self._runs[sandbox_id]["commands"].append(
            {
                "execution_id": execution_id,
                "argv": command,
                "requested_argv": command,
                "stdin_digest": (
                    hashlib.sha256(stdin.encode("utf-8")).hexdigest()
                    if stdin is not None
                    else None
                ),
                "exit_code": 0,
            }
        )
        return execution_id

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        sandbox_id = execution_id.split(":exec:", 1)[0]
        record = self._runs[sandbox_id]
        spec: RunSpec = record["spec"]
        bundle = EvidenceBundle(
            run_id=run_id,
            provenance_digest=spec.skill.provenance_digest,
            exit_code=0,
            stdout="fake runtime execution\n",
            commands=record["commands"],
            assertions={"runtime_completed": True},
            runtime_metadata={"backend": "fake", "verification_state": "deterministic-mock"},
        )
        return mark_evidence_captured(
            bundle,
            self.evidence_kinds,
            runtime_backend=self.backend.value,
        )

    def destroy(self, sandbox_id: str) -> None:
        self._runs.pop(sandbox_id, None)


class OpenShellRuntime(RuntimeAdapter):
    backend = RuntimeBackend.OPENSHELL
    evidence_kinds = frozenset({
        "exit_code", "stdout", "stderr", "commands", "processes", "network",
        "filesystem_before", "filesystem_after", "assertions", "findings",
        "runtime_metadata", "policy", "ocsf_events",
    })
    capabilities = RuntimeCapabilities(
        kernel_or_vm_isolation=True,
        network_deny_by_default=True,
        l7_http_policy=True,
        filesystem_policy=True,
        brokered_secrets=True,
        process_telemetry=True,
        snapshot_restore=False,
        persistent_filesystem=True,
        gpu=True,
        network_telemetry=True,
        stdin_stream=True,
    )

    def __init__(self, controller: OpenShellController | None = None) -> None:
        self.controller = controller or OpenShellHarnessController()

    def prepare(self, spec: RunSpec) -> str:
        return self.controller.prepare(spec)

    def execute(
        self,
        sandbox_id: str,
        command: list[str],
        *,
        stdin: str | None = None,
    ) -> str:
        if stdin is None:
            return self.controller.execute(sandbox_id, command)
        try:
            return self.controller.execute(sandbox_id, command, stdin=stdin)
        except TypeError as exc:
            raise ValueError(
                "configured OpenShell controller does not support stdin streaming"
            ) from exc

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        return mark_evidence_captured(
            self.controller.collect(run_id, execution_id),
            self.evidence_kinds,
            runtime_backend=self.backend.value,
        )

    def destroy(self, sandbox_id: str) -> None:
        self.controller.destroy(sandbox_id)


class CloudflareRuntime(RuntimeAdapter):
    backend = RuntimeBackend.CLOUDFLARE
    evidence_kinds = frozenset({
        "exit_code", "stdout", "stderr", "commands", "network",
        "filesystem_before", "filesystem_after", "assertions", "runtime_metadata",
    })
    capabilities = RuntimeCapabilities(
        kernel_or_vm_isolation=True,
        network_deny_by_default=True,
        l7_http_policy=True,
        filesystem_policy=True,
        brokered_secrets=True,
        process_telemetry=False,
        snapshot_restore=False,
        persistent_filesystem=True,
        gpu=False,
        network_telemetry=True,
        stdin_stream=False,
    )

    def __init__(self, client: CloudflareSandboxClient) -> None:
        self.controller = CloudflareHarnessController(client)

    def prepare(self, spec: RunSpec) -> str:
        return self.controller.prepare(spec)

    def execute(
        self,
        sandbox_id: str,
        command: list[str],
        *,
        stdin: str | None = None,
    ) -> str:
        if stdin is not None:
            raise ValueError("Cloudflare runtime bridge does not support stdin streaming")
        return self.controller.execute(sandbox_id, command)

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        return mark_evidence_captured(
            self.controller.collect(run_id, execution_id),
            self.evidence_kinds,
            runtime_backend=self.backend.value,
        )

    def destroy(self, sandbox_id: str) -> None:
        self.controller.destroy(sandbox_id)


def runtime_capabilities_for(backend: RuntimeBackend) -> RuntimeCapabilities:
    profiles = {
        RuntimeBackend.FAKE: FakeRuntime.capabilities,
        RuntimeBackend.OPENSHELL: OpenShellRuntime.capabilities,
        RuntimeBackend.CLOUDFLARE: CloudflareRuntime.capabilities,
    }
    try:
        return profiles[backend]
    except KeyError as exc:
        raise ValueError(f"no capability profile for runtime backend: {backend.value}") from exc


def runtime_evidence_for(backend: RuntimeBackend) -> frozenset[str]:
    profiles = {
        RuntimeBackend.FAKE: FakeRuntime.evidence_kinds,
        RuntimeBackend.OPENSHELL: OpenShellRuntime.evidence_kinds,
        RuntimeBackend.CLOUDFLARE: CloudflareRuntime.evidence_kinds,
    }
    try:
        return profiles[backend]
    except KeyError as exc:
        raise ValueError(f"no evidence profile for runtime backend: {backend.value}") from exc
