# Run Artifact Bundle v0.1

## Status

This layer derives cross-domain, digest-addressed artifacts from:

```text
EvaluatorAuthority
+ HarnessPlan
+ EvidenceBundle
+ HarnessVerdict
        │
        ▼
RunArtifactBundle
├── EvidenceGraph
├── ReplayManifest
├── LogicalTrace
└── OutcomeScorecard
```

The implementation is deterministic and verified by the repository unit and integration workflows. It does not claim cryptographic attestation, live OpenTelemetry transport, or exact replay without a captured runtime snapshot.

## Problem

A Skill package is an untrusted executable supply-chain artifact. A package-supplied `harness.yaml`, test command, assertion, or natural-language success statement does not become authoritative merely because it exists.

The evaluator authority must be supplied outside the Skill package and pinned to immutable content:

```text
Trusted operator / evaluator repository
            │
            ▼
EvaluatorAuthority
├── immutable evaluator reference
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

The builder validates authority and continuity. It does not infer trust from popularity, repository ownership, stars, downloads, or model claims.

## Trust boundaries

### Trusted

- operator-supplied `EvaluatorAuthority`;
- Harness Kernel and Run Artifact builder code;
- persisted plan, evidence, and verdict inputs whose digests validate;
- runtime collector attestations under `runtime_metadata.evidence_contract`;
- verifier and security-gate results preserved in `HarnessVerdict`.

### Untrusted

- Skill package content;
- package-supplied evaluator claims;
- model, agent, tool, browser, device, network, and document output;
- empty `EvidenceBundle` defaults without collector attestation;
- a content digest presented as if it were a signature.

## Evaluator authority

Example:

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

Accepted immutable references are deliberately narrow:

```text
40-character lowercase Git commit SHA
64-character lowercase SHA-256
sha256:<64 lowercase hex>
git:<40 lowercase hex>
```

Mutable values such as `main`, `master`, `HEAD`, `latest`, `*`, and `unknown` fail closed. `manifest_digest` must exactly match the manifest compiled into the `HarnessPlan`.

The authority digest detects mutation. It is not a cryptographic signature. A later attestation layer must sign the authority and bundle with an identity unavailable to the evaluated sandbox.

## Digest and continuity validation

Before deriving artifacts, the builder validates:

```text
authority.authority_digest
plan.plan_digest
verdict.verdict_digest
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

- immutable Skill provenance;
- internal runtime-backend consistency;
- evidence run/provenance/runtime continuity;
- verdict failed-check and status consistency;
- failed security gate presence in failed checks;
- High/Critical findings cannot coexist with a passing security gate.

A stale or modified plan or verdict is rejected before graph or score generation.

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

Representative edges:

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

Graph IDs are deterministic. Validation rejects duplicate node or edge IDs and dangling structural references.

Source evidence linking is also fail-closed:

- duplicate `source_evidence_id` values are rejected because they make a claim ambiguous;
- verifier `evidence_ids` must resolve to exactly one evidence object;
- passing verdicts cannot contain findings that reference unknown evidence;
- failed security runs may retain an explicit `unresolved_evidence_reference` node so diagnostic artifacts are not lost, but they remain non-rank-eligible.

Raw stdout and stderr are not copied into graph attributes. Their nodes contain only SHA-256, byte count, and empty-state metadata. Other evidence objects are represented by payload digest and channel/index metadata.

## Mandatory evidence coverage

Coverage is calculated only from trusted collector attestation:

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

A default empty field is not evidence. For example, `{"stderr": ""}` counts only when `stderr` appears in the trusted `captured` list.

This rule applies to Coding, Browser, Android, Desktop, SRE, Documents, Voice, Robotics, and future adapters.

## Replay Manifest

Replay classification is conservative.

### Exact

Requires all of:

```text
runtime_capabilities.snapshot_restore = true
captured immutable snapshot digest
runtime image pinned to SHA-256
immutable Skill provenance
immutable evaluator authority
```

### Partial

Used when immutable task/evaluator configuration exists but snapshot or exact runtime image evidence is incomplete.

### None

