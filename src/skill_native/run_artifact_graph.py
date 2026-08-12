from __future__ import annotations

from typing import Any, Iterable, Mapping

from .run_artifact_common import (
    EvaluatorAuthority,
    EvidenceGraph,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    RunArtifactError,
    _digest_ref,
    _json_mapping,
    _json_payload,
    _require_str,
    canonical_digest,
)


class _GraphBuilderMixin:
    def _build_graph(
        self,
        authority: EvaluatorAuthority,
        plan: Mapping[str, Any],
        plan_digest: str,
        evidence: Mapping[str, Any],
        evidence_digest: str,
        verdict: Mapping[str, Any],
        verdict_digest: str,
    ) -> EvidenceGraph:
        nodes: list[EvidenceGraphNode] = []
        edges: list[EvidenceGraphEdge] = []
        source_evidence_ids: dict[str, str] = {}

        def add_node(kind: str, payload_digest: str, attributes: dict[str, Any]) -> str:
            normalized_attributes = _json_payload(attributes)
            node_id = _digest_ref(
                canonical_digest(
                    {
                        "kind": kind,
                        "payload_digest": payload_digest,
                        "attributes": normalized_attributes,
                    }
                )
            )
            nodes.append(
                EvidenceGraphNode(
                    id=node_id,
                    kind=kind,
                    payload_digest=payload_digest,
                    attributes=normalized_attributes,
                )
            )
            return node_id

        def add_edge(
            source: str,
            target: str,
            relation: str,
            attributes: dict[str, Any] | None = None,
        ) -> str:
            normalized_attributes = _json_payload(attributes or {})
            edge_id = _digest_ref(
                canonical_digest(
                    {
                        "source": source,
                        "target": target,
                        "relation": relation,
                        "attributes": normalized_attributes,
                    }
                )
            )
            edges.append(
                EvidenceGraphEdge(
                    id=edge_id,
                    source=source,
                    target=target,
                    relation=relation,
                    attributes=normalized_attributes,
                )
            )
            return edge_id

        def register_source_evidence_id(raw_id: str, object_node: str) -> None:
            existing = source_evidence_ids.get(raw_id)
            if existing is not None:
                raise RunArtifactError(
                    f"duplicate source evidence id creates an ambiguous graph: {raw_id}"
                )
            source_evidence_ids[raw_id] = object_node

        def require_source_evidence_id(raw_id: Any, *, context: str) -> str:
            if not isinstance(raw_id, str) or not raw_id:
                raise RunArtifactError(f"{context} must contain a non-empty evidence id")
            target = source_evidence_ids.get(raw_id)
            if target is None:
                raise RunArtifactError(
                    f"{context} references unknown source evidence id: {raw_id}"
                )
            return target

        run_spec = _json_mapping(plan.get("run_spec"), "plan.run_spec")
        skill = _json_mapping(run_spec.get("skill"), "plan.run_spec.skill")
        agent = _json_mapping(run_spec.get("agent"), "plan.run_spec.agent")
        model = _json_mapping(run_spec.get("model"), "plan.run_spec.model")
        runtime = _json_mapping(run_spec.get("runtime"), "plan.run_spec.runtime")

        authority_node = add_node(
            "evaluator_authority",
            authority.authority_digest,
            {
                "authority_id": authority.authority_id,
                "kind": authority.kind.value,
                "trust_basis": authority.trust_basis.value,
                "source_url": authority.source_url,
                "commit_or_digest": authority.commit_or_digest,
            },
        )
        plan_node = add_node(
            "harness_plan",
            plan_digest,
            {
                "manifest_id": plan.get("manifest_id"),
                "manifest_version": plan.get("manifest_version"),
                "domain": plan.get("domain"),
                "adapter": plan.get("adapter"),
            },
        )
        skill_node = add_node(
            "skill_provenance",
            _require_str(plan, "provenance_digest", "plan"),
            {
                "source_url": skill.get("source_url"),
                "commit_or_digest": skill.get("commit_or_digest"),
                "entrypoint": skill.get("entrypoint"),
            },
        )
        runtime_node = add_node(
            "runtime",
            canonical_digest(runtime),
            {
                "backend": runtime.get("backend"),
                "version": runtime.get("version"),
                "image_digest": runtime.get("image_digest"),
            },
        )
        agent_node = add_node(
            "agent",
            canonical_digest(agent),
            {"harness": agent.get("harness"), "version": agent.get("version")},
        )
        model_node = add_node(
            "model",
            canonical_digest(model),
            {
                "provider": model.get("provider"),
                "model": model.get("model"),
                "quota_class": model.get("quota_class"),
            },
        )
        evidence_node = add_node(
            "evidence_bundle",
            evidence_digest,
            {
                "captured": sorted(_captured_evidence(evidence)),
                "channel_count": _evidence_channel_count(evidence),
            },
        )
        verdict_node = add_node(
            "harness_verdict",
            verdict_digest,
            {
                "status": verdict.get("status"),
                "security_gate": verdict.get("security_gate"),
                "failed_check_ids": verdict.get("failed_check_ids", []),
            },
        )

        add_edge(authority_node, plan_node, "authorizes")
        add_edge(skill_node, plan_node, "input_to")
        add_edge(runtime_node, plan_node, "configures")
        add_edge(agent_node, plan_node, "configures")
        add_edge(model_node, plan_node, "configures")
        add_edge(plan_node, evidence_node, "produces")
        add_edge(evidence_node, verdict_node, "evaluated_by")
        add_edge(authority_node, verdict_node, "authorizes_evaluation")

        for channel, index, value in _iter_evidence_objects(evidence):
            digest = canonical_digest(value)
            attributes: dict[str, Any] = {"channel": channel}
            if index is not None:
                attributes["index"] = index
            if isinstance(value, Mapping):
                raw_evidence_id = value.get("evidence_id")
                if isinstance(raw_evidence_id, str) and raw_evidence_id:
                    attributes["source_evidence_id"] = raw_evidence_id
            object_node = add_node("evidence_object", digest, attributes)
            add_edge(object_node, evidence_node, "contained_in", attributes)
            raw_id = attributes.get("source_evidence_id")
            if isinstance(raw_id, str):
                register_source_evidence_id(raw_id, object_node)

        checks = verdict.get("checks", [])
        for index, raw_check in enumerate(checks):
            check = _json_mapping(raw_check, f"verdict.checks[{index}]")
            check_node = add_node(
                "verification_check",
                canonical_digest(check),
                {
                    "check_id": check.get("id"),
                    "kind": check.get("kind"),
                    "passed": check.get("passed") is True,
                },
            )
            add_edge(check_node, verdict_node, "supports")
            add_edge(authority_node, check_node, "authorizes")
            evidence_ids = check.get("evidence_ids", [])
            if not isinstance(evidence_ids, list):
                raise RunArtifactError(
                    f"verdict.checks[{index}].evidence_ids must be a list"
                )
            normalized_ids = [str(value) for value in evidence_ids]
            if len(normalized_ids) != len(set(normalized_ids)):
                raise RunArtifactError(
                    f"verdict.checks[{index}].evidence_ids contains duplicates"
                )
            for evidence_id in evidence_ids:
                target = require_source_evidence_id(
                    evidence_id,
                    context=f"verdict.checks[{index}].evidence_ids",
                )
                add_edge(check_node, target, "references")

        findings = verdict.get("security_findings", [])
        if not isinstance(findings, list):
            raise RunArtifactError("verdict.security_findings must be a list")
        for index, raw_finding in enumerate(findings):
            finding = _json_mapping(
                raw_finding, f"verdict.security_findings[{index}]"
            )
            finding_node = add_node(
                "security_finding",
                canonical_digest(finding),
                {
                    "severity": finding.get("severity"),
                    "rule": finding.get("rule"),
                },
            )
            add_edge(finding_node, verdict_node, "constrains")
            source_id = finding.get("evidence_id")
            if source_id in (None, ""):
                continue
            target = source_evidence_ids.get(str(source_id))
            if target is None:
                if verdict.get("status") == "pass" or verdict.get("security_gate") == "pass":
                    raise RunArtifactError(
                        "passing verdict contains a security finding with an unknown "
                        f"source evidence id: {source_id}"
                    )
                unresolved_node = add_node(
                    "unresolved_evidence_reference",
                    canonical_digest({"source_evidence_id": str(source_id)}),
                    {
                        "source_evidence_id": str(source_id),
                        "resolved": False,
                    },
                )
                add_edge(finding_node, unresolved_node, "references_missing")
            else:
                add_edge(finding_node, target, "derived_from")

        nodes = sorted(nodes, key=lambda node: node.id)
        edges = sorted(edges, key=lambda edge: edge.id)
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": _require_str(plan, "run_id", "plan"),
            "nodes": nodes,
            "edges": edges,
        }
        normalized = _json_payload(payload)
        return EvidenceGraph.model_validate(
            {**normalized, "graph_digest": canonical_digest(normalized)}
        )


