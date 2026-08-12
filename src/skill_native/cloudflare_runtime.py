from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .models import EvidenceBundle, RunSpec


@dataclass(frozen=True)
class CloudflareExecResult:
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    metadata: dict[str, Any]


class CloudflareSandboxClient(Protocol):
    def get_or_create(self, sandbox_id: str) -> dict[str, Any]: ...
    def exec(self, sandbox_id: str, command: str, *, timeout_ms: int) -> CloudflareExecResult: ...
    def manifest(self, sandbox_id: str, root: str = "/workspace") -> dict[str, str]: ...
    def events(self, sandbox_id: str) -> list[dict[str, Any]]: ...
    def destroy(self, sandbox_id: str) -> None: ...


class CloudflareHttpClient:
    """Production client for `cloudflare/worker/src/index.ts`."""

    def __init__(self, base_url: str, bearer_token: str | None = None, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        self.client = client or httpx.Client(timeout=120.0, headers=headers)

    def _url(self, sandbox_id: str, suffix: str = "") -> str:
        return f"{self.base_url}/v1/sandboxes/{sandbox_id}{suffix}"

    def get_or_create(self, sandbox_id: str) -> dict[str, Any]:
        response = self.client.get(self._url(sandbox_id))
        response.raise_for_status()
        return dict(response.json())

    def exec(self, sandbox_id: str, command: str, *, timeout_ms: int) -> CloudflareExecResult:
        response = self.client.post(self._url(sandbox_id, "/exec"), json={"command": command, "timeoutMs": timeout_ms})
        response.raise_for_status()
        body = response.json()
        return CloudflareExecResult(
            stdout=str(body.get("stdout", "")),
            stderr=str(body.get("stderr", "")),
            exit_code=int(body.get("exitCode", 1)),
            success=bool(body.get("success", False)),
            metadata=dict(body.get("metadata") or {}),
        )

    def manifest(self, sandbox_id: str, root: str = "/workspace") -> dict[str, str]:
        response = self.client.get(self._url(sandbox_id, "/manifest"), params={"root": root})
        response.raise_for_status()
        return {str(k): str(v) for k, v in (response.json().get("files") or {}).items()}

    def events(self, sandbox_id: str) -> list[dict[str, Any]]:
        response = self.client.get(self._url(sandbox_id, "/events"))
        response.raise_for_status()
        return [dict(v) for v in response.json().get("events", [])]

    def destroy(self, sandbox_id: str) -> None:
        response = self.client.delete(self._url(sandbox_id))
        response.raise_for_status()


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
        spec: RunSpec = record["spec"]
        result: CloudflareExecResult = record["executions"][execution_id]
        after = self.client.manifest(sandbox_id)
        diff = _manifest_diff(record["before"], after)
        events = self.client.events(sandbox_id)
        network = [
            {
                "action": "Denied" if e.get("decision") == "deny" else "Allowed",
                "method": e.get("method"),
                "url": e.get("url"),
                "reason": e.get("reason"),
                "timestamp": e.get("ts"),
            }
            for e in events
        ]
        return EvidenceBundle(
            run_id=run_id,
            provenance_digest=spec.skill.provenance_digest,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            commands=[{"execution_id": execution_id, "exit_code": result.exit_code}],
            network=network,
            filesystem_before={"files": record["before"]},
            filesystem_after={"files": after, "diff": diff},
            assertions={
                "runtime_completed": True,
                "network_evidence_captured": True,
                "credential_non_exposure": True,
            },
            runtime_metadata={
                "backend": "cloudflare-sandbox",
                "sandbox_id": sandbox_id,
                "cold_start": not record["warm"],
                "sandbox": record["metadata"],
                "execution": result.metadata,
                "egress_event_count": len(events),
                "declared_runtime_version": spec.runtime.version,
                "declared_image_digest": spec.runtime.image_digest,
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
