from __future__ import annotations

from dataclasses import replace

from .models import AgentRef, ModelRef, RunSpec, RuntimeRef, Scenario, SkillRef
from .provenance import ProvenanceRecord, provenance_digest


def run_spec_from_provenance(
    provenance: ProvenanceRecord,
    *,
    source_url: str,
    run_id: str,
    agent: AgentRef,
    model: ModelRef,
    runtime: RuntimeRef,
    scenario: Scenario,
) -> RunSpec:
    digest = provenance_digest(provenance)
    immutable_ref = provenance.attestations[0].immutable_ref
    return RunSpec(
        run_id=run_id,
        skill=SkillRef(
            source_url=source_url,
            commit_or_digest=immutable_ref or provenance.content_sha256,
            entrypoint=provenance.entrypoint,
            provenance_digest=digest,
        ),
        agent=agent,
        model=model,
        runtime=runtime,
        scenario=scenario,
    )
