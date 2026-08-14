# Skill.md-native

Runtime-verified evidence, security, compatibility, and outcome ranking for Agent Skills across registries and execution domains.

> **Agents:** read [`AGENTS.md`](./AGENTS.md) → this README → [`docs/INTEGRATION_STATE.md`](./docs/INTEGRATION_STATE.md) → relevant domain docs → [`docs/STATE_MACHINES.md`](./docs/STATE_MACHINES.md) → [`docs/STACKED_DELIVERY.md`](./docs/STACKED_DELIVERY.md).

## Current integration snapshot — 2026-08-14

| Area | State | Trace |
|---|---|---|
| Cross-domain Harness Kernel | merged | #17 |
| Coding Agent Harness | merged/hardened | #19, #26 |
| Run Artifact / Evidence Graph / replay / scorecard | merged | #22 |
| DSSE Ed25519 + transparency | merged | #24 |
| Playwright Browser Harness | merged/hardened | #29, #32 |
| Android bounded contract | merged | #35 |
| Android canonical compile boundary | **merged on main** | #37; `main@afbab914ba09fa5743bead3f059316c3ece7fcab`; unit #136 + integration #56 succeeded before merge |
| Android HarnessManifest/ADB runner/evidence/emulator | pending | Issue #28 |
| OpenShell/Cloudflare live evidence gates | externally pending where evidence is absent | #1/#2/#3/#5 |

Verification states are not interchangeable: `implemented`, `CI-verified`, `scripted-fixture`, `emulator`, `physical-device`, and `runtime-isolated` each require their own evidence.

## End-to-end product chain

```text
Registry / Repository / Plugin
→ immutable provenance + SBOM/license evidence
→ RunSpec
→ HarnessManifest + DomainAdapter
→ digest-addressed HarnessPlan
→ controlled runtime/domain runner
→ raw evidence + trusted domain receipt
→ EvidenceBundle
→ deterministic verifiers + non-compensable security gate
→ HarnessVerdict
→ EvidenceGraph + ReplayManifest + LogicalTrace + OutcomeScorecard
→ RunArtifactBundle
→ optional DSSE + trust policy + transparency inclusion
→ Skill × Agent × Runtime × Model compatibility cells
→ evidence-traceable ranking/report
```

## Repository topology → State Machine ownership

```text
Skill.md-native/
├── AGENTS.md
│   └── Agent policy, trust invariants, current handoff rules
├── README.md
│   └── topology, state-machine map, data flow, Stack PR index
├── docs/
│   ├── INTEGRATION_STATE.md   exact mutable state ledger
│   ├── STATE_MACHINES.md      detailed transitions
│   ├── STACKED_DELIVERY.md    stack parent/PR rules
│   ├── HARNESS_KERNEL.md      kernel/compiler contract
│   ├── CODING_AGENT_HARNESS.md / Browser/Android domain docs
│   ├── RUN_ARTIFACTS.md
│   └── ATTESTATIONS.md
├── src/skill_native/
│   ├── registries.py / github_ingest.py / provenance.py / supply_chain.py
│   │   └── discovery → immutable artifact identity
│   ├── models.py / harness_contract.py
│   │   └── untyped input → strict contract
│   ├── harness_adapters.py / *_contract.py / *_compile.py
│   │   └── domain contract → trusted command/stdin plan
│   ├── harness_kernel*.py / harness_verifiers.py
│   │   └── plan → capability/policy/budget checks → verdict
│   ├── coding_agent.py / browser modules / future Android runner
│   │   └── untrusted target → trusted domain receipt
│   ├── runtime.py / openshell.py / cloudflare_runtime.py
│   │   └── prepare → execute → collect → destroy
│   ├── gateway.py / providers.py / policy.py
│   │   └── inference request → governed receipt
│   ├── evidence.py / security.py / adversarial.py
│   │   └── observation → evidence IDs/findings/security gate
│   ├── run_artifact*.py / run_artifacts.py
│   │   └── plan+evidence+verdict → graph/replay/trace/scorecard
│   ├── attestations.py / transparency_log.py
│   │   └── valid bundle → signature/policy/publication
│   └── compatibility.py / scoring.py / reporting.py
│       └── explicit cells → uncertainty-aware ranking
├── schemas/                 generated public contracts; drift-checked
├── examples/                deterministic fixtures, never production claims
├── tests/                   success/failure/tamper/continuity proofs
├── cloudflare/              cloud runtime bridges
└── .github/workflows/       delivery and external evidence gates
```

