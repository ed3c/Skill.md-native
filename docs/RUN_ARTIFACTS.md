# Run Artifact Bundle v0.1

## Status

This increment adds a cross-domain evidence derivation layer on top of the existing:

```text
HarnessPlan
+ EvidenceBundle
+ HarnessVerdict
```

The output is a digest-addressed `RunArtifactBundle` containing:

```text
EvaluatorAuthority
+ EvidenceGraph
+ ReplayManifest
+ LogicalTrace
+ OutcomeScorecard
```

The implementation is deterministic and covered by a standalone local test suite. It does not claim live OpenTelemetry export, cryptographic attestation, exact replay without a captured snapshot, or GitHub Actions verification while repository jobs are blocked by the account billing/spending-limit state.

## Problem being solved

A Skill package is an untrusted supply-chain artifact. A package-supplied `harness.yaml`, test command, assertion, or natural-language success statement cannot become authoritative merely because it exists.

The prior Harness Kernel bound a manifest to a plan and a verdict. This increment makes the authority behind that evaluator explicit:

```text
Trusted operator / evaluator repository
            │
            ▼
EvaluatorAuthority sidecar
            │
            ├── immutable evaluator commit or digest
            ├── evaluator artifact digest
            ├── authorized manifest digest
            └── trust basis
            │
            ▼
HarnessPlan → EvidenceBundle → HarnessVerdict
            │
            ▼
RunArtifactBundle
```

The authority sidecar must be supplied outside the untrusted Skill package. The builder validates it; the builder does not discover or infer trust from popularity, repository ownership, or package claims.

## Trust boundaries

### Trusted

- operator-supplied `EvaluatorAuthority` sidecar;
- the Run Artifact builder and content-addressed store;
- the existing Harness Kernel digest chain;
- runtime collector attestations under `runtime_metadata.evidence_contract`;
- verifier and security-gate output preserved in `HarnessVerdict`.

### Untrusted

- Skill package content;
- package-supplied harness claims;
- model, agent, tool, browser, device, network, and document output;
- empty `EvidenceBundle` defaults without collector attestation;
- a receipt digest presented as if it were a cryptographic signature.

## Evaluator authority

Example shape:

```json
{
  "schema_version": "1.0",
  "authority_id": "skill-native.fixture-evaluator",
  "kind": "repository",
  "trust_basis": "repository-pinned",
  "source_url": "https://github.com/ed3c/Skill.md-native",
  "commit_or_digest": "2222222222222222222222222222222222222222",
  "manifest_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "evaluator_digest": "3333333333333333333333333333333333333333333333333333333333333333",
  "authority_digest": "..."
}
```

Accepted immutable reference forms are deliberately narrow:

```text
40-character lowercase Git commit SHA
64-character lowercase SHA-256
sha256:<64 lowercase hex>
git:<40 lowercase hex>
```

Mutable names such as `main`, `master`, `HEAD`, `latest`, `*`, and `unknown` fail closed.

`manifest_digest` must exactly match the digest compiled into the `HarnessPlan`. This makes evaluator ownership explicit for commands such as Coding Harness `version_command` and `test_commands`.

The authority digest detects mutation. It is not a signature. A later attestation layer should sign the authority, plan, evidence, and verdict with a key unavailable to the evaluated sandbox.

## Digest and continuity validation

Before deriving any artifact, the builder validates:

```text
plan.plan_digest
verdict.verdict_digest
authority.authority_digest
```

It then checks continuity across:

```text
run_id
manifest_digest
provenance_digest
plan_digest
evidence_digest
runtime_backend
```

Additional checks include:

- immutable Skill reference;
- internal runtime-backend consistency;
- evidence run/provenance/runtime continuity;
- verdict failed-check list and status consistency;
- failed security gate presence in failed checks;
- High/Critical finding cannot coexist with a passing security gate.

A stale or modified plan/verdict is rejected before graph or score generation.

## Evidence Graph

The graph contains digest-addressed nodes for:

```text
evaluator authority
Harness plan
Skill provenance
runtime
agent
model
EvidenceBundle
individual evidence objects
verification checks
security findings
HarnessVerdict
```

Representative relationships:

```text
EvaluatorAuthority ──authorizes──────────▶ HarnessPlan
SkillProvenance ─────input_to────────────▶ HarnessPlan
Runtime / Agent / Model ─configures──────▶ HarnessPlan
HarnessPlan ─────────produces────────────▶ EvidenceBundle
EvidenceObject ──────contained_in────────▶ EvidenceBundle
EvidenceBundle ──────evaluated_by────────▶ HarnessVerdict
VerificationCheck ───supports────────────▶ HarnessVerdict
SecurityFinding ─────constrains──────────▶ HarnessVerdict
```

Every node and edge has a deterministic ID. Graph validation rejects duplicate node/edge IDs and dangling references.

Raw stdout and stderr are not copied into graph attributes. Their graph nodes contain only digest, byte count, and empty-state metadata. Other evidence objects are represented by payload digest and channel/index metadata, limiting accidental duplication of sensitive payloads.

## Mandatory evidence coverage

Scorecard evidence coverage is calculated only from trusted collector attestation:

