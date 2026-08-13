# Skill.md-native

Runtime-verified evidence, security, compatibility, and outcome ranking for Agent Skills across registries and execution domains.

> **Coding/AI Agents:** read [`AGENTS.md`](./AGENTS.md), this README, [`docs/INTEGRATION_STATE.md`](./docs/INTEGRATION_STATE.md), and the relevant domain/trust document before changing code, Issues, CI, runtime adapters, evaluation logic, schemas, or documentation. Branch/PR work must also follow [`docs/STACKED_DELIVERY.md`](./docs/STACKED_DELIVERY.md).

## Current integration snapshot

The exact evidence-state ledger is maintained in [`docs/INTEGRATION_STATE.md`](./docs/INTEGRATION_STATE.md). At the 2026-08-12 snapshot:

| Area | State | Trace |
|---|---|---|
| Immutable ingestion, provenance, broker, runtime contracts, adversarial evaluation, compatibility/ranking MVP | merged | PR #7 |
| Cross-domain Harness Kernel | merged | PR #17 |
| Coding Agent Harness | merged | PR #19 |
| Evaluator-authorized Run Artifact Bundle | merged | PR #22 |
| Coding stdin backpressure hardening | merged | PR #26 |
| DSSE Ed25519 attestation and local transparency publication | merged | PR #24; `main@032a933d15f3770b93be24aa9abfed98b9a2a898` at snapshot |
| Playwright Browser Harness | open Draft, not merged | Issue #27, PR #29, `agent/27-browser-playwright-harness@c58cbef0ac5f21356ccf454cd1bf1c6396e0049d` |
| Android ADB Harness | planned | Issue #28; no implementation PR at snapshot |
| OpenShell/Cloudflare live runtime and detector-quality gates | externally pending | Issues #1, #2, #3, #5 |

PR #29 was open, Draft, and mergeable at the snapshot. Its `unit`, `integration`, and `schema-sync-pr` workflows reported `action_required`; this is not green hosted CI and is not a runtime-verification claim.

## Mission

Every third-party `SKILL.md` package is treated as an untrusted executable supply-chain artifact. The project pins its origin, executes it through controlled runtimes, captures content-addressed evidence, evaluates security and task outcomes, and ranks results without silently mixing Skill, Agent, Runtime, Model, policy, scenario, or evaluator confounders.

```text
Registry / Repository / Plugin source
  → immutable Skill provenance + SBOM/license evidence
  → RunSpec
  → HarnessManifest + DomainAdapter
  → explicit EvaluatorAuthority sidecar
  → digest-addressed HarnessPlan
  → OpenShell | Cloudflare Sandbox | Dynamic Worker | Fake/domain fixture
  → governed inference broker
  → EvidenceBundle + collector attestation + evidence IDs
  → deterministic verifiers + non-compensable security gate
  → digest-addressed HarnessVerdict
  → EvidenceGraph + ReplayManifest + LogicalTrace
  → evidence-first OutcomeScorecard
  → canonical RunArtifactStatement + DSSE Ed25519 signature
  → verifier-owned identity policy
  → transparency-log inclusion receipt
  → Skill × Agent × Runtime × Model compatibility cells
  → digest-addressed reports and ranking artifacts
```

## Repository topology → State Machine ownership

The repository is organized by state transition, not only by technology. Detailed transitions and invariants are in [`docs/STATE_MACHINES.md`](./docs/STATE_MACHINES.md).

```text
Skill.md-native/
├── AGENTS.md
│   └── repository policy, trust/evidence invariants, Agent working rules
├── README.md
│   └── current-state, topology, data-flow, Stack PR and traceability entrypoint
├── docs/
│   ├── architecture and evaluation contracts
│   ├── domain trust boundaries
│   ├── Run Artifact and attestation semantics
│   └── integration/state-machine/stack ledgers
├── src/skill_native/
│   ├── ingestion + provenance
│   ├── Harness contracts/compiler/verifiers
│   ├── domain contracts/runners/adapters
│   ├── runtime lifecycle/controllers
│   ├── governed inference
│   ├── evidence/security/scoring/reporting
│   ├── Run Artifact derivation
│   └── signing + transparency publication
├── cloudflare/
│   ├── worker/              deployable Sandbox bridge
│   └── dynamic-worker/      isolated Code Mode bridge
├── examples/
│   ├── harnesses/           deterministic domain fixtures
│   ├── run-artifacts/       authority/plan/evidence/verdict fixtures
│   └── attestations/        signing identity fixtures
├── schemas/                 generated public contracts; CI drift-checked
├── tests/                   transitions, failure paths, tamper and compatibility proofs
└── .github/workflows/       delivery and external verification state gates
```

