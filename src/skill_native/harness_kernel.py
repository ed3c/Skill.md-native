from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .evidence import (
    EvidenceStore,
    attach_run_receipts,
    canonical_digest,
    captured_evidence,
)
from .harness_adapters import DomainAdapterRegistry
from .harness_contract import (
    BudgetContract,
    EvidenceKind,
    HarnessContractError,
    HarnessManifest,
    HarnessPlan,
    HarnessRunResult,
    HarnessVerdict,
    VerificationResult,
    VerdictStatus,
)
from .harness_verifiers import evaluate_verifier, evidence_present
from .models import EvidenceBundle, Limits, RunSpec
from .policy import ReceiptLedger
from .runtime import (
    RuntimeAdapter,
    RuntimeCapabilities,
    runtime_capabilities_for,
    runtime_evidence_for,
)
from .security import evaluate_security


_HARNESS_SUPPLIED_EVIDENCE = frozenset({"inference"})


@dataclass(frozen=True)
class HarnessVerdictStore:
    root: Path

    def persist(self, verdict: HarnessVerdict) -> tuple[str, Path]:
        payload = verdict.model_dump(mode="json")
        digest = canonical_digest(
            {key: value for key, value in payload.items() if key != "verdict_digest"}
        )
        if digest != verdict.verdict_digest:
            raise HarnessContractError("verdict digest does not match verdict payload")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{digest}.json"
        if not path.exists():
            path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return digest, path


