# Skill.md-native

Runtime-verified evidence, security, compatibility, and outcome ranking for Agent Skills across registries and execution domains.

> **Agents:** read [`AGENTS.md`](./AGENTS.md) → this README → [`docs/INTEGRATION_STATE.md`](./docs/INTEGRATION_STATE.md) → relevant domain docs → [`docs/STATE_MACHINES.md`](./docs/STATE_MACHINES.md) → [`docs/STACKED_DELIVERY.md`](./docs/STACKED_DELIVERY.md) before changing code or delivery state.

## Current integration snapshot — 2026-08-14

| Area | State | Trace |
|---|---|---|
| Cross-registry provenance/runtime/evaluation MVP | merged | PR #7 lineage |
| Cross-domain Harness Kernel | merged | PR #17 |
| Coding Agent Harness | merged | PR #19 + hardening #26 |
| Run Artifact / Evidence Graph / replay / scorecard | merged | PR #22 |
| DSSE Ed25519 + transparency publication | merged | PR #24 |
| Playwright Browser Harness | merged + hardened | PR #29, Browser continuity hotfix #32 |
| Android bounded contract | **merged on main** | PR #35, `main@49251371eddc36da8b4337eceef4575993ed1824` |
| Android compile boundary | CI verified, landing to main | stacked PR #36; main-target PR #37; unit #136 + integration #56 success |
| Android trusted ADB runner/evidence/emulator | not yet established | Issue #28 |
| OpenShell/Cloudflare live gates | externally pending where account/runtime evidence is absent | Issues #1/#2/#3/#5 |

`implemented`, `CI verified`, `scripted-fixture verified`, `emulator verified`, `physical-device verified`, and `runtime-isolated verified` are different states.

## Mission and trust chain

Every third-party Skill is an untrusted executable supply-chain artifact. The desired chain is:

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
→ optional DSSE signature + verifier-owned trust policy + transparency receipt
→ Skill × Agent × Runtime × Model compatibility cells
→ evidence-traceable ranking/report
```

## Repository topology → State Machine ownership

```text
Skill.md-native/
├── AGENTS.md
│   └── long-lived Agent policy, trust invariants, current handoff rules
├── README.md
│   └── topology, state-machine map, end-to-end data flow, stack index
├── docs/
│   ├── INTEGRATION_STATE.md   exact mutable integration ledger
│   ├── STATE_MACHINES.md      detailed transition definitions
│   ├── STACKED_DELIVERY.md    parent/branch/PR lineage and merge rules
│   ├── HARNESS_KERNEL.md      compiler/kernel contract
│   ├── CODING_AGENT_HARNESS.md
│   ├── BROWSER_HARNESS.md / browser docs when present
│   ├── ANDROID_HARNESS.md     Android trust boundary/roadmap when present
│   ├── RUN_ARTIFACTS.md
│   └── ATTESTATIONS.md
├── src/skill_native/
│   ├── registries.py / github_ingest.py / provenance.py / supply_chain.py
│   │   └── discovery → immutable artifact identity
│   ├── models.py / harness_contract.py
│   │   └── untyped input → strict contracts
│   ├── harness_adapters.py / *_contract.py / *_compile.py
│   │   └── domain contract → trusted command/stdin plan
│   ├── harness_kernel*.py / harness_verifiers.py
│   │   └── compile → capability/policy/budget checks → verdict
│   ├── coding_agent.py / browser runner modules / future android runner
│   │   └── untrusted target → trusted domain receipt
│   ├── runtime.py / openshell.py / cloudflare_runtime.py
│   │   └── prepare → execute → collect → destroy
│   ├── gateway.py / providers.py / policy.py
│   │   └── inference request → governed provider receipt
│   ├── evidence.py / security.py / adversarial.py
│   │   └── observations → evidence IDs/findings/security gate
│   ├── run_artifact*.py / run_artifacts.py
│   │   └── plan+evidence+verdict → graph/replay/trace/scorecard
│   ├── attestations.py / transparency_log.py
│   │   └── valid bundle → signature/policy/publication receipt
│   └── compatibility.py / scoring.py / reporting.py
│       └── explicit cells → uncertainty-aware ranking/report
├── schemas/
│   └── generated machine contracts; CI drift-checked
├── examples/
│   └── deterministic vertical fixtures; never production claims
├── tests/
│   └── positive, failure, tamper and continuity proofs
├── cloudflare/
│   └── cloud runtime bridges
└── .github/workflows/
    └── delivery checks and external verification gates
