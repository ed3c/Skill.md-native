from __future__ import annotations

from abc import ABC, abstractmethod
from string import Formatter

from .coding_agent import (
    build_runner_config,
    child_command_digest,
    contract_digest,
    encode_runner_config,
    parse_coding_receipt,
)
from .evidence import mark_evidence_captured
from .harness_contract import (
    HarnessContractError,
    HarnessDomain,
    HarnessManifest,
    HarnessPlan,
    VerificationResult,
)
from .models import EvidenceBundle, RunSpec


class DomainAdapter(ABC):
    adapter_id: str
    domain: HarnessDomain
    evidence_kinds: frozenset[str] = frozenset()

    @abstractmethod
    def compile_command(self, manifest: HarnessManifest, spec: RunSpec) -> list[str]: ...

    def compile_stdin(self, manifest: HarnessManifest, spec: RunSpec) -> str | None:
        return None

    def normalize_evidence(
        self,
        manifest: HarnessManifest,
        plan: HarnessPlan,
        evidence: EvidenceBundle,
    ) -> EvidenceBundle:
        return evidence

    def verify_evidence(
        self,
        manifest: HarnessManifest,
        plan: HarnessPlan,
        evidence: EvidenceBundle,
    ) -> list[VerificationResult]:
        return []


class _CommandTemplateRenderer:
    _formatter = Formatter()

    def __init__(self, allowed_fields: set[str]) -> None:
        self.allowed_fields = allowed_fields

    def render_command(
        self,
        values: list[str],
        context: dict[str, str],
    ) -> list[str]:
        return [self.render(value, context) for value in values]

    def render(self, value: str, context: dict[str, str]) -> str:
        for _, field_name, format_spec, conversion in self._formatter.parse(value):
            if field_name is None:
                continue
            if field_name not in self.allowed_fields:
                raise HarnessContractError(f"unsupported command placeholder: {field_name!r}")
            if format_spec or conversion:
                raise HarnessContractError(
                    "format specifiers and conversions are not allowed in command templates"
                )
        try:
            return value.format_map(context)
        except (KeyError, ValueError) as exc:
            raise HarnessContractError(f"invalid command template {value!r}") from exc


class CodingCommandAdapter(DomainAdapter):
    adapter_id = "coding.command.v1"
    domain = HarnessDomain.CODING
    _renderer = _CommandTemplateRenderer(
        {"entrypoint", "run_id", "scenario_id", "task", "skill_digest"}
    )

    def compile_command(self, manifest: HarnessManifest, spec: RunSpec) -> list[str]:
        return self._renderer.render_command(
            manifest.execution.command,
            _command_context(spec, include_task=True),
        )