| Directory/module group | State Machine responsibility | Primary output |
|---|---|---|
| `registries.py`, `github_ingest.py`, `provenance.py`, `supply_chain.py`, `run_factory.py` | mutable discovery → immutable pinned/materialized/inspected artifact | provenance digest, SBOM/license evidence, linked RunSpec |
| `models.py`, `harness_contract.py` | untyped input → strict contract | validated manifest/run/evidence models |
| `harness_adapters.py`, domain adapters | domain contract → command/stdin plan; raw evidence → domain evidence/checks | DomainAdapter plan and normalized evidence |
| `harness_kernel.py`, `harness_kernel_impl.py`, `harness_verifiers.py` | compile → execute → collect → verify | HarnessPlan, EvidenceBundle, HarnessVerdict |
| `coding_contract.py`, `coding_agent.py` | untrusted child task → trusted CodingAgentReceipt | events, workspace diff, deterministic test evidence |
| Browser modules on PR #29 | deterministic Browser actions → BrowserReceipt and artifacts | DOM/ARIA/network/screenshot/download evidence |
| Android modules planned by Issue #28 | constrained ADB actions → Android receipt and device/UI artifacts | scripted/emulator/device evidence with distinct states |
| `runtime.py`, `openshell.py`, `cloudflare_runtime.py`, controllers | prepare → execute → collect → destroy | raw runtime evidence and capability/evidence attestation |
| `gateway.py`, `providers.py`, `provider_metadata.py`, `policy.py` | request → policy/budget routing → provider attempts | inference receipts |
| `evidence.py`, `security.py`, `adversarial.py`, `security_benchmark.py` | observed behavior → evidence IDs/findings/security gate | EvidenceBundle security state |
| `scoring.py`, `compatibility.py`, `reporting.py` | explicit cells/samples → uncertainty/ranking report | recomputable cross-run reports |
| `run_artifact_*.py`, `run_artifacts.py` | authority + plan + evidence + verdict → trust graph/replay/trace/scorecard | RunArtifactBundle |
| `attestation_*.py`, `attestations.py`, `transparency_log.py` | valid bundle → signed/policy-verified/published artifact | DSSE envelope, verification and inclusion receipts |
| `schemas/` | model contract → deterministic JSON Schema | public machine-readable contracts |
| `tests/` and workflows | expected transition → executable evidence | regression/check artifacts; never an inferred claim |

## State Machine index

### A. Immutable ingestion

```text
DISCOVERED
→ RESOLVING
→ PINNED
→ MATERIALIZING
→ INSPECTED
→ PROVENANCE_READY

any invalid identity/extraction/entrypoint/license-contract condition
→ REJECTED
```

A mutable branch or tag may be an input to resolution, but it cannot remain the evaluated identity.

### B. Harness compilation

```text
MANIFEST_LOADED
→ CONTRACT_VALIDATED
→ ADAPTER_RESOLVED
→ CAPABILITY_MATCHED
→ POLICY_MATCHED
→ BUDGET_MATCHED
→ PLAN_COMPILED
→ PLAN_DIGEST_VALIDATED

unsupported/ambiguous/weaker input
→ REJECTED
```

The compiler fails closed on unknown adapters, domain mismatch, mutable provenance, unsupported evidence, unavailable capabilities, missing stdin transport, policy mismatch, or budget overrun.

### C. Runtime and domain execution

```text
PREPARED
→ EXECUTING
→ COLLECTING
→ DOMAIN_NORMALIZING
→ EVIDENCE_ATTESTED
→ DESTROYING
→ COMPLETED

failure at any stage
→ FAILED_CLOSED
→ DESTROYING
```

The runtime owns lifecycle and raw collection. The DomainAdapter owns domain receipt validation and normalization. The Harness Kernel owns global continuity, mandatory evidence, verifier aggregation, and the security gate.