def _captured_evidence(evidence: Mapping[str, Any]) -> frozenset[str]:
    metadata = evidence.get("runtime_metadata", {})
    if not isinstance(metadata, Mapping):
        return frozenset()
    contract = metadata.get("evidence_contract", {})
    if not isinstance(contract, Mapping):
        return frozenset()
    values = contract.get("captured", [])
    if not isinstance(values, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(str(value) for value in values)


def _evidence_channel_count(evidence: Mapping[str, Any]) -> int:
    return len(_captured_evidence(evidence))


def _iter_evidence_objects(
    evidence: Mapping[str, Any],
) -> Iterable[tuple[str, int | None, Any]]:
    list_channels = (
        "commands",
        "processes",
        "network",
        "inference",
        "findings",
        "ocsf_events",
        "agent_events",
        "test_results",
    )
    singular_channels = (
        "exit_code",
        "stdout",
        "stderr",
        "filesystem_before",
        "filesystem_after",
        "assertions",
        "runtime_metadata",
        "policy",
        "coding_receipt",
        "workspace_diff",
    )
    captured = _captured_evidence(evidence)
    for channel in list_channels:
        value = evidence.get(channel, [])
        if isinstance(value, list):
            for index, item in enumerate(value):
                yield channel, index, item
        elif channel in captured:
            yield channel, None, value
    for channel in singular_channels:
        if channel not in evidence and channel not in captured:
            continue
        value = evidence.get(channel)
        if channel in captured or value not in (None, "", [], {}):
            if channel in {"stdout", "stderr"} and isinstance(value, str):
                value = {
                    "sha256": _text_digest(value),
                    "bytes": len(value.encode("utf-8")),
                    "empty": value == "",
                }
            yield channel, None, value


def _text_digest(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