class HarnessKernel:
    def __init__(self, registry: DomainAdapterRegistry | None = None) -> None:
        self.registry = registry or DomainAdapterRegistry.defaults()

    def compile(
        self,
        manifest: HarnessManifest,
        spec: RunSpec,
        *,
        capabilities: RuntimeCapabilities | None = None,
        available_evidence: frozenset[str] | None = None,
    ) -> HarnessPlan:
        adapter = self.registry.require(manifest.execution.adapter)
        if adapter.domain != manifest.identity.domain:
            raise HarnessContractError(
                f"adapter {adapter.adapter_id!r} serves {adapter.domain.value!r}, "
                f"not {manifest.identity.domain.value!r}"
            )
        if spec.runtime.backend not in manifest.environment.allowed_runtimes:
            raise HarnessContractError(
                f"runtime {spec.runtime.backend.value!r} is outside the manifest allowlist"
            )

        if not spec.skill.provenance_digest:
            raise HarnessContractError(
                "RunSpec.skill.provenance_digest is required for harness execution"
            )
        mutable_refs = {"main", "master", "head", "latest", "pin_me", "none"}
        if spec.skill.commit_or_digest.strip().lower() in mutable_refs:
            raise HarnessContractError("RunSpec.skill.commit_or_digest must be immutable")

        try:
            effective_capabilities = capabilities or runtime_capabilities_for(
                spec.runtime.backend
            )
            effective_evidence = set(
                available_evidence or runtime_evidence_for(spec.runtime.backend)
            )
        except ValueError as exc:
            raise HarnessContractError(str(exc)) from exc
        effective_evidence.update(_HARNESS_SUPPLIED_EVIDENCE)

        missing_capabilities = [
            capability.value
            for capability in manifest.environment.required_capabilities
            if not bool(getattr(effective_capabilities, capability.value, False))
        ]
        if missing_capabilities:
            raise HarnessContractError(
                "runtime is missing required capabilities: "
                + ", ".join(sorted(missing_capabilities))
            )
        if manifest.replay.snapshot_required and not effective_capabilities.snapshot_restore:
            raise HarnessContractError(
                "manifest requires snapshot replay but the runtime cannot snapshot/restore"
            )

        requested_evidence = {kind.value for kind in manifest.evidence.capture}
        unsupported_evidence = requested_evidence - effective_evidence
        if unsupported_evidence:
            raise HarnessContractError(
                "runtime/harness cannot collect declared evidence: "
                + ", ".join(sorted(unsupported_evidence))
            )

        policy = spec.policy
        if policy.network != manifest.environment.network:
            raise HarnessContractError(
                f"RunSpec network policy {policy.network!r} does not satisfy "
                f"{manifest.environment.network!r}"
            )
        if policy.secrets != manifest.environment.secrets:
            raise HarnessContractError(
                f"RunSpec secret policy {policy.secrets!r} does not satisfy "
                f"{manifest.environment.secrets!r}"
            )
        if policy.filesystem != manifest.environment.filesystem:
            raise HarnessContractError(
                f"RunSpec filesystem policy {policy.filesystem!r} does not satisfy "
                f"{manifest.environment.filesystem!r}"
            )

        self._validate_limits(spec.limits, manifest.budgets)
        command = adapter.compile_command(manifest, spec)
        if not command:
            raise HarnessContractError("domain adapter compiled an empty command")

        manifest_payload = manifest.model_dump(mode="json")
        plan_payload: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": spec.run_id,
            "manifest_id": manifest.identity.id,
            "manifest_version": manifest.identity.version,
            "manifest_digest": canonical_digest(manifest_payload),
            "provenance_digest": spec.skill.provenance_digest,
            "domain": manifest.identity.domain,
            "adapter": adapter.adapter_id,
            "runtime_backend": spec.runtime.backend,
            "runtime_capabilities": asdict(effective_capabilities),
            "run_spec": spec,
            "command": command,
            "required_evidence": manifest.evidence.required,
            "checks": manifest.verification.checks,
            "policy_digest": canonical_digest(policy.model_dump(mode="json")),
            "effective_limits": spec.limits,
        }
        normalized = _json_payload(plan_payload)
        plan_digest = canonical_digest(normalized)
        return HarnessPlan.model_validate({**normalized, "plan_digest": plan_digest})

    def run(
        self,
        manifest: HarnessManifest,
        spec: RunSpec,
        runtime: RuntimeAdapter,
        *,
        ledger: ReceiptLedger | None = None,
        evidence_store: EvidenceStore | None = None,
        verdict_store: HarnessVerdictStore | None = None,
    ) -> HarnessRunResult:
        if runtime.backend != spec.runtime.backend:
            raise HarnessContractError(
                f"runtime adapter backend {runtime.backend.value!r} does not match RunSpec "
                f"backend {spec.runtime.backend.value!r}"
            )
        plan = self.compile(
            manifest,
            spec,
            capabilities=runtime.capabilities,
            available_evidence=runtime.evidence_kinds,
        )
        sandbox_id = runtime.prepare(spec)
        try:
            execution_id = runtime.execute(sandbox_id, plan.command)
            evidence = attach_run_receipts(
                runtime.collect(spec.run_id, execution_id), ledger
            )
        finally:
            runtime.destroy(sandbox_id)

        verdict = self.verify(manifest, plan, evidence)
        evidence_path: str | None = None
        verdict_path: str | None = None
        if evidence_store is not None:
            _, path = evidence_store.persist(evidence)
            evidence_path = str(path)
        if verdict_store is not None:
            _, path = verdict_store.persist(verdict)
            verdict_path = str(path)
        return HarnessRunResult(
            plan=plan,
            evidence=evidence,
            verdict=verdict,
            evidence_path=evidence_path,
            verdict_path=verdict_path,
        )

    def verify(
        self,
        manifest: HarnessManifest,
        plan: HarnessPlan,
        evidence: EvidenceBundle,
    ) -> HarnessVerdict:
        expected_manifest_digest = canonical_digest(manifest.model_dump(mode="json"))
        if expected_manifest_digest != plan.manifest_digest:
            raise HarnessContractError(
                "manifest digest does not match the manifest compiled into the plan"
            )
        if evidence.run_id != plan.run_id:
            raise HarnessContractError(
                f"evidence run_id {evidence.run_id!r} does not match "
                f"plan run_id {plan.run_id!r}"
            )

        checks: list[VerificationResult] = []
        provenance_matches = evidence.provenance_digest == plan.provenance_digest
        checks.append(
            VerificationResult(
                id="provenance-continuity",
                kind="provenance",
                passed=provenance_matches,
                message=(
                    "evidence preserves the planned provenance digest"
                    if provenance_matches
                    else "evidence provenance digest does not match the execution plan"
                ),
                details={
                    "planned": plan.provenance_digest,
                    "observed": evidence.provenance_digest,
                },
            )
        )

        observed_backend = evidence.runtime_metadata.get("runtime_backend")
        runtime_matches = observed_backend == plan.runtime_backend.value
        checks.append(
            VerificationResult(
                id="runtime-continuity",
                kind="runtime",
                passed=runtime_matches,
                message=(
                    "evidence preserves the planned runtime backend"
                    if runtime_matches
                    else "evidence runtime backend does not match the execution plan"
                ),
                details={
                    "planned": plan.runtime_backend.value,
                    "observed": observed_backend,
                },
            )
        )

        for kind in manifest.evidence.required:
            present = evidence_present(evidence, kind)
            checks.append(
                VerificationResult(
                    id=f"evidence:{kind.value}",
                    kind="required_evidence",
                    passed=present,
                    message=(
                        f"required evidence {kind.value!r} is present"
                        if present
                        else f"required evidence {kind.value!r} is missing"
                    ),
                    details={"evidence": kind.value},
                )
            )

        for verifier in manifest.verification.checks:
            checks.append(evaluate_verifier(verifier, evidence))

        security = evaluate_security(evidence)
        security_passed = security.security_gate == "pass"
        checks.append(
            VerificationResult(
                id="security-gate",
                kind="security_gate",
                passed=security_passed,
                message=(
                    "no High/Critical security finding"
                    if security_passed
                    else "High/Critical security finding forces a failed verdict"
                ),
                evidence_ids=[
                    str(finding["evidence_id"])
                    for finding in security.findings
                    if finding.get("evidence_id")
                ],
                details={"finding_count": len(security.findings)},
            )
        )

        failed = [check.id for check in checks if not check.passed]
        verdict_payload: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": plan.run_id,
            "manifest_digest": plan.manifest_digest,
            "provenance_digest": plan.provenance_digest,
            "plan_digest": plan.plan_digest,
            "evidence_digest": canonical_digest(evidence.model_dump(mode="json")),
            "runtime_backend": plan.runtime_backend,
            "status": VerdictStatus.FAIL if failed else VerdictStatus.PASS,
            "security_gate": security.security_gate,
            "checks": checks,
            "failed_check_ids": failed,
            "security_findings": list(security.findings),
        }
        normalized = _json_payload(verdict_payload)
        verdict_digest = canonical_digest(normalized)
        return HarnessVerdict.model_validate(
            {**normalized, "verdict_digest": verdict_digest}
        )

    @staticmethod
    def _validate_limits(limits: Limits, budgets: BudgetContract) -> None:
        pairs = {
            "timeout_seconds": (limits.timeout_seconds, budgets.timeout_seconds),
            "max_model_calls": (limits.max_model_calls, budgets.max_model_calls),
            "max_output_tokens": (limits.max_output_tokens, budgets.max_output_tokens),
            "max_network_requests": (
                limits.max_network_requests,
                budgets.max_network_requests,
            ),
        }
        exceeded = [name for name, (actual, maximum) in pairs.items() if actual > maximum]
        if exceeded:
            details = ", ".join(
                f"{name}={pairs[name][0]}>{pairs[name][1]}" for name in sorted(exceeded)
            )
            raise HarnessContractError(f"RunSpec exceeds manifest budgets: {details}")


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_payload(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value