```json
{
  "runtime_metadata": {
    "evidence_contract": {
      "schema_version": "1.0",
      "captured": ["exit_code", "stderr", "runtime_metadata"]
    }
  }
}
```

A default empty field is not evidence. For example:

```json
{"stderr": ""}
```

counts only when `stderr` is present in the trusted `captured` list.

This rule applies across Coding, Browser, Android, Desktop, SRE, Documents, Voice, Robotics, and future adapters.

## Replay Manifest

Replay classification is intentionally conservative.

### Exact

Requires all of:

```text
runtime_capabilities.snapshot_restore = true
captured immutable snapshot digest
runtime image pinned to SHA-256
immutable Skill provenance
evaluator authority pinned to immutable commit/digest
```

### Partial

Used when the immutable task/evaluator configuration is available but a snapshot or exact runtime image is missing.

### None

Used when a required runtime reference remains mutable. Mutable evaluator and Skill references are rejected earlier rather than classified as replayable.

A runtime claiming snapshot support without a captured snapshot digest cannot receive `exact` classification.

## Logical trace envelope

The bundle includes a deterministic logical trace with spans for:

```text
authority.resolve
harness.plan
harness.execute
harness.verify
run-artifacts.build
```

Trace and span IDs are derived from content digests. The schema contains no start time, end time, timestamp, or duration fields.

```json
{"timing_state": "not-captured"}
```

This is an export-ready semantic envelope, not evidence that OpenTelemetry or OpenInference collectors were active. A later exporter can add real timing and transport receipts without changing the logical identity chain.

## Outcome Scorecard

Policy version:

```text
evidence-first-v1
```

The scorecard exposes:

```text
mandatory evidence coverage
verifier pass rate
verdict outcome
security gate
replay class
rank eligibility
explicit Agent / Model / Runtime / Skill / Harness confounders
diagnostic score
```

Diagnostic score:

```text
35 × mandatory evidence coverage
+ 35 × verifier pass rate
+ 20 when verdict passes
+ 10 exact replay / 5 partial replay / 0 no replay
```

This score is diagnostic, not proof of correctness.

Non-compensable rules:

```text
High/Critical finding or failed security gate → diagnostic_score = 0
failed verdict                              → rank_eligible = false
missing mandatory evidence                 → rank_eligible = false
any failed verifier                        → rank_eligible = false
```

A high quality score can never compensate for a security failure or missing mandatory evidence.

## CLI

### Create an authority sidecar

```bash
skill-native-run-artifacts create-authority \
  --authority-id skill-native.operator-evaluator \
  --kind repository \
  --trust-basis repository-pinned \
  --source-url https://github.com/ed3c/Skill.md-native \
  --commit-or-digest <40-char-commit-sha> \
  --manifest-digest <64-char-manifest-digest> \
  --evaluator-digest <64-char-evaluator-artifact-digest> \
  --output /tmp/authority.json
```

### Build and persist run artifacts

```bash
skill-native-run-artifacts build \
  --authority /tmp/authority.json \
  --plan /tmp/harness-plan.json \
  --evidence /tmp/evidence.json \
  --verdict /tmp/harness-verdict.json \
  --output /tmp/run-artifacts
```

Output layout:

```text
/tmp/run-artifacts/<bundle-digest>/
├── authority.json
├── evidence-graph.json
├── logical-trace.json
├── outcome-scorecard.json
├── replay-manifest.json
└── run-artifact-bundle.json
```

The build command exits with status 2 when the bundle is valid but not rank eligible. Artifacts are still persisted for diagnosis.

### Export JSON Schemas

```bash
skill-native-run-artifacts export-schemas /tmp/run-artifact-schemas
```

## Deterministic verification

```bash
PYTHONPATH=src python -m unittest tests.test_run_artifacts -v
```

The suite covers:

- deterministic digests;
- graph referential integrity;
- mutable authority rejection;
- authority/manifest mismatch;
- plan and verdict tampering;
- missing collector attestation;
- non-compensable security failure;
- severe finding hidden behind a passing gate;
- exact replay requirements;
- logical trace timing boundaries;
- nested artifact tampering;
- content-addressed persistence;
- schema export.

## Verification vocabulary

- **implemented**: code, schemas, examples, and deterministic local tests exist.
- **integration-verified**: persisted artifacts were produced from an external adapter or service.
- **runtime-verified**: the pinned artifact ran in the declared isolated runtime and all required assertions passed.
- **cryptographically attested**: a trusted signing identity covered the relevant digests.

This increment is implemented and locally deterministic-tested. It is not cryptographically attested and does not claim a GitHub Actions pass while Actions jobs cannot start because of the account billing/spending-limit block.

## Follow-on work

1. Sign evaluator authority and Run Artifact Bundles with short-lived workload identity.
2. Publish append-only transparency-log entries for authority and bundle digests.
3. Export logical spans through OpenTelemetry/OpenInference with real timing receipts.
4. Attach mutation-tested verifier-strength evidence.
5. Add Browser and Android domain artifacts under the same graph, replay, trace, and scorecard contracts.
6. Add Temporal/Dagger orchestration without changing evidence semantics.
