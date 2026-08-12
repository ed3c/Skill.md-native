from __future__ import annotations

from typing import Any, Mapping

from .run_artifact_common import (
    EvaluatorAuthority,
    RunArtifactError,
    _HEX_64,
    _MUTABLE_REFS,
    _is_sha256_reference,
    _json_mapping,
    _json_payload,
    _require_str,
    canonical_digest,
)
from .run_artifact_contract import (
    LogicalTrace,
    LogicalTraceSpan,
    OutcomeScorecard,
    ReplayClass,
    ReplayManifest,
    ScorecardTier,
    TraceSpanStatus,
)
from .run_artifact_graph import _captured_evidence


class _DerivedBuilderMixin:
    @staticmethod
    def _build_replay(
        authority: EvaluatorAuthority,
        plan: Mapping[str, Any],
        evidence: Mapping[str, Any],
    ) -> ReplayManifest:
        run_spec = _json_mapping(plan.get("run_spec"), "plan.run_spec")
        runtime = _json_mapping(run_spec.get("runtime"), "plan.run_spec.runtime")
        capabilities = _json_mapping(
            plan.get("runtime_capabilities", {}), "plan.runtime_capabilities"
        )
        snapshot_capable = capabilities.get("snapshot_restore") is True
        snapshot_digest = _find_snapshot_digest(
            _json_mapping(
                evidence.get("runtime_metadata", {}), "evidence.runtime_metadata"
            )
        )
        runtime_image = _require_str(runtime, "image_digest", "plan.run_spec.runtime")
        runtime_version = _require_str(runtime, "version", "plan.run_spec.runtime")
        reasons: list[str] = []

        exact = (
            snapshot_capable
            and snapshot_digest is not None
            and _is_sha256_reference(runtime_image)
        )
        if exact:
            replay_class = ReplayClass.EXACT
        else:
            replay_class = ReplayClass.PARTIAL
            if not snapshot_capable:
                reasons.append("runtime-does-not-support-snapshot-restore")
            if snapshot_digest is None:
                reasons.append("snapshot-digest-not-captured")
            if not _is_sha256_reference(runtime_image):
                reasons.append("runtime-image-is-not-a-sha256-pin")
            if runtime_version.strip().lower() in _MUTABLE_REFS:
                replay_class = ReplayClass.NONE
                reasons.append("runtime-version-is-mutable")

        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": _require_str(plan, "run_id", "plan"),
            "plan_digest": _require_str(plan, "plan_digest", "plan"),
            "authority_digest": authority.authority_digest,
            "provenance_digest": _require_str(plan, "provenance_digest", "plan"),
            "policy_digest": _require_str(plan, "policy_digest", "plan"),
            "command_digest": canonical_digest(plan.get("command", [])),
            "stdin_digest": plan.get("stdin_digest"),
            "runtime_backend": _require_str(plan, "runtime_backend", "plan"),
            "runtime_version": runtime_version,
            "runtime_image_digest": runtime_image,
            "snapshot_capable": snapshot_capable,
            "snapshot_digest": snapshot_digest,
            "replay_class": replay_class,
            "reasons": sorted(set(reasons)),
        }
        normalized = _json_payload(payload)
        return ReplayManifest.model_validate(
            {**normalized, "replay_digest": canonical_digest(normalized)}
        )

    @staticmethod
    def _build_trace(
        authority: EvaluatorAuthority,
        plan: Mapping[str, Any],
        plan_digest: str,
        evidence: Mapping[str, Any],
        evidence_digest: str,
        verdict: Mapping[str, Any],
        verdict_digest: str,
    ) -> LogicalTrace:
        trace_id = canonical_digest(["logical-trace", plan_digest])[:32]
        spans: list[LogicalTraceSpan] = []

        def add_span(
            name: str,
            *,
            parent: str | None,
            status: TraceSpanStatus,
            attributes: dict[str, Any],
        ) -> str:
            normalized_attributes = _json_payload(attributes)
            span_id = canonical_digest(
                {
                    "parent_span_id": parent,
                    "name": name,
                    "kind": "internal",
                    "status": status.value,
                    "attributes": normalized_attributes,
                }
            )[:16]
            spans.append(
                LogicalTraceSpan(
                    span_id=span_id,
                    parent_span_id=parent,
                    name=name,
                    status=status,
                    attributes=normalized_attributes,
                )
            )
            return span_id

        authority_span = add_span(
            "skill-native.authority.resolve",
            parent=None,
            status=TraceSpanStatus.OK,
            attributes={
                "skill.native.authority_id": authority.authority_id,
                "skill.native.authority_digest": authority.authority_digest,
            },
        )
        plan_span = add_span(
            "skill-native.harness.plan",
            parent=authority_span,
            status=TraceSpanStatus.OK,
            attributes={
                "skill.native.plan_digest": plan_digest,
                "skill.native.manifest_digest": plan.get("manifest_digest"),
                "skill.native.provenance_digest": plan.get("provenance_digest"),
                "skill.native.domain": plan.get("domain"),
                "skill.native.adapter": plan.get("adapter"),
            },
        )
        execute_status = (
            TraceSpanStatus.OK
            if evidence.get("exit_code") == 0
            else TraceSpanStatus.ERROR
        )
        execute_span = add_span(
            "skill-native.harness.execute",
            parent=plan_span,
            status=execute_status,
            attributes={
                "skill.native.evidence_digest": evidence_digest,
                "skill.native.runtime_backend": plan.get("runtime_backend"),
                "skill.native.exit_code": evidence.get("exit_code"),
                "skill.native.captured_evidence": sorted(
                    _captured_evidence(evidence)
                ),
            },
        )
        verify_status = (
            TraceSpanStatus.OK
            if verdict.get("status") == "pass"
            else TraceSpanStatus.ERROR
        )
        verify_span = add_span(
            "skill-native.harness.verify",
            parent=execute_span,
            status=verify_status,
            attributes={
                "skill.native.verdict_digest": verdict_digest,
                "skill.native.verdict_status": verdict.get("status"),
                "skill.native.security_gate": verdict.get("security_gate"),
            },
        )
        add_span(
            "skill-native.run-artifacts.build",
            parent=verify_span,
            status=TraceSpanStatus.OK,
            attributes={
                "skill.native.timing_state": "not-captured",
                "skill.native.trace_kind": "deterministic-logical-envelope",
            },
        )

        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": _require_str(plan, "run_id", "plan"),
            "plan_digest": plan_digest,
            "trace_id": trace_id,
            "timing_state": "not-captured",
            "semantic_convention_targets": sorted(
                {
                    "openinference.span.kind",
                    "otel.trace_id",
                    "skill.native.run_id",
                    "skill.native.plan_digest",
                    "skill.native.evidence_digest",
                    "skill.native.verdict_digest",
                }
            ),
            "spans": spans,
        }
        normalized = _json_payload(payload)
        return LogicalTrace.model_validate(
            {**normalized, "trace_digest": canonical_digest(normalized)}
        )

    @staticmethod
    def _build_scorecard(
        authority: EvaluatorAuthority,
        plan: Mapping[str, Any],
        plan_digest: str,
        evidence: Mapping[str, Any],
        evidence_digest: str,
        verdict: Mapping[str, Any],
        verdict_digest: str,
        replay: ReplayManifest,
    ) -> OutcomeScorecard:
        required = [str(value) for value in plan.get("required_evidence", [])]
        captured = _captured_evidence(evidence)
        captured_required = [value for value in required if value in captured]
        evidence_total = len(required)
        evidence_count = len(captured_required)
        evidence_coverage = (
            1.0 if evidence_total == 0 else evidence_count / evidence_total
        )

        checks = verdict.get("checks", [])
        if not isinstance(checks, list):
            raise RunArtifactError("verdict.checks must be a list")
        verifier_total = len(checks)
        verifier_passed = sum(
            1
            for check in checks
            if isinstance(check, Mapping) and check.get("passed") is True
        )
        verifier_rate = (
            1.0 if verifier_total == 0 else verifier_passed / verifier_total
        )
        status = str(verdict.get("status"))
        security_gate = str(verdict.get("security_gate"))
        failures: list[str] = []
        missing = sorted(set(required) - captured)
        if missing:
            failures.extend(f"missing-evidence:{value}" for value in missing)
        if security_gate == "fail":
            failures.append("security-gate-failed")
        if status != "pass":
            failures.append("verdict-failed")
        if _severe_findings(verdict.get("security_findings", [])):
            failures.append("high-or-critical-security-finding")
        failures = sorted(set(failures))

        rank_eligible = (
            status == "pass"
            and security_gate == "pass"
            and evidence_coverage == 1.0
            and verifier_rate == 1.0
            and not failures
        )
        tier = (
            ScorecardTier.RANKABLE
            if rank_eligible
            else ScorecardTier.REJECTED
            if failures
            else ScorecardTier.PROVISIONAL
        )
        replay_points = {
            ReplayClass.EXACT: 10.0,
            ReplayClass.PARTIAL: 5.0,
            ReplayClass.NONE: 0.0,
        }[replay.replay_class]
        diagnostic_score = round(
            35.0 * evidence_coverage
            + 35.0 * verifier_rate
            + (20.0 if status == "pass" else 0.0)
            + replay_points,
            2,
        )
        if security_gate == "fail":
            diagnostic_score = 0.0

        run_spec = _json_mapping(plan.get("run_spec"), "plan.run_spec")
        skill = _json_mapping(run_spec.get("skill"), "plan.run_spec.skill")
        agent = _json_mapping(run_spec.get("agent"), "plan.run_spec.agent")
        model = _json_mapping(run_spec.get("model"), "plan.run_spec.model")
        runtime = _json_mapping(run_spec.get("runtime"), "plan.run_spec.runtime")
        confounders = {
            "skill": {
                "source_url": skill.get("source_url"),
                "commit_or_digest": skill.get("commit_or_digest"),
            },
            "agent": {
                "harness": agent.get("harness"),
                "version": agent.get("version"),
            },
            "model": {
                "provider": model.get("provider"),
                "model": model.get("model"),
                "quota_class": model.get("quota_class"),
            },
            "runtime": {
                "backend": runtime.get("backend"),
                "version": runtime.get("version"),
                "image_digest": runtime.get("image_digest"),
            },
            "harness": {
                "domain": plan.get("domain"),
                "adapter": plan.get("adapter"),
                "manifest_id": plan.get("manifest_id"),
                "manifest_version": plan.get("manifest_version"),
            },
        }

        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "policy_version": "evidence-first-v1",
            "run_id": _require_str(plan, "run_id", "plan"),
            "authority_digest": authority.authority_digest,
            "plan_digest": plan_digest,
            "evidence_digest": evidence_digest,
            "verdict_digest": verdict_digest,
            "outcome_status": status,
            "security_gate": security_gate,
            "mandatory_evidence_total": evidence_total,
            "mandatory_evidence_captured": evidence_count,
            "mandatory_evidence_coverage": evidence_coverage,
            "verifier_total": verifier_total,
            "verifier_passed": verifier_passed,
            "verifier_pass_rate": verifier_rate,
            "replay_class": replay.replay_class,
            "rank_eligible": rank_eligible,
            "tier": tier,
            "diagnostic_score": diagnostic_score,
            "non_compensable_failures": failures,
            "confounders": confounders,
        }
        normalized = _json_payload(payload)
        return OutcomeScorecard.model_validate(
            {**normalized, "scorecard_digest": canonical_digest(normalized)}
        )


def _severe_findings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        severity = str(item.get("severity", "")).strip().lower()
        if severity in {"high", "critical"}:
            result.append({str(key): child for key, child in item.items()})
    return result


def _find_snapshot_digest(metadata: Mapping[str, Any]) -> str | None:
    wanted = {"snapshot_digest", "snapshot_sha256", "snapshotdigest"}
    stack: list[Any] = [metadata]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            for key, child in value.items():
                normalized = str(key).replace("-", "_").lower()
                if normalized in wanted and isinstance(child, str):
                    digest = child.removeprefix("sha256:")
                    if _HEX_64.fullmatch(digest):
                        return digest
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)
    return None