## State Machine index

### Immutable ingestion

```text
DISCOVERED → RESOLVING → PINNED → MATERIALIZING → INSPECTED → PROVENANCE_READY
invalid/mutable/ambiguous identity → REJECTED
```

### Harness compilation

```text
MANIFEST_LOADED
→ CONTRACT_VALIDATED
→ ADAPTER_RESOLVED
→ CAPABILITY_MATCHED
→ POLICY_MATCHED
→ BUDGET_MATCHED
→ PLAN_COMPILED
→ PLAN_DIGEST_VALIDATED
unsupported/weaker input → REJECTED
```

### Domain/runtime execution

```text
PREPARED → EXECUTING → COLLECTING → DOMAIN_NORMALIZING
→ EVIDENCE_ATTESTED → DESTROYING → COMPLETED
failure → FAILED_CLOSED → DESTROYING
```

Runtime owns lifecycle/raw collection; domain runner owns the trusted receipt; adapter owns normalization; kernel owns global continuity/verdict.

### Verdict

```text
IDENTITY_CONTINUITY
→ COMMAND_INPUT_CONTINUITY
→ REQUIRED_EVIDENCE
→ DOMAIN_VERIFICATION
→ MANIFEST_VERIFICATION
→ SECURITY_GATE
→ VERDICT_PERSISTED
```

### Run Artifact

```text
AUTHORITY_VALIDATED
→ CROSS_ARTIFACT_CONTINUITY
→ EVIDENCE_GRAPH_BUILT
→ REPLAY_CLASSIFIED
→ LOGICAL_TRACE_DERIVED
→ SCORECARD_BUILT
→ BUNDLE_VALIDATED
→ PERSISTED
```

### Attestation/publication

```text
BUNDLE_VALIDATED → STATEMENT_BUILT → CANONICAL_DSSE_PAYLOAD → SIGNED
→ POLICY_VERIFIED → PUBLICATION_REVERIFIED → LOG_APPENDED → INCLUSION_RECEIPT_VERIFIED
```

Signing cannot upgrade a failed verdict.

### Compatibility/ranking

```text
CELL_KEYED → SAMPLE_ACCUMULATED → SECURITY_ELIGIBLE → COVERAGE_EVALUATED → RANKED
missing evidence / failed security → INELIGIBLE
```

Minimum cell: `Skill digest × Agent/version × Runtime/version × Model/provider`.

### GitHub delivery

```text
ISSUE_SCOPED → TERMINAL_BRANCH → DRAFT_PR → CHECKS_PENDING
→ REVIEWABLE → READY → MERGED → LEDGER_UPDATED
external runner/account unavailable → BLOCKED_INFRASTRUCTURE
```

Merge state != verification state.

## Trust-boundary data flow

```text
UNTRUSTED SOURCE
registry / repo / Skill
        ↓
TRUSTED INGESTION
immutable provenance + supply-chain evidence
        ↓
TRUSTED COMPILER
manifest + RunSpec + DomainAdapter
        ↓
HarnessPlan ───────────────────────────────┐
        ↓                                 │
UNTRUSTED TARGET                          │
Skill / child agent / page / app/device   │
        ↓                                 │
TRUSTED RUNTIME + DOMAIN COLLECTOR        │
raw evidence + validated receipt          │
        ↓                                 │
EvidenceBundle ◄──────────────────────────┘
        ↓
TRUSTED VERIFIERS
continuity + mandatory evidence + domain checks + security gate
        ↓
HarnessVerdict
        ↓
VERIFIER-OWNED RUN ARTIFACT DERIVATION
        ↓
RunArtifactBundle
        ↓
SIGNING / PUBLICATION CONTROL PLANE
        ↓
CROSS-RUN ANALYTICS / RANKING
```