### D. Verdict construction

```text
IDENTITY_CONTINUITY
→ COMMAND_INPUT_CONTINUITY
→ REQUIRED_EVIDENCE
→ DOMAIN_VERIFICATION
→ MANIFEST_VERIFICATION
→ SECURITY_GATE
→ VERDICT_PERSISTED
```

A High/Critical finding forces a failed security gate and cannot be compensated by task success.

### E. Run Artifact derivation

```text
AUTHORITY_VALIDATED
→ CROSS_ARTIFACT_CONTINUITY_VALIDATED
→ EVIDENCE_GRAPH_BUILT
→ REPLAY_CLASSIFIED
→ LOGICAL_TRACE_DERIVED
→ SCORECARD_BUILT
→ BUNDLE_VALIDATED
→ PERSISTED
```

Evaluator authority is outside the untrusted Skill package. Exact replay requires a captured immutable snapshot and pinned runtime identity. Logical timing remains `not-captured` until real timing evidence exists.

### F. Attestation and publication

```text
BUNDLE_VALIDATED
→ STATEMENT_BUILT
→ CANONICAL_DSSE_PAYLOAD
→ SIGNED
→ POLICY_VERIFIED
→ PUBLICATION_REVERIFIED
→ LOG_APPENDED
→ INCLUSION_RECEIPT_VERIFIED
```

Publication repeats bundle/signature/key/policy checks. A caller-supplied success receipt is never authoritative. Signing or publication cannot upgrade a failed verdict.

### G. Compatibility and ranking

```text
CELL_KEYED
→ SAMPLE_ACCUMULATED
→ SECURITY_ELIGIBLE
→ COVERAGE_EVALUATED
→ RANKED

missing evidence / failed verdict / failed security gate
→ INELIGIBLE
```

The minimum cell is:

```text
Skill artifact digest
× Agent harness/version
× Runtime/version
× Model/provider
```

No silent confounder pooling is allowed.

### H. GitHub delivery

```text
ISSUE_SCOPED
→ BRANCH_CREATED
→ DRAFT_PR
→ CHECKS_PENDING
→ REVIEWABLE
→ READY
→ MERGED
→ STATE_LEDGER_UPDATED

no job/external account or runner unavailable
→ BLOCKED_INFRASTRUCTURE
→ retry without fabricating a pass
```

Merge state and verification state are separate.

## End-to-end data flow and trust boundaries

```text
UNTRUSTED SOURCE
Registry / repository / Skill package
        │
        ▼
TRUSTED INGESTION CONTROL PLANE
immutable provenance + SBOM/license evidence
        │
        ▼
TRUSTED COMPILER
HarnessManifest + RunSpec + DomainAdapter
        │
        ▼
HarnessPlan ─────────────────────────────┐
        │                               │
        ▼                               │
UNTRUSTED EXECUTION TARGET              │
Skill / child coding agent / page / app │
        │                               │
        ▼                               │
TRUSTED RUNTIME + DOMAIN COLLECTORS     │
raw evidence → validated domain receipt │
        │                               │
        ▼                               │
EvidenceBundle ◄────────────────────────┘
        │
        ▼
TRUSTED VERIFIERS
continuity + required evidence + domain checks + security gate
        │
        ▼
HarnessVerdict
        │
        ▼
VERIFIER-OWNED AUTHORITY
EvidenceGraph + ReplayManifest + LogicalTrace + OutcomeScorecard
        │
        ▼
RunArtifactBundle
        │
        ▼
SIGNING / PUBLICATION CONTROL PLANE
DSSE signature + policy verification + transparency inclusion
        │
        ▼
CROSS-RUN ANALYTICS
compatibility cells + uncertainty + reports/ranking
```

## Stack PR and traceability index

### Git Town status

No repository-level `.git-branches.toml`, `git-town.toml`, `.git-town.toml`, or `git-town` path was detected on the snapshot `main`. The repository must not be described as currently Git Town-managed.

The project nevertheless uses a Git Town-compatible explicit ledger: every slice records its parent branch, exact head SHA, Issue, PR, evidence state, and non-claims. See [`docs/STACKED_DELIVERY.md`](./docs/STACKED_DELIVERY.md).

