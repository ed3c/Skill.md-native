from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .browser_contract import BrowserContract, BrowserReceipt
from .coding_contract import CodingAgentContract, CodingAgentReceipt
from .evidence import canonical_digest
from .models import EvidenceBundle, Limits, RunSpec, RuntimeBackend


_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_RESERVED_CHECK_IDS = frozenset(
    {
        "provenance-continuity",
        "runtime-continuity",
        "command-continuity",
        "input-continuity",
        "security-gate",
    }
)
_RESERVED_CHECK_PREFIXES = ("evidence:", "domain:")
_CODING_AGENT_EVIDENCE = frozenset(
    {
        "exit_code",
        "stdout",
        "stderr",
        "commands",
        "assertions",
        "runtime_metadata",
        "coding_receipt",
        "agent_events",
        "workspace_diff",
        "test_results",
    }
)
_BROWSER_EVIDENCE = frozenset(
    {
        "exit_code",
        "stdout",
        "stderr",
        "commands",
        "network",
        "assertions",
        "runtime_metadata",
        "browser_receipt",
        "browser_events",
        "dom_snapshot",
        "accessibility_snapshot",
        "network_trace",
        "screenshots",
        "downloads",
        "browser_assertions",
    }
)


class HarnessContractError(ValueError):
    """Raised when a harness contract cannot be compiled without weakening it."""


class HarnessDomain(str, Enum):
    CODING = "coding"
    BROWSER = "browser"
    ANDROID = "android"
    DESKTOP = "desktop"
    SRE = "sre"
    DOCUMENTS = "documents"
    VOICE = "voice"
    ROBOTICS = "robotics"
    CUSTOM = "custom"


class RuntimeCapability(str, Enum):
    KERNEL_OR_VM_ISOLATION = "kernel_or_vm_isolation"
    NETWORK_DENY_BY_DEFAULT = "network_deny_by_default"
    L7_HTTP_POLICY = "l7_http_policy"
    FILESYSTEM_POLICY = "filesystem_policy"
    BROKERED_SECRETS = "brokered_secrets"
    PROCESS_TELEMETRY = "process_telemetry"
    NETWORK_TELEMETRY = "network_telemetry"
    SNAPSHOT_RESTORE = "snapshot_restore"
    PERSISTENT_FILESYSTEM = "persistent_filesystem"
    GPU = "gpu"
    STDIN_STREAM = "stdin_stream"


class EvidenceKind(str, Enum):
    EXIT_CODE = "exit_code"
    STDOUT = "stdout"
    STDERR = "stderr"
    COMMANDS = "commands"
    PROCESSES = "processes"
    NETWORK = "network"
    FILESYSTEM_BEFORE = "filesystem_before"
    FILESYSTEM_AFTER = "filesystem_after"
    INFERENCE = "inference"
    ASSERTIONS = "assertions"
    FINDINGS = "findings"
    RUNTIME_METADATA = "runtime_metadata"
    POLICY = "policy"
    OCSF_EVENTS = "ocsf_events"
    CODING_RECEIPT = "coding_receipt"
    AGENT_EVENTS = "agent_events"
    WORKSPACE_DIFF = "workspace_diff"
    TEST_RESULTS = "test_results"
    BROWSER_RECEIPT = "browser_receipt"
    BROWSER_EVENTS = "browser_events"
    DOM_SNAPSHOT = "dom_snapshot"
    ACCESSIBILITY_SNAPSHOT = "accessibility_snapshot"
    NETWORK_TRACE = "network_trace"
    SCREENSHOTS = "screenshots"
    DOWNLOADS = "downloads"
    BROWSER_ASSERTIONS = "browser_assertions"


class VerdictStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HarnessIdentity(_StrictModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    version: str = Field(min_length=1)
    domain: HarnessDomain
    description: str = ""


class LicensingContract(_StrictModel):
    code: str = Field(min_length=1)
    models: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class EnvironmentContract(_StrictModel):
    allowed_runtimes: list[RuntimeBackend] = Field(min_length=1)
    required_capabilities: list[RuntimeCapability] = Field(default_factory=list)
    network: Literal["deny-by-default"] = "deny-by-default"
    filesystem: Literal["ephemeral", "persistent", "workspace-only"] = "ephemeral"
    secrets: Literal["brokered"] = "brokered"

    @model_validator(mode="after")
    def unique_values(self) -> "EnvironmentContract":
        if len(set(self.allowed_runtimes)) != len(self.allowed_runtimes):
            raise ValueError("allowed_runtimes must not contain duplicates")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("required_capabilities must not contain duplicates")
        return self


class InterfaceContract(_StrictModel):
    action_schema: str = "urn:skill-native:action:argv:v1"
    observation_schema: str = "urn:skill-native:observation:evidence-bundle:v1"
    protocols: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_protocols(self) -> "InterfaceContract":
        if len(set(self.protocols)) != len(self.protocols):
            raise ValueError("interfaces.protocols must not contain duplicates")
        return self


class ExecutionContract(_StrictModel):
    adapter: str = Field(min_length=1)
    command: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def non_empty_arguments(self) -> "ExecutionContract":
        if any(value == "" for value in self.command):
            raise ValueError("execution.command must contain non-empty argv strings")
        return self


class EvidenceContract(_StrictModel):
    capture: list[EvidenceKind] = Field(min_length=1)
    required: list[EvidenceKind] = Field(min_length=1)

    @model_validator(mode="after")
    def required_is_captured(self) -> "EvidenceContract":
        if len(set(self.capture)) != len(self.capture):
            raise ValueError("evidence.capture must not contain duplicates")
        if len(set(self.required)) != len(self.required):
            raise ValueError("evidence.required must not contain duplicates")
        missing = set(self.required) - set(self.capture)
        if missing:
            values = ", ".join(sorted(value.value for value in missing))
            raise ValueError(f"required evidence is not declared for capture: {values}")
        return self


class ExitCodeZeroVerifier(_StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["exit_code_zero"] = "exit_code_zero"


class AssertionTrueVerifier(_StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["assertion_true"] = "assertion_true"
    assertion: str = Field(min_length=1)


class StdoutContainsVerifier(_StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["stdout_contains"] = "stdout_contains"
    value: str = Field(min_length=1)


class StderrEmptyVerifier(_StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["stderr_empty"] = "stderr_empty"


class EvidencePresentVerifier(_StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["evidence_present"] = "evidence_present"
    evidence: EvidenceKind


VerifierSpec = Annotated[
    Union[
        ExitCodeZeroVerifier,
        AssertionTrueVerifier,
        StdoutContainsVerifier,
        StderrEmptyVerifier,
        EvidencePresentVerifier,
    ],
    Field(discriminator="kind"),
]


def _verifier_evidence(verifier: VerifierSpec) -> EvidenceKind:
    if isinstance(verifier, ExitCodeZeroVerifier):
        return EvidenceKind.EXIT_CODE
    if isinstance(verifier, AssertionTrueVerifier):
        return EvidenceKind.ASSERTIONS
    if isinstance(verifier, StdoutContainsVerifier):
        return EvidenceKind.STDOUT
    if isinstance(verifier, StderrEmptyVerifier):
        return EvidenceKind.STDERR
    if isinstance(verifier, EvidencePresentVerifier):
        return verifier.evidence
    raise HarnessContractError(f"unsupported verifier type: {type(verifier).__name__}")


class VerificationContract(_StrictModel):
    security_gate: Literal["fail-on-high-or-critical"] = "fail-on-high-or-critical"
    checks: list[VerifierSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_check_ids(self) -> "VerificationContract":
        ids = [check.id for check in self.checks]
        if len(set(ids)) != len(ids):
            raise ValueError("verification check ids must be unique")
        reserved = [
            check_id
            for check_id in ids
            if check_id in _RESERVED_CHECK_IDS
            or any(check_id.startswith(prefix) for prefix in _RESERVED_CHECK_PREFIXES)
        ]
        if reserved:
            raise ValueError(
                "verification check ids use reserved kernel identifiers: "
                + ", ".join(sorted(reserved))
            )
        return self


class BudgetContract(_StrictModel):
    timeout_seconds: int = Field(default=300, ge=1)
    max_model_calls: int = Field(default=20, ge=0)
    max_output_tokens: int = Field(default=20_000, ge=0)
    max_network_requests: int = Field(default=100, ge=0)


class ReplayContract(_StrictModel):
    supported: bool = False
    snapshot_required: bool = False

    @model_validator(mode="after")
    def snapshot_requires_replay(self) -> "ReplayContract":
        if self.snapshot_required and not self.supported:
            raise ValueError("snapshot_required=true requires replay.supported=true")
        return self


class HarnessManifest(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    identity: HarnessIdentity
    licensing: LicensingContract
    environment: EnvironmentContract
    interfaces: InterfaceContract = Field(default_factory=InterfaceContract)
    execution: ExecutionContract
    coding: CodingAgentContract | None = None
    browser: BrowserContract | None = None
    evidence: EvidenceContract
    verification: VerificationContract
    budgets: BudgetContract = Field(default_factory=BudgetContract)
    replay: ReplayContract = Field(default_factory=ReplayContract)
    failure_taxonomy: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cross_field_contract(self) -> "HarnessManifest":
        if self.execution.adapter == "coding.agent.v1":
            if self.identity.domain is not HarnessDomain.CODING:
                raise ValueError("coding.agent.v1 requires identity.domain=coding")
            if self.coding is None:
                raise ValueError("coding.agent.v1 requires a coding contract")
            required = {kind.value for kind in self.evidence.required}
            missing = sorted(_CODING_AGENT_EVIDENCE - required)
            if missing:
                raise ValueError(
                    "coding.agent.v1 requires mandatory coding evidence: "
                    + ", ".join(missing)
                )
        elif self.coding is not None:
            raise ValueError("coding contract is only valid with execution.adapter=coding.agent.v1")

        if self.execution.adapter == "browser.playwright.v1":
            if self.identity.domain is not HarnessDomain.BROWSER:
                raise ValueError("browser.playwright.v1 requires identity.domain=browser")
            if self.browser is None:
                raise ValueError("browser.playwright.v1 requires a browser contract")
            required = {kind.value for kind in self.evidence.required}
            missing = sorted(_BROWSER_EVIDENCE - required)
            if missing:
                raise ValueError(
                    "browser.playwright.v1 requires mandatory browser evidence: "
                    + ", ".join(missing)
                )
        elif self.browser is not None:
            raise ValueError(
                "browser contract is only valid with execution.adapter=browser.playwright.v1"
            )

        required_evidence = set(self.evidence.required)
        for check in self.verification.checks:
            dependency = _verifier_evidence(check)
            if dependency not in required_evidence:
                raise ValueError(
                    f"verifier {check.id!r} depends on {dependency.value!r}, "
                    "which must be mandatory evidence"
                )
        if any(not value for value in self.failure_taxonomy):
            raise ValueError("failure_taxonomy entries must be non-empty")
        if len(set(self.failure_taxonomy)) != len(self.failure_taxonomy):
            raise ValueError("failure_taxonomy must not contain duplicates")
        return self


class HarnessPlan(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    manifest_id: str
    manifest_version: str
    manifest_digest: str = Field(pattern=_DIGEST_PATTERN)
    provenance_digest: str = Field(pattern=_DIGEST_PATTERN)
    domain: HarnessDomain
    adapter: str
    runtime_backend: RuntimeBackend
    runtime_capabilities: dict[str, bool]
    run_spec: RunSpec
    command: list[str]
    stdin_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    required_evidence: list[EvidenceKind]
    checks: list[VerifierSpec]
    policy_digest: str = Field(pattern=_DIGEST_PATTERN)
    effective_limits: Limits
    plan_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_plan_integrity(self) -> "HarnessPlan":
        if self.run_spec.run_id != self.run_id:
            raise ValueError("run_spec.run_id does not match plan run_id")
        if self.run_spec.skill.provenance_digest != self.provenance_digest:
            raise ValueError("run_spec provenance digest does not match plan provenance digest")
        if self.run_spec.runtime.backend != self.runtime_backend:
            raise ValueError("run_spec runtime backend does not match plan runtime backend")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"plan_digest"}))
        if expected != self.plan_digest:
            raise ValueError("plan digest does not match plan payload")
        return self


class VerificationResult(_StrictModel):
    id: str
    kind: str
    passed: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class HarnessVerdict(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    manifest_digest: str = Field(pattern=_DIGEST_PATTERN)
    provenance_digest: str = Field(pattern=_DIGEST_PATTERN)
    plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    evidence_digest: str = Field(pattern=_DIGEST_PATTERN)
    runtime_backend: RuntimeBackend
    status: VerdictStatus
    security_gate: Literal["pass", "fail"]
    checks: list[VerificationResult]
    failed_check_ids: list[str]
    security_findings: list[dict[str, Any]] = Field(default_factory=list)
    verdict_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_verdict_integrity(self) -> "HarnessVerdict":
        expected_failed = [check.id for check in self.checks if not check.passed]
        if expected_failed != self.failed_check_ids:
            raise ValueError("failed_check_ids do not match failed checks")
        expected_status = VerdictStatus.FAIL if expected_failed else VerdictStatus.PASS
        if self.status != expected_status:
            raise ValueError("verdict status does not match failed checks")
        if self.security_gate == "fail" and "security-gate" not in self.failed_check_ids:
            raise ValueError("failed security gate is missing from failed_check_ids")
        expected_digest = canonical_digest(
            self.model_dump(mode="json", exclude={"verdict_digest"})
        )
        if expected_digest != self.verdict_digest:
            raise ValueError("verdict digest does not match verdict payload")
        return self


class HarnessRunResult(_StrictModel):
    plan: HarnessPlan
    evidence: EvidenceBundle
    verdict: HarnessVerdict
    evidence_path: str | None = None
    verdict_path: str | None = None


def load_harness_manifest(path: Path) -> HarnessManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise HarnessContractError("harness manifest must be a YAML object")
    return HarnessManifest.model_validate(raw)


def export_harness_schemas(output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    schemas = {
        "harness.schema.json": HarnessManifest.model_json_schema(),
        "harness-plan.schema.json": HarnessPlan.model_json_schema(),
        "harness-verdict.schema.json": HarnessVerdict.model_json_schema(),
        "coding-agent-receipt.schema.json": CodingAgentReceipt.model_json_schema(),
        "browser-receipt.schema.json": BrowserReceipt.model_json_schema(),
    }
    result: dict[str, Path] = {}
    for name, schema in schemas.items():
        path = output / name
        path.write_text(
            json.dumps(schema, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        result[name] = path
    return result
