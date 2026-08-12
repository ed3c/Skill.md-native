from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .cloudflare_runtime import CloudflareRuntimeController, CloudflareSandboxClient
from .models import EvidenceBundle, RunSpec, RuntimeBackend
from .openshell import OpenShellController


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


class RuntimeAdapter(ABC):
    backend: RuntimeBackend
    capabilities: RuntimeCapabilities

    @abstractmethod
    def prepare(self, spec: RunSpec) -> str: ...

    @abstractmethod
    def execute(self, sandbox_id: str, command: list[str]) -> str: ...

    @abstractmethod
    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle: ...

    @abstractmethod
    def destroy(self, sandbox_id: str) -> None: ...


class FakeRuntime(RuntimeAdapter):
    backend = RuntimeBackend.FAKE
    capabilities = RuntimeCapabilities(False, True, False, True, True, True, True, False, False)

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    def prepare(self, spec: RunSpec) -> str:
        sandbox_id = f"fake:{spec.run_id}"
        self._runs[sandbox_id] = {"spec": spec, "commands": []}
        return sandbox_id

    def execute(self, sandbox_id: str, command: list[str]) -> str:
        execution_id = f"{sandbox_id}:exec:{len(self._runs[sandbox_id]['commands'])}"
        self._runs[sandbox_id]["commands"].append({"execution_id": execution_id, "argv": command, "exit_code": 0})
        return execution_id

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        sandbox_id = execution_id.split(":exec:", 1)[0]
        record = self._runs[sandbox_id]
        spec: RunSpec = record["spec"]
        return EvidenceBundle(
            run_id=run_id,
            provenance_digest=spec.skill.provenance_digest,
            exit_code=0,
            stdout="fake runtime execution\n",
            commands=record["commands"],
            assertions={"runtime_completed": True},
            runtime_metadata={"backend": "fake"},
        )

    def destroy(self, sandbox_id: str) -> None:
        self._runs.pop(sandbox_id, None)


class OpenShellRuntime(RuntimeAdapter):
    backend = RuntimeBackend.OPENSHELL
    capabilities = RuntimeCapabilities(True, True, True, True, True, True, False, True, True)

    def __init__(self, controller: OpenShellController | None = None) -> None:
        self.controller = controller or OpenShellController()

    def prepare(self, spec: RunSpec) -> str:
        return self.controller.prepare(spec)

    def execute(self, sandbox_id: str, command: list[str]) -> str:
        return self.controller.execute(sandbox_id, command)

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        return self.controller.collect(run_id, execution_id)

    def destroy(self, sandbox_id: str) -> None:
        self.controller.destroy(sandbox_id)


class CloudflareRuntime(RuntimeAdapter):
    backend = RuntimeBackend.CLOUDFLARE
    capabilities = RuntimeCapabilities(True, True, True, True, True, False, False, True, False)

    def __init__(self, client: CloudflareSandboxClient) -> None:
        self.controller = CloudflareRuntimeController(client)

    def prepare(self, spec: RunSpec) -> str:
        return self.controller.prepare(spec)

    def execute(self, sandbox_id: str, command: list[str]) -> str:
        return self.controller.execute(sandbox_id, command)

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        return self.controller.collect(run_id, execution_id)

    def destroy(self, sandbox_id: str) -> None:
        self.controller.destroy(sandbox_id)
