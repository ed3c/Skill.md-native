from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .models import EvidenceBundle, RunSpec


@dataclass(frozen=True)
class CloudflareExecResult:
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    metadata: dict[str, Any]


class CloudflareSandboxClient(Protocol):
    """Transport-neutral client matching Cloudflare Sandbox SDK semantics.

    A production implementation may live in a Worker/TypeScript bridge, while
    Python tests can use deterministic fakes. Raw provider credentials are not
    part of this interface.
    """

    def get_or_create(self, sandbox_id: str) -> dict[str, Any]: ...
    def exec(self, sandbox_id: str, command: str, *, timeout_ms: int) -> CloudflareExecResult: ...
    def manifest(self, sandbox_id: str, root: str = "/workspace") -> dict[str, str]: ...
    def destroy(self, sandbox_id: str) -> None: ...


class CloudflareRuntimeController:
    def __init__(self, client: CloudflareSandboxClient) -> None:
        self.client = client
        self._runs: dict[str, dict[str, Any]] = {}

    def prepare(self, spec: RunSpec) -> str:
        sandbox_id = f"skill-native-{spec.run_id}"
        metadata = self.client.get_or_create(sandbox_id)
        before = self.client.manifest(sandbox_id)
        self._runs[sandbox_id] = {
            "spec": spec,
            "metadata": metadata,
            "before": before,
            "executions": {},
            "warm": bool(metadata.get("reused", False)),
        }
        return sandbox_id

    def execute(self, sandbox_id: str, command: list[str]) -> str:
        record = self._runs[sandbox_id]
        spec: RunSpec = record["spec"]
        execution_id = f"{sandbox_id}:exec:{len(record['executions'])}"
        quoted = " ".join(_shell_quote(part) for part in command)
        result = self.client.exec(sandbox_id, quoted, timeout_ms=spec.limits.timeout_seconds * 1000)
        record["executions"][execution_id] = result
        return execution_id

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        sandbox_id = execution_id.split(":exec:", 1)[0]
        record = self._runs[sandbox_id]
        result: CloudflareExecResult = record["executions"][execution_id]
        after = self.client.manifest(sandbox_id)
        diff = _manifest_diff(record["before"], after)
        return EvidenceBundle(
            run_id=run_id,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            commands=[{"execution_id": execution_id, "exit_code": result.exit_code}],
            filesystem_before={"files": record["before"]},
            filesystem_after={"files": after, "diff": diff},
            assertions={"runtime_completed": True},
            runtime_metadata={
                "backend": "cloudflare-sandbox",
                "sandbox_id": sandbox_id,
                "cold_start": not record["warm"],
                "sandbox": record["metadata"],
                "execution": result.metadata,
            },
        )

    def destroy(self, sandbox_id: str) -> None:
        self.client.destroy(sandbox_id)
        self._runs.pop(sandbox_id, None)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _manifest_diff(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    before_keys, after_keys = set(before), set(after)
    return {
        "added": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "modified": sorted(k for k in before_keys & after_keys if before[k] != after[k]),
    }