### Actual active graph

```text
main@032a933d15f3770b93be24aa9abfed98b9a2a898
└── agent/27-browser-playwright-harness@c58cbef0ac5f21356ccf454cd1bf1c6396e0049d
    └── PR #29 → Issue #27
        state: open / Draft / mergeable
        hosted workflows: action_required at snapshot
```

PR #29 is currently a single large feature node. Its conceptual atomic review slices are indexed as Browser contract, adapter, runner, artifact boundary, fixture runtime, graph/schema integration, tests, and workflow automation. These are **not** separate PRs.

### Planned Android terminal stack

The following branches are planned by documentation only and do not yet exist:

```text
main
└── agent/28-android-contract
    └── agent/28-android-runner
        └── agent/28-android-evidence
            └── agent/28-android-scripted-fixtures
                └── agent/28-android-emulator-ci
```

| Stack | Slice | Parent | Branch | Issue | PR | State | Establishes |
|---|---|---|---|---:|---:|---|---|
| Browser-27 | combined implementation | `main` | `agent/27-browser-playwright-harness` | 27 | 29 | actual Draft | implementation on branch; local evidence recorded in Issue |
| Android-28 | A1 contract/schema | `main` | `agent/28-android-contract` | 28 | — | planned | compile-time contract only |
| Android-28 | A2 trusted runner | A1 | `agent/28-android-runner` | 28 | — | planned | constrained ADB process/receipt boundary |
| Android-28 | A3 evidence/graph | A2 | `agent/28-android-evidence` | 28 | — | planned | artifact continuity and EvidenceBundle integration |
| Android-28 | A4 scripted fixtures | A3 | `agent/28-android-scripted-fixtures` | 28 | — | planned | deterministic scripted-fixture state |
| Android-28 | A5 emulator CI | A4 | `agent/28-android-emulator-ci` | 28 | — | planned | emulator state only after an executed persisted run |

A terminal PR should change one trust boundary and make one state transition independently executable. Public contract, trusted runner, runtime transport, EvidenceBundle semantics, security evaluator, Run Artifact lineage, external CI, and ranking policy should normally be separate slices.

### Historical merged chain

```text
PR #7  runtime evidence lab bootstrap
→ PR #17 Harness Kernel
→ PR #19 Coding Agent Harness
→ PR #22 Run Artifact Bundle
→ PR #26 stdin timeout hardening
→ PR #24 attestation and transparency
→ snapshot main
```

Old remote branches may remain, but merged branches are historical context rather than an active stack.

## Cross-domain Harness Kernel

The portable evaluation unit is:

```text
SKILL.md
+ harness.yaml
+ immutable RunSpec
+ runtime capability/evidence profile
+ executable assertions
+ EvidenceBundle
+ HarnessVerdict
```

Merged adapters on `main`:

```text
coding.command.v1
coding.agent.v1
```

Open branch implementation:

```text
browser.playwright.v1   # PR #29; not merged
```

Planned:

```text
android.adb.v1          # Issue #28; no implementation PR at snapshot
```

`coding.command.v1` is the deterministic command vertical slice. `coding.agent.v1` adds a trusted wrapper, structured events, workspace policy, independent tests, bounded output, stdin task delivery, and a digest-addressed `CodingAgentReceipt`.

Unknown adapters, unsupported capabilities/evidence, weaker policies, mutable Skill references, missing provenance, malformed receipts, and budget overruns fail closed.

```bash
skill-native validate-harness examples/harnesses/coding/harness.yaml
skill-native plan-harness \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml

skill-native validate-harness examples/harnesses/coding-agent/harness.yaml
skill-native plan-harness \
  examples/harnesses/coding-agent/harness.yaml \
  examples/harnesses/coding-agent/run.fake.yaml
```

The committed JSON Schemas are under [`schemas/`](./schemas). Schema generation is deterministic and CI compares generated output with committed files. A passing fake-runtime verdict is deterministic contract evidence, not live model or sandbox verification.

## Evaluator authority and Run Artifact Bundle

A package-supplied command, assertion, or test is not automatically trusted. `skill-native-run-artifacts` requires a separate `EvaluatorAuthority` sidecar that pins the evaluator and binds it to the exact manifest digest.

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