```

## State Machine index

### 1. Immutable ingestion

```text
DISCOVERED
→ RESOLVING
→ PINNED
→ MATERIALIZING
→ INSPECTED
→ PROVENANCE_READY

invalid/mutable/ambiguous identity → REJECTED
```

### 2. Harness compilation

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

### 3. Domain/runtime execution

```text
PREPARED
→ EXECUTING
→ COLLECTING
→ DOMAIN_NORMALIZING
→ EVIDENCE_ATTESTED
→ DESTROYING
→ COMPLETED

failure → FAILED_CLOSED → DESTROYING
```

Runtime owns lifecycle/raw collection. Domain runner owns trusted domain receipt. Adapter owns normalization. Kernel owns global continuity and verdict aggregation.

### 4. Verdict

```text
IDENTITY_CONTINUITY
→ COMMAND_INPUT_CONTINUITY
→ REQUIRED_EVIDENCE
→ DOMAIN_VERIFICATION
→ MANIFEST_VERIFICATION
→ SECURITY_GATE
→ VERDICT_PERSISTED
```

High/Critical findings are non-compensable.

### 5. Run Artifact derivation

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

### 6. Attestation/publication

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

Signature/publication cannot upgrade a failed verdict.

### 7. Compatibility/ranking

```text
CELL_KEYED
→ SAMPLE_ACCUMULATED
→ SECURITY_ELIGIBLE
→ COVERAGE_EVALUATED
→ RANKED

missing evidence / failed security → INELIGIBLE
```

Minimum cell:

```text
Skill artifact digest × Agent/version × Runtime/version × Model/provider
```

### 8. GitHub delivery

```text
ISSUE_SCOPED
→ TERMINAL_BRANCH
→ DRAFT_PR
→ CHECKS_PENDING
→ REVIEWABLE
→ READY
→ MERGED
→ LEDGER_UPDATED

external runner/account unavailable → BLOCKED_INFRASTRUCTURE
```

Merge state is not verification state.

## End-to-end trust-boundary data flow

```text
UNTRUSTED SOURCE
registry / repo / Skill package
        ↓
TRUSTED INGESTION
immutable provenance + supply-chain evidence
        ↓
TRUSTED COMPILER
manifest + RunSpec + DomainAdapter
        ↓
HarnessPlan ─────────────────────────────┐
        ↓                               │
UNTRUSTED EXECUTION TARGET              │
Skill / child agent / browser page / app/device
        ↓                               │
TRUSTED RUNTIME + DOMAIN COLLECTOR      │
raw evidence + validated receipt        │
        ↓                               │
EvidenceBundle ◄────────────────────────┘
        ↓
TRUSTED VERIFIERS
continuity + required evidence + domain checks + security gate
        ↓
HarnessVerdict
        ↓
VERIFIER-OWNED RUN ARTIFACT DERIVATION
EvidenceGraph + ReplayManifest + LogicalTrace + OutcomeScorecard
        ↓
RunArtifactBundle
        ↓
SIGNING / PUBLICATION CONTROL PLANE
DSSE + trust policy + transparency inclusion
        ↓
