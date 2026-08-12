from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QuotaClass(str, Enum):
    FREE = "free"
    PAID = "paid"
    LOCAL = "local"


class RuntimeBackend(str, Enum):
    OPENSHELL = "openshell"
    CLOUDFLARE = "cloudflare"
    ENROOT = "enroot"
    FAKE = "fake"


class SkillRef(BaseModel):
    source_url: str
    commit_or_digest: str
    entrypoint: str = "SKILL.md"
    provenance_digest: str | None = None


class AgentRef(BaseModel):
    harness: str
    version: str


class ModelRef(BaseModel):
    provider: str
    model: str
    quota_class: QuotaClass = QuotaClass.FREE


class RuntimeRef(BaseModel):
    backend: RuntimeBackend
    version: str
    image_digest: str


class NetworkRule(BaseModel):
    host: str
    port: int = 443
    protocol: str = "rest"
    access: str = "read-only"
    binaries: list[str] = Field(default_factory=lambda: ["/usr/bin/curl"])
    path: str | None = None


class SandboxPolicy(BaseModel):
    network: str = "deny-by-default"
    allowed_hosts: list[str] = Field(default_factory=list)
    network_rules: list[NetworkRule] = Field(default_factory=list)
    filesystem: str = "ephemeral"
    secrets: str = "brokered"
    landlock_compatibility: str = "hard_requirement"
    provider_names: list[str] = Field(default_factory=list)
    secret_env_names: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    task: str
    assertions: list[str] = Field(default_factory=list)


class Limits(BaseModel):
    timeout_seconds: int = 300
    max_model_calls: int = 20
    max_output_tokens: int = 20_000
    max_network_requests: int = 100


class RunSpec(BaseModel):
    run_id: str
    skill: SkillRef
    agent: AgentRef
    model: ModelRef
    runtime: RuntimeRef
    policy: SandboxPolicy = Field(default_factory=SandboxPolicy)
    scenario: Scenario
    limits: Limits = Field(default_factory=Limits)


class InferenceReceipt(BaseModel):
    provider: str
    model: str
    request_hash: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0
    price_usd: float = 0
    quota_class: QuotaClass
    rate_limit_headers: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    run_id: str | None = None


class EvidenceBundle(BaseModel):
    run_id: str
    provenance_digest: str | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    commands: list[dict[str, Any]] = Field(default_factory=list)
    processes: list[dict[str, Any]] = Field(default_factory=list)
    network: list[dict[str, Any]] = Field(default_factory=list)
    filesystem_before: dict[str, Any] = Field(default_factory=dict)
    filesystem_after: dict[str, Any] = Field(default_factory=dict)
    inference: list[InferenceReceipt] = Field(default_factory=list)
    assertions: dict[str, bool] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    runtime_metadata: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    ocsf_events: list[dict[str, Any]] = Field(default_factory=list)
