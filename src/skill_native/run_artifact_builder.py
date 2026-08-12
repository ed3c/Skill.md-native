from __future__ import annotations

from typing import Any, Mapping

from .run_artifact_common import (
    EvaluatorAuthority,
    RunArtifactError,
    _is_immutable_reference,
    _json_mapping,
    _json_payload,
    _require_str,
    _validate_content_digest,
    canonical_digest,
)
from .run_artifact_bundle import RunArtifactBundle
from .run_artifact_derived import _DerivedBuilderMixin, _severe_findings
from .run_artifact_graph import _GraphBuilderMixin


class RunArtifactBuilder(_GraphBuilderMixin, _DerivedBuilderMixin):
    def build(
        self,
        authority: EvaluatorAuthority | Mapping[str, Any],
        plan: Mapping[str, Any],
        evidence: Mapping[str, Any],
        verdict: Mapping[str, Any],
    ) -> RunArtifactBundle:
        authority_model = (
            authority
            if isinstance(authority, EvaluatorAuthority)
            else EvaluatorAuthority.model_validate(authority)
        )
        plan_value = _json_mapping(plan, "plan")
        evidence_value = _json_mapping(evidence, "evidence")
        verdict_value = _json_mapping(verdict, "verdict")

        plan_digest = _validate_content_digest(plan_value, "plan_digest", "plan")
        verdict_digest = _validate_content_digest(
            verdict_value, "verdict_digest", "verdict"
        )
        evidence_digest = canonical_digest(evidence_value)
        continuity = self._validate_continuity(
            authority_model,
            plan_value,
            plan_digest,
            evidence_value,
            evidence_digest,
            verdict_value,
        )

        graph = self._build_graph(
            authority_model,
            plan_value,
            plan_digest,
            evidence_value,
            evidence_digest,
            verdict_value,
            verdict_digest,
        )
        replay = self._build_replay(authority_model, plan_value, evidence_value)
        trace = self._build_trace(
            authority_model,
            plan_value,
            plan_digest,
            evidence_value,
            evidence_digest,
            verdict_value,
            verdict_digest,
        )
        scorecard = self._build_scorecard(
            authority_model,
            plan_value,
            plan_digest,
            evidence_value,
            evidence_digest,
            verdict_value,
            verdict_digest,
            replay,
        )
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": continuity["run_id"],
            "authority": authority_model,
            "evidence_graph": graph,
            "replay_manifest": replay,
            "logical_trace": trace,
            "scorecard": scorecard,
            "plan_digest": plan_digest,
            "evidence_digest": evidence_digest,
            "verdict_digest": verdict_digest,
        }
        normalized = _json_payload(payload)
        return RunArtifactBundle.model_validate(
            {**normalized, "bundle_digest": canonical_digest(normalized)}
        )

    @staticmethod
    def _validate_continuity(
        authority: EvaluatorAuthority,
        plan: Mapping[str, Any],
        plan_digest: str,
        evidence: Mapping[str, Any],
        evidence_digest: str,
        verdict: Mapping[str, Any],
    ) -> dict[str, str]:
        run_id = _require_str(plan, "run_id", "plan")
        manifest_digest = _require_str(plan, "manifest_digest", "plan")
        provenance_digest = _require_str(plan, "provenance_digest", "plan")
        runtime_backend = _require_str(plan, "runtime_backend", "plan")
        if authority.manifest_digest != manifest_digest:
            raise RunArtifactError(
                "evaluator authority manifest digest does not match the plan"
            )

        run_spec = _json_mapping(plan.get("run_spec"), "plan.run_spec")
        skill = _json_mapping(run_spec.get("skill"), "plan.run_spec.skill")
        skill_ref = _require_str(skill, "commit_or_digest", "plan.run_spec.skill")
        if not _is_immutable_reference(skill_ref):
            raise RunArtifactError("plan skill reference is mutable")
        runtime = _json_mapping(run_spec.get("runtime"), "plan.run_spec.runtime")
        if _require_str(runtime, "backend", "plan.run_spec.runtime") != runtime_backend:
            raise RunArtifactError("plan runtime backend is internally inconsistent")

        if _require_str(evidence, "run_id", "evidence") != run_id:
            raise RunArtifactError("evidence run id does not match plan")
        if evidence.get("provenance_digest") != provenance_digest:
            raise RunArtifactError("evidence provenance digest does not match plan")
        metadata = _json_mapping(
            evidence.get("runtime_metadata", {}), "evidence.runtime_metadata"
        )
        if metadata.get("runtime_backend") != runtime_backend:
            raise RunArtifactError("evidence runtime backend does not match plan")

        expected = {
            "run_id": run_id,
            "manifest_digest": manifest_digest,
            "provenance_digest": provenance_digest,
            "plan_digest": plan_digest,
            "evidence_digest": evidence_digest,
            "runtime_backend": runtime_backend,
        }
        for key, value in expected.items():
            if verdict.get(key) != value:
                raise RunArtifactError(f"verdict {key} does not preserve continuity")

        checks = verdict.get("checks")
        if not isinstance(checks, list):
            raise RunArtifactError("verdict.checks must be a list")
        failed = [
            str(check.get("id"))
            for check in checks
            if isinstance(check, Mapping) and check.get("passed") is not True
        ]
        if verdict.get("failed_check_ids") != failed:
            raise RunArtifactError("verdict failed_check_ids do not match checks")
        expected_status = "fail" if failed else "pass"
        if verdict.get("status") != expected_status:
            raise RunArtifactError("verdict status does not match failed checks")
        security_gate = verdict.get("security_gate")
        if security_gate not in {"pass", "fail"}:
            raise RunArtifactError("verdict security_gate is invalid")
        if security_gate == "fail" and "security-gate" not in failed:
            raise RunArtifactError("failed security gate is missing from failed checks")

        severe = _severe_findings(verdict.get("security_findings", []))
        if severe and security_gate != "fail":
            raise RunArtifactError(
                "High/Critical security findings cannot be compensated by a passing gate"
            )
        return expected