The builder validates authority, plan, verdict, run, provenance, runtime, evidence, graph, replay, trace, and scorecard continuity. Mutable evaluator refs such as `main`, `master`, `HEAD`, or `latest` are rejected.

```bash
skill-native-run-artifacts build \
  --authority examples/run-artifacts/authority.json \
  --plan examples/run-artifacts/plan.json \
  --evidence examples/run-artifacts/evidence.json \
  --verdict examples/run-artifacts/verdict.json \
  --output /tmp/run-artifacts
```

The `evidence-first-v1` scorecard keeps these failures non-compensable:

```text
High/Critical finding or failed security gate
failed HarnessVerdict
missing mandatory evidence
failed verifier
```

See [`docs/RUN_ARTIFACTS.md`](./docs/RUN_ARTIFACTS.md).

## Signed attestations and transparency publication

`skill-native-attest` binds the exact Run Artifact Bundle to a canonical in-toto-style statement, signs DSSE pre-authentication bytes with Ed25519, verifies derived key identity and signed claims against verifier-owned policy, and publishes only re-verified envelopes to a local hash-chained Merkle log.

```text
RunArtifactBundle
→ RunArtifactStatement
→ canonical DSSE payload
→ Ed25519 signature
→ AttestationTrustPolicy
→ AttestationVerificationReceipt
→ TransparencyLogEntry
→ checkpoint + inclusion receipt
```

```bash
skill-native-attest generate-key \
  --private-key /tmp/signing-key.pem \
  --public-key /tmp/signing-key.pub.pem

skill-native-attest create-policy \
  --policy-id skill-native.local \
  --public-key /tmp/signing-key.pub.pem \
  --output /tmp/attestation-policy.json

skill-native-attest sign \
  --bundle /tmp/run-artifacts/<digest>/run-artifact-bundle.json \
  --identity examples/attestations/identity.json \
  --private-key /tmp/signing-key.pem \
  --output /tmp/run-artifact.dsse.json

skill-native-attest log-append \
  --bundle /tmp/run-artifacts/<digest>/run-artifact-bundle.json \
  --envelope /tmp/run-artifact.dsse.json \
  --public-key /tmp/signing-key.pub.pem \
  --policy /tmp/attestation-policy.json \
  --log /tmp/run-artifacts-transparency.jsonl \
  --receipt-output /tmp/inclusion-receipt.json
```

Content addressing, signing, policy verification, transparency publication, integration verification, and runtime verification are distinct states. The local checkpoint is not independently signed or publicly witnessed and is not a Sigstore/Rekor replacement. See [`docs/ATTESTATIONS.md`](./docs/ATTESTATIONS.md).

## Immutable ingestion and supply-chain evidence

### GitHub

```bash
skill-native ingest-github https://github.com/vercel-labs/agent-skills \
  --ref main \
  --skill-path skills/react-best-practices \
  --output .skill-native/artifacts/react-best-practices \
  --provenance-dir .skill-native/provenance
```

Mutable input is resolved to an immutable commit before evaluation. Provenance records content SHA-256, source/publisher attestations, license evidence, dependency manifests, SBOM digest, and a deterministic provenance digest.

### Other registries

`SkillsShAdapter` uses the documented API and operator-owned authorization. OpenAI Plugin metadata ingestion accepts only operator-supplied accessible first-party JSON metadata; it does not scrape authenticated UI or invent undocumented endpoints.

A `harness.yaml` license block is a declaration only. It never overrides source license files, dependencies, model/dataset licenses, or provenance evidence.

## Governed inference broker

The OpenAI-compatible broker supports configured Groq, Gemini, Workers AI, and local endpoints. It provides local-only routing, deterministic provider pinning, operator request/token/cost ceilings, normalized rate-limit evidence, capability/privacy metadata, and an append-only receipt ledger.

```bash
skill-native serve-gateway examples/providers.yaml \
  --local-only \
  --receipt-ledger .skill-native/inference.jsonl \
  --max-daily-requests 100 \
  --max-daily-tokens 100000
```

Credentials remain operator-owned. Credential harvesting, account farming, quota-bypass rotation, and unauthorized key pooling are outside the contract.

## Runtimes

### NVIDIA OpenShell