CROSS-RUN ANALYTICS
compatibility + uncertainty + ranking/report
```

## Domain state

### Coding

Merged. `coding.command.v1` and `coding.agent.v1` provide deterministic command and child-agent execution paths with bounded output, workspace policy, tests, evidence and receipt continuity.

### Browser

Merged and hardened. The trusted Playwright path uses canonical stdin-bound configuration, origin constraints, DOM/ARIA/network/screenshot/download evidence, artifact integrity, deterministic final assertions, and explicit non-isolated fixture labeling.

### Android

Current main contains `android_contract.py` from PR #35. The contract defines a bounded grammar for activity start, key events, tap/swipe, bounded waits, package/activity/UI-text waits, UI hierarchy and screenshot capture; device constraints; ADB version/SHA constraints; final assertions; and artifact budgets.

The next compile layer is represented by PR #37 and must land before being described as a main capability:

```text
AndroidContract
→ contract_digest
→ action_plan_digest
→ AndroidRunnerConfig
→ canonical stdin JSON
→ SHA-256(stdin bytes)
→ fixed argv: skill-native-android-runner --config-stdin
```

No arbitrary shell/free-form ADB command belongs in v1.

## Git Town status

No repository-level `.git-branches.toml`, `git-town.toml`, `.git-town.toml`, or Git Town path is detected on current main. Therefore the repository is **not** currently claimed to be Git Town-managed.

We use a Git Town-compatible explicit stack ledger instead. If Git Town is later committed, it must preserve the same parent/terminal-slice traceability.

## Stack PR traceability index

### Historical merged chain

```text
PR #7   runtime/evidence bootstrap
→ #17   Cross-domain Harness Kernel
→ #19   Coding Agent Harness
→ #22   Run Artifact Bundle
→ #26   Coding stdin timeout hardening
→ #24   Attestation/transparency
→ #29   Browser Harness
→ #32   Browser stdin/evidence/origin/budget hardening
→ #35   Android bounded contract
→ main@49251371eddc36da8b4337eceef4575993ed1824
```

### Active Android-28 stack

```text
main@49251371...
│
├── #37  land Android compile boundary to main
│   └── derived from CI-green stacked #36
│
└── after #37 merge:
    A1c HarnessManifest + android.adb.v1 registration
        ↓
    A2a ADB binary/device/typed-argv primitives
        ↓
    A2b bounded subprocess lifecycle
        ↓
    A3 AndroidReceipt + artifact/evidence normalization
        ↓
    A4 scripted fake-ADB verification
        ↓
    A5 fixed emulator CI + persisted evidence
        ↓
    A6 Appium/Maestro
        ↓
    A7 Mobly/multi-device
```

| Stack | Slice | Trace | State | Establishes | Does not establish |
|---|---|---|---|---|---|
| Android-28 | A1 contract | PR #35 | merged | bounded compile-time Android contract | ADB execution |
| Android-28 | A1b compile | PR #36 → #37 | unit #136 + integration #56 success; #37 pending merge | canonical runner config/stdin continuity | runner/evidence |
| Android-28 | A1c manifest wiring | planned | — | `android.adb.v1` compiler registration | device execution |
| Android-28 | A2a ADB primitives | planned refreshed slice | prior prototype exists only as historical branch | binary/device/argv boundary | subprocess lifecycle |
| Android-28 | A2b process runner | planned | — | timeout/output/process cleanup | evidence completeness |
| Android-28 | A3 evidence | planned | — | receipt/artifact/EvidenceBundle continuity | emulator verification |
| Android-28 | A4 scripted fixture | planned | — | deterministic scripted verification | real emulator/device |
| Android-28 | A5 emulator | planned | — | emulator verification only after executed persisted run | physical device |

Historical PRs #31/#34/#33 are stale-ancestry evidence, not the active delivery chain.

## Terminal PR rule

A terminal PR should modify one trust boundary and make one state transition independently reviewable. Record in every stack entry:

```text
Stack-ID
Parent-Branch
Parent-Head-At-Open
Slice
Depends-On
Establishes-State
Does-Not-Claim
```

After squash-merging a parent, rebuild or retarget children to the new main. Do not carry stale ancestry forward and repair unrelated regressions in child slices.

## Documentation and evidence rule

When a merge or verification state changes, update this README plus `docs/INTEGRATION_STATE.md` and `docs/STACKED_DELIVERY.md` in the same delivery sequence. Never copy old state forward without checking GitHub.

Source-of-truth order:

```text
persisted runtime evidence
> executed Actions
> merged commits
> current PR metadata
> canonical Issues
> documentation
> Agent memory
```

See [`docs/README.md`](./docs/README.md) for the full document index.