Used when a required runtime reference remains mutable. Mutable evaluator and Skill references are rejected earlier.

Snapshot capability alone is never sufficient for `exact`.

## Logical trace envelope

The bundle includes deterministic logical spans for:

```text
authority.resolve
harness.plan
harness.execute
harness.verify
run-artifacts.build
```

Trace and span IDs derive from content digests. Timing is explicit:

```json
{"timing_state": "not-captured"}
```

No start time, end time, timestamp, or duration is fabricated. A later OpenTelemetry/OpenInference exporter may add real timing receipts without changing logical trace identity.

## Outcome Scorecard

Policy:

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
Skill / Agent / Model / Runtime / Harness confounders
diagnostic score
```

Diagnostic score:

```text
35 × mandatory evidence coverage
+ 35 × verifier pass rate
+ 20 when verdict passes
+ 10 exact replay / 5 partial replay / 0 no replay
```

Non-compensable rules:

```text
High/Critical finding or failed security gate → diagnostic_score = 0
failed verdict                              → rank_eligible = false
missing mandatory evidence                 → rank_eligible = false
any failed verifier                        → rank_eligible = false
```

The score is diagnostic, not proof of correctness.

## CLI

### Create authority

```bash
skill-native-run-artifacts create-authority \
  --authority-id skill-native.operator-evaluator \
  --kind repository \
  --trust-basis repository-pinned \
  --source-url https://github.com/ed3c/Skill.md-native \
  --commit-or-digest <immutable-ref> \
  --manifest-digest <64-char-manifest-digest> \
  --evaluator-digest <64-char-evaluator-digest> \
  --output /tmp/authority.json
```

### Build and persist

```bash
skill-native-run-artifacts build \
  --authority /tmp/authority.json \
  --plan /tmp/harness-plan.json \
  --evidence /tmp/evidence.json \
  --verdict /tmp/harness-verdict.json \
  --output /tmp/run-artifacts
```

Output:

```text
/tmp/run-artifacts/<bundle-digest>/
├── authority.json
├── evidence-graph.json
├── logical-trace.json
├── outcome-scorecard.json
├── replay-manifest.json
└── run-artifact-bundle.json
```

A valid but non-rank-eligible build persists diagnostics and exits with status 2.

### Export schemas

```bash
skill-native-run-artifacts export-schemas /tmp/run-artifact-schemas
```

## Verification

Repository CI executes:

```bash
python -m unittest discover -s tests -v
skill-native-run-artifacts export-schemas /tmp/run-artifact-schemas
# committed/generated schema diff
# deterministic fixture build and artifact-count checks
```

The focused suites cover:

- deterministic digests and JSON round-trip;
- graph referential integrity;
- duplicate and unknown source evidence references;
- unresolved-reference diagnostics for failed security runs;
- mutable authority rejection and authority/manifest mismatch;
- stale plan and verdict rejection;
- missing collector attestation;
- non-compensable security failure;
- exact replay requirements;
- no fabricated timing;
- nested artifact tampering;
- content-addressed persistence and schema export.

For PR #22 head `4a506b2daa9a072d40e661ddcff2ae33e5c410f8`:

```text
unit workflow #95        success
integration workflow #22 success
```

## Verification vocabulary

- **implemented**: code, schemas, examples, and deterministic tests exist;
- **integration-verified**: an external adapter or service produced persisted evidence;
- **runtime-verified**: the pinned artifact ran in the declared isolated runtime and all required assertions passed;
- **cryptographically attested**: a trusted signing identity covered the relevant digests.

This increment is implemented and CI-verified. It is not yet cryptographically attested and does not claim live OpenTelemetry/OpenInference export.

## Follow-on work

1. Sign evaluator authority and Run Artifact Bundles with short-lived workload identity.
2. Publish authority and bundle digests to an append-only transparency log.
3. Export logical spans through OpenTelemetry/OpenInference with real timing receipts.
4. Attach mutation-tested verifier-strength evidence.
5. Add Browser and Android adapters under the same graph, replay, trace, and scorecard contracts.
6. Add Temporal/Dagger orchestration without changing evidence semantics.