class CodingAgentAdapter(DomainAdapter):
    adapter_id = "coding.agent.v1"
    domain = HarnessDomain.CODING
    runner_binary = "skill-native-coding-runner"
    _renderer = _CommandTemplateRenderer(
        {"entrypoint", "run_id", "scenario_id", "skill_digest"}
    )
    evidence_kinds = frozenset(
        {"coding_receipt", "agent_events", "workspace_diff", "test_results"}
    )

    def compile_command(self, manifest: HarnessManifest, spec: RunSpec) -> list[str]:
        contract = self._contract(manifest)
        child_command = self._compile_child_command(manifest, spec)
        config = build_runner_config(
            run_id=spec.run_id,
            task=spec.scenario.task,
            child_command=child_command,
            contract=contract,
        )
        return [
            self.runner_binary,
            "--config-b64",
            encode_runner_config(config),
            "--",
            *child_command,
        ]

    def compile_stdin(self, manifest: HarnessManifest, spec: RunSpec) -> str:
        contract = self._contract(manifest)
        task = spec.scenario.task
        if not task:
            raise HarnessContractError("coding.agent.v1 requires a non-empty scenario.task")
        if len(task.encode("utf-8")) > contract.max_task_bytes:
            raise HarnessContractError("scenario.task exceeds coding.max_task_bytes")
        return task

    def normalize_evidence(
        self,
        manifest: HarnessManifest,
        plan: HarnessPlan,
        evidence: EvidenceBundle,
    ) -> EvidenceBundle:
        assertions = dict(evidence.assertions)
        metadata = dict(evidence.runtime_metadata)
        try:
            contract = self._contract(manifest)
            receipt = parse_coding_receipt(evidence.stdout)
            child_command = self._compile_child_command(manifest, plan.run_spec)
            expected_contract_digest = contract_digest(contract)
            expected_child_digest = child_command_digest(child_command)
            expected_task_digest = plan.stdin_digest
            mismatches: list[str] = []
            if receipt.run_id != plan.run_id:
                mismatches.append("run_id")
            if receipt.driver != contract.driver:
                mismatches.append("driver")
            if receipt.driver_version != contract.driver_version:
                mismatches.append("driver_version")
            if receipt.contract_digest != expected_contract_digest:
                mismatches.append("contract_digest")
            if receipt.task_digest != expected_task_digest:
                mismatches.append("task_digest")
            if receipt.child_command_digest != expected_child_digest:
                mismatches.append("child_command_digest")
            if receipt.agent_process.argv != child_command:
                mismatches.append("agent_process.argv")
            if receipt.version_probe.argv != contract.version_command:
                mismatches.append("version_probe.argv")
            observed_tests = [result.argv for result in receipt.test_results]
            if observed_tests != contract.test_commands:
                mismatches.append("test_results.argv")
            if receipt.policy_checks["changed_file_budget"] is not (
                receipt.workspace_diff.changed_files <= contract.max_changed_files
            ):
                mismatches.append("changed_file_budget")
            if receipt.policy_checks["changed_byte_budget"] is not (
                receipt.workspace_diff.changed_bytes <= contract.max_changed_bytes
            ):
                mismatches.append("changed_byte_budget")
            if mismatches:
                raise ValueError(
                    "coding receipt does not preserve the plan: " + ", ".join(mismatches)
                )
        except Exception as exc:  # noqa: BLE001 - convert malformed child output to evidence
            assertions.update(
                {
                    "coding_receipt_valid": False,
                    "coding_outcome_pass": False,
                    "coding_policy_pass": False,
                    "coding_wrapper_exit_consistent": False,
                }
            )
            metadata["coding_agent"] = {
                "receipt_valid": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            return evidence.model_copy(
                update={"assertions": assertions, "runtime_metadata": metadata}
            )

        wrapper_exit_consistent = (receipt.outcome == "pass") == (evidence.exit_code == 0)
        assertions.update(
            {
                "coding_receipt_valid": True,
                "coding_outcome_pass": receipt.outcome == "pass",
                "coding_policy_pass": all(receipt.policy_checks.values()),
                "coding_wrapper_exit_consistent": wrapper_exit_consistent,
                "coding_tests_passed": all(result.passed for result in receipt.test_results),
                "coding_changes_allowed": (
                    not receipt.workspace_diff.disallowed_paths
                    and not receipt.workspace_diff.protected_paths
                ),
                "coding_driver_verified": receipt.version_probe.passed,
            }
        )
        metadata["coding_agent"] = {
            "receipt_valid": True,
            "receipt_digest": receipt.receipt_digest,
            "runner_version": receipt.runner_version,
            "driver": receipt.driver.value,
            "driver_version": receipt.driver_version,
            "outcome": receipt.outcome,
            "raw_event_count": receipt.raw_event_count,
            "event_parse_error": receipt.event_parse_error,
            "changed_files": receipt.workspace_diff.changed_files,
            "changed_bytes": receipt.workspace_diff.changed_bytes,
        }
        normalized = evidence.model_copy(
            update={
                "assertions": assertions,
                "runtime_metadata": metadata,
                "coding_receipt": receipt.model_dump(mode="json"),
                "agent_events": list(receipt.agent_events),
                "workspace_diff": receipt.workspace_diff.model_dump(mode="json"),
                "test_results": [
                    result.model_dump(mode="json") for result in receipt.test_results
                ],
            }
        )
        return mark_evidence_captured(normalized, self.evidence_kinds)

    def verify_evidence(
        self,
        manifest: HarnessManifest,
        plan: HarnessPlan,
        evidence: EvidenceBundle,
    ) -> list[VerificationResult]:
        checks = [
            (
                "domain:coding-receipt-continuity",
                "coding_receipt_valid",
                "coding receipt is valid and preserves the compiled plan",
            ),
            (
                "domain:coding-outcome",
                "coding_outcome_pass",
                "coding agent, deterministic tests, and workspace policy passed",
            ),
            (
                "domain:coding-policy",
                "coding_policy_pass",
                "all trusted coding-runner policy checks passed",
            ),
            (
                "domain:coding-wrapper-exit",
                "coding_wrapper_exit_consistent",
                "wrapper exit status is consistent with the coding receipt",
            ),
        ]
        return [
            VerificationResult(
                id=check_id,
                kind="coding_agent",
                passed=evidence.assertions.get(assertion) is True,
                message=(
                    message
                    if evidence.assertions.get(assertion) is True
                    else f"{message} — failed"
                ),
                details={"assertion": assertion},
            )
            for check_id, assertion, message in checks
        ]

    def _compile_child_command(
        self,
        manifest: HarnessManifest,
        spec: RunSpec,
    ) -> list[str]:
        return self._renderer.render_command(
            manifest.execution.command,
            _command_context(spec, include_task=False),
        )

    @staticmethod
    def _contract(manifest: HarnessManifest):
        if manifest.coding is None:
            raise HarnessContractError("coding.agent.v1 requires a coding contract")
        return manifest.coding


class DomainAdapterRegistry:
    def __init__(self, adapters: list[DomainAdapter] | None = None) -> None:
        self._adapters: dict[str, DomainAdapter] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: DomainAdapter) -> None:
        if not adapter.adapter_id:
            raise HarnessContractError("domain adapter id must not be empty")
        if adapter.adapter_id in self._adapters:
            raise HarnessContractError(f"duplicate domain adapter: {adapter.adapter_id}")
        self._adapters[adapter.adapter_id] = adapter

    def require(self, adapter_id: str) -> DomainAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise HarnessContractError(f"unknown domain adapter: {adapter_id}") from exc

    @classmethod
    def defaults(cls) -> "DomainAdapterRegistry":
        return cls([CodingCommandAdapter(), CodingAgentAdapter()])


def _command_context(spec: RunSpec, *, include_task: bool) -> dict[str, str]:
    context = {
        "entrypoint": spec.skill.entrypoint,
        "run_id": spec.run_id,
        "scenario_id": spec.scenario.id,
        "skill_digest": spec.skill.commit_or_digest,
    }
    if include_task:
        context["task"] = spec.scenario.task
    return context