## Domain status

### Coding
Merged execution/evidence vertical slice.

### Browser
Merged Playwright vertical slice plus #32 stdin/evidence/origin/budget hardening. Local deterministic Browser evidence is not automatically public-site, credentialed-site, hosted-browser, or isolated-runtime evidence.

### Android
Main now contains:

```text
AndroidContract
→ contract_digest
→ action_plan_digest
→ AndroidRunnerConfig
→ canonical stdin JSON
→ SHA-256(stdin bytes)
→ fixed argv: skill-native-android-runner --config-stdin
```

The bounded contract supports typed activity/key/tap/swipe/wait/state-check/UI-capture actions, device constraints, ADB version/SHA constraints, final assertions, and artifact budgets. It intentionally exposes no arbitrary shell/free-form ADB primitive.

It still does **not** establish a registered `android.adb.v1` DomainAdapter, real ADB subprocess execution, AndroidReceipt, EvidenceBundle integration, emulator evidence, or physical-device evidence.

## Git Town status

No repository-level `.git-branches.toml`, `git-town.toml`, `.git-town.toml`, or Git Town path is detected. The repository is not currently claimed to be Git Town-managed.

We use a Git Town-compatible explicit Stack PR ledger. If Git Town is adopted later, terminal trust-boundary slices should map one-to-one to stack branches.

## Stack PR traceability index

### Merged chain

```text
#7 runtime/evidence bootstrap
→ #17 Harness Kernel
→ #19 Coding Agent Harness
→ #22 Run Artifact Bundle
→ #26 stdin hardening
→ #24 attestation/transparency
→ #29 Browser Harness
→ #32 Browser hardening
→ #35 Android contract
→ #37 Android compile boundary
→ main@afbab914ba09fa5743bead3f059316c3ece7fcab
```

### Android-28 terminal stack

```text
main@afbab914...
└── A1c HarnessManifest + android.adb.v1 wiring      NEXT
    └── A2a ADB binary/device/typed-argv primitives
        └── A2b bounded subprocess lifecycle
            └── A3 AndroidReceipt + artifact/evidence
                └── A4 scripted fake-ADB verification
                    └── A5 fixed emulator CI
                        ├── A6 Appium/Maestro
                        └── A7 Mobly/multi-device
```

| Slice | State | Establishes | Does not establish |
|---|---|---|---|
| A1 #35 | merged | bounded Android contract | execution |
| A1b #37 | merged | canonical compile/stdin continuity | ADB runner/evidence |
| A1c | next | manifest/domain-adapter compile wiring | device execution |
| A2a | planned | ADB binary/device/typed argv | subprocess lifecycle |
| A2b | planned | bounded process boundary | evidence completeness |
| A3 | planned | receipt/artifact/EvidenceBundle continuity | emulator verification |
| A4 | planned | scripted fixture verification | real emulator/device |
| A5 | planned | emulator verification after persisted run | physical device |

Historical PRs #31/#34/#33 are stale-ancestry evidence, not active parents.

## Terminal PR rule

Every stack entry records:

```text
Stack-ID
Parent-Branch
Parent-Head-At-Open
Slice
Depends-On
Establishes-State
Does-Not-Claim
```

One terminal PR should normally change one trust boundary. After squash-merging a parent, rebuild/retarget children to the new main and obtain fresh CI.

## Documentation rule

After every merge or verification-state change, update this README, `docs/INTEGRATION_STATE.md`, and the stack ledger. Source-of-truth order is runtime evidence → Actions → merged commits → PR metadata → Issues → docs → memory.