OpenShell is the hostile-code reference runtime. The adapter provides deny-by-default network policy, hard Landlock where required, filesystem manifests, OCSF evidence, effective policy/runtime attestation, provider attachment, credential non-exposure probes, and fail-closed mandatory evidence checks.

Issue #1 remains open until persisted real OpenShell evidence exists. Issue #2 requires the same runtime to prove brokered inference without raw credential exposure.

### Cloudflare Sandbox and Dynamic Workers

`cloudflare/worker/` is a deployable Sandbox bridge with explicit outbound policy and control-plane credential injection. `cloudflare/dynamic-worker/` uses isolated Worker loading with no global outbound capability by default.

Issue #3 remains open until real account-backed cold/warm, egress, resource, and credential-isolation evidence is persisted.

### Enroot and Fake

Enroot is a performance/compatibility reference, not the primary hostile-code boundary. `FakeRuntime` validates contracts and CI logic only and records deterministic/mock verification state.

## Adversarial benchmark, compatibility, and ranking

Executable benign/malicious fixtures cover prompt/code injection, credential access, undeclared egress, control-file mutation, persistence, and sandbox probes. Findings cite immutable evidence IDs. High/Critical findings force the security gate to fail.

Issue #5 remains open until live runtime detector recall/FPR is measured from persisted real executions.

`ScorePolicy v0.4` uses versioned compatibility-matrix weights:

- correctness: 70%
- reproducibility: 20%
- least privilege: 10%
- any High/Critical security gate failure: aggregate score = 0

The Run Artifact scorecard is a per-run prerequisite layer; it does not replace multi-cell statistical ranking. Reports retain raw latency, tokens, cost, recovery, denied-network and coverage dimensions with uncertainty.

```bash
skill-native build-report matrix-input.jsonl --output report.json
```

## Verification states

Use these terms precisely:

- **planned** — requirements exist; implementation has not landed.
- **implemented** — code, schemas, fixtures, and deterministic tests exist.
- **content-addressed** — object and nested continuity digests validate.
- **cryptographically signed** — an Ed25519 signature covers the exact canonical statement.
- **policy verified** — key identity and signed claims match verifier-owned policy.
- **transparency published** — a policy-verified envelope has an inclusion receipt.
- **integration-verified** — a real external source/service produced persisted evidence.
- **runtime-verified** — the pinned artifact ran in the declared isolated runtime and passed required assertions.
- **blocked infrastructure** — an account, approval, runner, billing, or external service prevented execution.

A configured workflow is not a passing workflow. A signature is not runtime evidence. A log inclusion is not task correctness. No-job and `action_required` states are not green CI.

## Documentation index

Start at [`docs/README.md`](./docs/README.md).

| Document | Purpose |
|---|---|
| [`AGENTS.md`](./AGENTS.md) | canonical repository requirements and Agent rules |
| [`docs/INTEGRATION_STATE.md`](./docs/INTEGRATION_STATE.md) | merged/open/planned/blocked truth ledger |
| [`docs/STATE_MACHINES.md`](./docs/STATE_MACHINES.md) | detailed state transitions, directory ownership, trust boundaries |
| [`docs/STACKED_DELIVERY.md`](./docs/STACKED_DELIVERY.md) | Git Town detection, actual/planned stacks, PR atomicity and retarget protocol |
| [`docs/HARNESS_KERNEL.md`](./docs/HARNESS_KERNEL.md) | cross-domain Harness contract |
| [`docs/CODING_AGENT_HARNESS.md`](./docs/CODING_AGENT_HARNESS.md) | Coding trusted runner and receipt boundary |
| [`docs/RUN_ARTIFACTS.md`](./docs/RUN_ARTIFACTS.md) | evaluator authority, graph, replay, trace and scorecard |
| [`docs/ATTESTATIONS.md`](./docs/ATTESTATIONS.md) | DSSE/signing/policy/transparency semantics |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | overall architecture |
| [`docs/EVALUATION_CONTRACT.md`](./docs/EVALUATION_CONTRACT.md) | evidence and evaluation contract |

## License

Repository source is licensed under the [MIT License](./LICENSE). Model weights, datasets, third-party Skills, generated artifacts, and dependencies may carry separate licenses and must be evaluated independently.
