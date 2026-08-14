# Skill.md-native

**Runtime-verified trust, evidence, security, compatibility, and outcome ranking for Agent Skills / `SKILL.md` workflows.**

Skill.md-native is a cross-registry Harness Engineering layer for answering a harder question than “can this Skill be discovered or installed?”:

> **What exact Skill ran, in what runtime, with what permissions and model, what actually happened, did the task succeed, was it safe, can the result be replayed, and can every ranking claim be traced back to immutable evidence?**

The repository treats every third-party Skill, prompt package, coding-agent task, browser page, device target, model response, runtime output, and external artifact as untrusted until it crosses an explicit verifier-owned trust boundary.

> **Coding/AI Agents:** read [`AGENTS.md`](./AGENTS.md) → this README → [`docs/INTEGRATION_STATE.md`](./docs/INTEGRATION_STATE.md) → the relevant domain/trust document → [`docs/STATE_MACHINES.md`](./docs/STATE_MACHINES.md) → [`docs/STACKED_DELIVERY.md`](./docs/STACKED_DELIVERY.md) before changing code, schemas, runtime adapters, evidence semantics, Issues, CI, or delivery state.

---

## What this repository is for

Skill.md-native is designed for teams building or evaluating reusable Agent Skills across coding agents, browser automation, Android/device automation, isolated runtimes, hosted sandboxes, model providers, and future execution domains.

It provides five connected capabilities:

1. **Immutable Skill identity and provenance** — resolve mutable registry/repository references into pinned artifacts with content digests and supply-chain evidence.
2. **Cross-domain Harness execution contracts** — compile `harness.yaml` + `RunSpec` + a trusted `DomainAdapter` into a digest-addressed execution plan.
3. **Evidence-first verification** — collect runtime/domain receipts, artifacts, security findings, deterministic assertions, and fail closed when required evidence is absent or inconsistent.
4. **Run Artifact lineage and attestation** — derive Evidence Graphs, replay classification, logical traces, scorecards, DSSE signatures, trust-policy verification, and transparency inclusion receipts.
5. **Compatibility and ranking** — compare `Skill × Agent × Runtime × Model` cells without silently pooling confounders or allowing task success to compensate for a failed security gate.

It is **not** primarily another Skill marketplace, prompt registry, agent framework, or leaderboard. Discovery and execution frameworks are inputs. The product boundary is the verifier-owned evidence/evaluation layer above them.

## Typical use cases

```text
Open-source Skill evaluation
  GitHub / registry Skill
  → immutable provenance
  → sandbox/domain execution
  → evidence + verdict
  → reproducible report

Coding Agent evaluation
  issue/task
  → coding.agent.v1
  → trusted child-agent receipt
  → workspace diff + tests + security evidence
  → verdict / RunArtifactBundle

Browser automation evaluation
  deterministic Playwright contract
  → browser.playwright.v1
  → DOM/ARIA/network/screenshot/download evidence
  → final-state assertions
  → verdict

Android Harness development
  AndroidContract
  → canonical stdin-bound runner config
  → future android.adb.v1 runner
  → UI/device/artifact evidence
  → emulator / physical-device verification states kept distinct

Cross-runtime / cross-model benchmarking
  same immutable Skill + scenario
  × different Agent / Runtime / Model
  → explicit compatibility cells
  → evidence-traceable ranking
```

---

# Quick start

## Requirements

- Python 3.11+
- Git
- Optional Browser integration: Playwright Chromium
- Optional live runtimes: their own credentials/accounts and external prerequisites

Install the core package:

```bash
git clone https://github.com/ed3c/Skill.md-native.git
cd Skill.md-native
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Install the Browser extra when working with Playwright:

```bash
python -m pip install -e '.[browser]'
python -m playwright install chromium
```

Discover the CLI surface:

```bash
skill-native --help
```

## 1. Validate a `RunSpec`

```bash
skill-native validate path/to/run.yaml
```

This performs contract validation only. A valid spec is **not** runtime verification.

## 2. Validate a Harness manifest

```bash
skill-native validate-harness examples/harnesses/coding/harness.yaml
```

The command prints the normalized manifest and its deterministic digest.

## 3. Compile a deterministic Harness plan

```bash
skill-native plan-harness \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml
```

Compilation checks immutable provenance, adapter/domain compatibility, runtime capabilities, evidence support, policy strength, budgets, stdin transport, verifier availability, and replay requirements before execution.

## 4. Run the deterministic FakeRuntime vertical slice

```bash
skill-native run-harness-fake \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml \
  --evidence-dir .skill-native/evidence \
  --verdict-dir .skill-native/verdicts
```

This is useful for contract/evidence/verdict regression. `deterministic-mock` evidence must never be reported as live sandbox, hosted runtime, emulator, or physical-device verification.

## 5. Ingest a GitHub Skill immutably

```bash
skill-native ingest-github \
  https://github.com/OWNER/REPO \
  --ref main \
  --skill-path path/to/skill \
  --entrypoint SKILL.md \
  --output .skill-native/materialized \
  --provenance-dir .skill-native/provenance
```

A mutable branch may be supplied as a discovery input, but the evaluated identity is resolved to immutable provenance before downstream ranking claims are allowed.

## 6. Compile an OpenShell policy

```bash
skill-native compile-openshell-policy path/to/run.yaml
```

Policy compilation is not the same as executing and verifying a live OpenShell run.

## 7. Execute a configured runtime

Fake runtime:

```bash
skill-native run-fake path/to/run.yaml \
  --evidence-dir .skill-native/evidence
```

OpenShell:

```bash
skill-native run-openshell path/to/run.yaml \
  --evidence-dir .skill-native/evidence \
  -- your-command --arg value
```

Cloudflare bridge:

```bash
skill-native run-cloudflare path/to/run.yaml \
  --bridge-url "$BRIDGE_URL" \
  --evidence-dir .skill-native/evidence \
  -- your-command --arg value
```

Only persisted evidence from an actually executed environment may establish its corresponding runtime-verification state.

## 8. Export public JSON Schemas

```bash
skill-native export-harness-schemas /tmp/skill-native-schemas
```

Committed files under [`schemas/`](./schemas) are generated contracts; CI checks schema drift.

## 9. Build compatibility reports

```bash
skill-native build-report results.jsonl --output report.json
```

Rows are keyed by explicit compatibility dimensions rather than silently mixing different agents, runtimes, providers, or models.

## 10. Run tests

```bash
python -m unittest discover -s tests -v
```

Relevant workflows are under [`.github/workflows/`](./.github/workflows/). A configured workflow, skipped job, or merge event is never equivalent to a successful external verification run.

---

# The core trust model

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

The most important invariants are:

```text
merge state != verification state
configured workflow != executed evidence
signature != correctness
transparency inclusion != runtime verification
fixture success != isolated-runtime success
emulator verification != physical-device verification
correctness cannot compensate for High/Critical security failure
missing mandatory evidence fails closed
```

---

# Current integration snapshot — 2026-08-14

The mutable source of truth is [`docs/INTEGRATION_STATE.md`](./docs/INTEGRATION_STATE.md).

| Area | State | Trace |
|---|---|---|
| Immutable ingestion / provenance / supply-chain evidence | merged | historical runtime/evidence bootstrap and current `main` |
| Cross-domain Harness Kernel | merged | PR #17 |
| Coding Agent Harness | merged/hardened | PR #19, #26 |
| Run Artifact / Evidence Graph / replay / scorecard | merged | PR #22 |
| DSSE Ed25519 + transparency publication | merged | PR #24 |
| Playwright Browser Harness | merged/hardened | PR #29, #32 |
| Android bounded contract | merged | PR #35 |
| Android canonical compile boundary | merged | PR #37; compile CI verified before merge |
| Android `HarnessManifest` / `android.adb.v1` adapter / trusted ADB runner / evidence / emulator | pending | Issue #28 |
| OpenShell/Cloudflare live evidence and detector-quality gates | externally pending where evidence is absent | Issues #1/#2/#3/#5 |

Verification vocabulary remains intentionally separated:

```text
implemented
CI-verified
scripted-fixture-verified
deterministic-local-integration-verified
emulator-integration-verified
physical-device-verified
runtime-isolated-verified
production/credentialed-verified
```

A weaker state must never be renamed into a stronger one.

---

# Repository topology → State Machine ownership

```text
Skill.md-native/
├── AGENTS.md
│   └── Agent policy, trust invariants, handoff and delivery rules
├── README.md
│   └── product purpose, usage, topology, state flow, complete index
├── docs/
│   ├── README.md              documentation entrypoint
│   ├── INTEGRATION_STATE.md   mutable evidence-state ledger
│   ├── STATE_MACHINES.md      detailed state transitions
│   ├── STACKED_DELIVERY.md    Stack PR / parent / traceability rules
│   ├── ARCHITECTURE.md        system architecture
│   ├── HARNESS_KERNEL.md      compiler/kernel contract
│   ├── CODING_AGENT_HARNESS.md
│   ├── RUN_ARTIFACTS.md
│   ├── ATTESTATIONS.md
│   └── EVALUATION_CONTRACT.md
├── src/skill_native/
│   ├── registries.py / github_ingest.py / provenance.py / supply_chain.py
│   │   └── discovery → immutable artifact identity
│   ├── models.py / harness_contract.py
│   │   └── untyped input → strict contract
│   ├── harness_adapters.py / *_contract.py / *_compile.py
│   │   └── domain contract → trusted command/stdin plan
│   ├── harness_kernel*.py / harness_verifiers.py
│   │   └── compile → capability/policy/budget/evidence checks → verdict
│   ├── coding_contract.py / coding_agent.py
│   │   └── child coding task → trusted CodingAgentReceipt
│   ├── browser_contract.py / browser_adapter.py / browser_runner.py
│   │   └── deterministic Browser plan → trusted BrowserReceipt/artifacts
│   ├── android_contract.py / android_compile.py
│   │   └── typed Android plan → canonical stdin-bound runner config
│   ├── runtime.py / openshell.py / cloudflare_runtime.py
│   │   └── prepare → execute → collect → destroy
│   ├── gateway.py / providers.py / provider_metadata.py / policy.py
│   │   └── inference request → governed provider receipt
│   ├── evidence.py / security.py / adversarial.py / security_benchmark.py
│   │   └── observation → evidence IDs → findings → security gate
│   ├── run_artifact*.py / run_artifacts.py
│   │   └── authority + plan + evidence + verdict → graph/replay/trace/scorecard
│   ├── attestation*.py / attestations.py / transparency_log.py
│   │   └── valid bundle → DSSE/policy/publication receipt
│   └── compatibility.py / scoring.py / reporting.py
│       └── explicit cells → uncertainty-aware ranking
├── schemas/
│   └── generated machine-readable public contracts; CI drift-checked
├── examples/
│   ├── harnesses/            executable deterministic domain examples
│   ├── run-artifacts/        authority/plan/evidence/verdict fixtures
│   └── attestations/         signing/trust-policy examples
├── tests/
│   └── success, failure, tamper, continuity, replay and compatibility proofs
├── cloudflare/
│   ├── worker/               Sandbox bridge
│   └── dynamic-worker/       isolated Code Mode bridge
└── .github/workflows/
    └── unit, integration, schema and external evidence gates
```

## Directory ownership table

| Directory / module group | Owns this transition | Primary output |
|---|---|---|
| ingestion / provenance | mutable discovery → immutable pinned artifact | provenance digest, materialized package, supply-chain evidence |
| `harness_contract.py` | raw manifest → strict contract | `HarnessManifest` |
| adapters / domain contracts | domain intent → trusted executable plan | command/stdin config, domain digests |
| Harness Kernel | manifest + run + runtime → verified run | `HarnessPlan`, `EvidenceBundle`, `HarnessVerdict` |
| domain runners | untrusted execution target → trusted receipt | Coding/Browser/future Android receipts |
| runtime adapters | lifecycle state → captured raw evidence | process/network/filesystem/runtime metadata |
| evidence/security | observations → normalized evidence/security state | evidence IDs, findings, security gate |
| Run Artifact modules | authoritative run inputs → lineage artifact | graph, replay, trace, scorecard, bundle |
| attestation/transparency | valid bundle → policy-verified publication | DSSE envelope, verification receipt, inclusion receipt |
| compatibility/scoring/reporting | explicit run cells → comparison | uncertainty-aware report/ranking |
| schemas/tests/workflows | source contract → executable regression evidence | schemas, tests, CI records |

---

# State Machine index

Detailed transition semantics are in [`docs/STATE_MACHINES.md`](./docs/STATE_MACHINES.md).

## A. Immutable ingestion

```text
DISCOVERED
→ RESOLVING
→ PINNED
→ MATERIALIZING
→ INSPECTED
→ PROVENANCE_READY

invalid / ambiguous / unreproducible identity
→ REJECTED
```

## B. Harness compilation

```text
MANIFEST_LOADED
→ CONTRACT_VALIDATED
→ ADAPTER_RESOLVED
→ CAPABILITY_MATCHED
→ POLICY_MATCHED
→ BUDGET_MATCHED
→ PLAN_COMPILED
→ PLAN_DIGEST_VALIDATED

unsupported / ambiguous / weaker-than-required input
→ REJECTED
```

## C. Domain/runtime execution

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

Runtime owns lifecycle/raw collection. The domain runner owns its trusted receipt. The adapter owns domain normalization. The Kernel owns cross-artifact continuity and the final verdict.

## D. Verdict construction

```text
IDENTITY_CONTINUITY
→ COMMAND_INPUT_CONTINUITY
→ REQUIRED_EVIDENCE
→ DOMAIN_VERIFICATION
→ MANIFEST_VERIFICATION
→ SECURITY_GATE
→ VERDICT_PERSISTED
```

## E. Run Artifact derivation

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

## F. Attestation / publication

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

Signing/publication can authenticate lineage; it cannot upgrade a failed run.

## G. Compatibility / ranking

```text
CELL_KEYED
→ SAMPLE_ACCUMULATED
→ SECURITY_ELIGIBLE
→ COVERAGE_EVALUATED
→ RANKED

missing evidence / failed verdict / failed security gate
→ INELIGIBLE
```

Minimum cell identity:

```text
Skill artifact digest
× Agent harness/version
× Runtime/version
× Model/provider
```

## H. GitHub delivery

```text
ISSUE_SCOPED
→ TERMINAL_BRANCH
→ DRAFT_PR
→ CHECKS_PENDING
→ REVIEWABLE
→ READY
→ MERGED
→ STATE_LEDGER_UPDATED

external runner/account unavailable
→ BLOCKED_INFRASTRUCTURE
```

---

# End-to-end trust-boundary data flow

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
HarnessPlan ───────────────────────────────┐
        │                                 │
        ▼                                 │
UNTRUSTED EXECUTION TARGET                │
Skill / child coding agent / page / app   │
        │                                 │
        ▼                                 │
TRUSTED RUNTIME + DOMAIN COLLECTORS       │
raw evidence → validated domain receipt   │
        │                                 │
        ▼                                 │
EvidenceBundle ◄──────────────────────────┘
        │
        ▼
TRUSTED VERIFIERS
identity + input + mandatory evidence + domain checks + security gate
        │
        ▼
HarnessVerdict
        │
        ▼
VERIFIER-OWNED RUN ARTIFACT DERIVATION
EvidenceGraph + ReplayManifest + LogicalTrace + OutcomeScorecard
        │
        ▼
RunArtifactBundle
        │
        ▼
SIGNING / PUBLICATION CONTROL PLANE
DSSE signature + identity policy + transparency inclusion
        │
        ▼
CROSS-RUN ANALYTICS
compatibility cells + uncertainty + reports/ranking
```

---

# Domain index

## Coding Agent

**Status:** merged.

Primary implementation:

```text
src/skill_native/coding_contract.py
src/skill_native/coding_agent.py
src/skill_native/harness_adapters.py
```

Primary documentation: [`docs/CODING_AGENT_HARNESS.md`](./docs/CODING_AGENT_HARNESS.md).

The trusted wrapper captures structured child-agent execution evidence, workspace changes, independent tests, bounded output, and receipt continuity. Task success does not bypass the security gate.

## Browser / Playwright

**Status:** merged and hardened via PR #29 + #32.

Primary implementation:

```text
src/skill_native/browser_contract.py
src/skill_native/browser_adapter.py
src/skill_native/browser_runner.py
examples/harnesses/browser/
```

Evidence includes bounded DOM/ARIA/network/console/screenshot/download/final-assertion artifacts. The deterministic local Browser fixture does **not** imply public-site, credentialed-site, hosted-browser, CAPTCHA/stealth, or isolated-runtime verification.

## Android / ADB

**Status:** contract + compile boundary merged; execution/evidence still pending.

Main currently contains:

```text
AndroidContract
→ contract_digest
→ action_plan_digest
→ AndroidRunnerConfig
→ config_digest
→ canonical stdin JSON
→ SHA-256(stdin bytes)
→ fixed runner argv: skill-native-android-runner --config-stdin
```

Primary implementation:

```text
src/skill_native/android_contract.py
src/skill_native/android_compile.py
```

The contract exposes typed bounded primitives for activity start, key events, tap/swipe, bounded waits, package/activity/UI-state checks, UI hierarchy capture, and screenshots. It intentionally does not expose arbitrary shell or a free-form ADB command field.

Still pending under Issue #28:

```text
HarnessManifest.android + android.adb.v1 adapter registration
→ trusted ADB binary/device boundary
→ bounded subprocess lifecycle
→ AndroidReceipt
→ artifact + EvidenceBundle integration
→ scripted fake-ADB verification
→ fixed emulator integration
→ optional Appium/Maestro/Mobly layers
```

## Runtime index

```text
FakeRuntime       deterministic contract/evidence regression only
OpenShellRuntime  external isolated-runtime path; live claims require live evidence
CloudflareRuntime bridge to Cloudflare worker/sandbox integration
Browser fixture   deterministic local browser integration, not VM isolation
```

Runtime definitions and controllers live under `src/skill_native/runtime.py`, `openshell.py`, `cloudflare_runtime.py`, and `cloudflare/`.

---

# Evidence, security, replay, and ranking index

## EvidenceBundle and security

See:

- [`docs/EVALUATION_CONTRACT.md`](./docs/EVALUATION_CONTRACT.md)
- [`src/skill_native/evidence.py`](./src/skill_native/evidence.py)
- [`src/skill_native/security.py`](./src/skill_native/security.py)
- [`src/skill_native/adversarial.py`](./src/skill_native/adversarial.py)

High/Critical findings are non-compensable. Missing mandatory evidence fails closed.

## Run Artifact Bundle

See [`docs/RUN_ARTIFACTS.md`](./docs/RUN_ARTIFACTS.md).

```text
EvaluatorAuthority
+ HarnessPlan
+ EvidenceBundle
+ HarnessVerdict
→ EvidenceGraph
→ ReplayManifest
→ ConfounderSet
→ LogicalTrace
→ OutcomeScorecard
→ RunArtifactBundle
```

Replay readiness is separate from task correctness. Derived logical trace is not presented as live timing evidence.

## Attestation and transparency

See [`docs/ATTESTATIONS.md`](./docs/ATTESTATIONS.md).

```text
RunArtifactBundle
→ canonical statement
→ DSSE PAE
→ Ed25519 signature
→ verifier-owned trust policy
→ publication-boundary re-verification
→ append-only hash/Merkle log
→ inclusion receipt
```

## Compatibility / scoring / reporting

Primary modules:

```text
compatibility.py
scoring.py
reporting.py
```

The system keeps correctness, evidence completeness, security eligibility, replayability, and verification state separate instead of hiding them behind one opaque universal score.

---

# Complete documentation index

| Document | Read it when you need to understand... |
|---|---|
| [`AGENTS.md`](./AGENTS.md) | Agent operating contract, repository invariants, current handoff requirements |
| [`README.md`](./README.md) | Product purpose, usage, system map, State Machines, data flow, Domain and delivery index |
| [`docs/README.md`](./docs/README.md) | Documentation navigation order |
| [`docs/INTEGRATION_STATE.md`](./docs/INTEGRATION_STATE.md) | Exact mutable merged/open/planned/blocked verification state |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Overall system architecture and trust boundaries |
| [`docs/HARNESS_KERNEL.md`](./docs/HARNESS_KERNEL.md) | Harness manifest/compiler/kernel/verifier semantics |
| [`docs/STATE_MACHINES.md`](./docs/STATE_MACHINES.md) | Detailed transitions, owners, inputs/outputs, fail-closed states |
| [`docs/STACKED_DELIVERY.md`](./docs/STACKED_DELIVERY.md) | Terminal Stack PR decomposition, parent lineage, merge/rebuild rules |
| [`docs/CODING_AGENT_HARNESS.md`](./docs/CODING_AGENT_HARNESS.md) | Coding-agent trusted wrapper and evidence contract |
| [`docs/RUN_ARTIFACTS.md`](./docs/RUN_ARTIFACTS.md) | EvidenceGraph, replay, trace, confounders, scorecard and persistence |
| [`docs/ATTESTATIONS.md`](./docs/ATTESTATIONS.md) | DSSE signing, identity policy and transparency publication |
| [`docs/EVALUATION_CONTRACT.md`](./docs/EVALUATION_CONTRACT.md) | Evaluation/evidence semantics and result interpretation |
| [`schemas/`](./schemas/) | Public machine-readable contracts generated from source models |
| [`examples/`](./examples/) | Executable deterministic fixtures and usage examples |
| [`tests/`](./tests/) | Executable success/failure/tamper/continuity specifications |
| [`.github/workflows/`](./.github/workflows/) | Unit/integration/schema/external evidence delivery gates |

---

# Source module index

| Concern | Primary modules |
|---|---|
| Registry ingestion | `registries.py`, `github_ingest.py` |
| Provenance / supply chain | `provenance.py`, `supply_chain.py`, `run_factory.py` |
| Core models | `models.py` |
| Harness manifest / compiler | `harness_contract.py`, `harness_kernel.py`, `harness_kernel_impl.py` |
| Verifiers | `harness_verifiers.py` |
| Domain adapters | `harness_adapters.py`, domain `*_adapter.py` modules |
| Coding domain | `coding_contract.py`, `coding_agent.py` |
| Browser domain | `browser_contract.py`, `browser_adapter.py`, `browser_runner.py` |
| Android domain | `android_contract.py`, `android_compile.py` |
| Runtime lifecycle | `runtime.py`, `openshell.py`, `cloudflare_runtime.py` |
| Provider gateway | `gateway.py`, `providers.py`, `provider_metadata.py`, `policy.py` |
| Evidence | `evidence.py` |
| Security | `security.py`, `adversarial.py`, `security_benchmark.py` |
| Compatibility / scoring | `compatibility.py`, `scoring.py` |
| Reports | `reporting.py` |
| Run Artifact derivation | `run_artifact_*.py`, `run_artifacts.py` |
| Attestation | `attestation_*.py`, `attestations.py`, `attestation_cli.py` |
| Transparency | `transparency_log.py` |
| CLI | `cli.py` |

---

# Git Town and Stack PR traceability

## Git Town status

No repository-level `.git-branches.toml`, `git-town.toml`, `.git-town.toml`, or committed Git Town path is currently detected. The repository must therefore **not** be described as actively Git Town-managed.

The delivery model is deliberately Git Town-compatible: every terminal slice records an explicit parent and verification boundary so it can map one-to-one to Git Town stack branches if Git Town is introduced later.

## Merged delivery chain

```text
#7   runtime/evidence bootstrap
→ #17 Cross-domain Harness Kernel
→ #19 Coding Agent Harness
→ #22 Run Artifact Bundle
→ #26 Coding stdin hardening
→ #24 attestation/transparency
→ #29 Browser Harness
→ #32 Browser hardening
→ #35 Android bounded contract
→ #37 Android compile boundary
```

## Android-28 terminal stack

```text
main
└── A1c HarnessManifest + android.adb.v1 compile wiring      NEXT
    └── A2a ADB binary identity / device selection / typed argv
        └── A2b bounded subprocess lifecycle
            └── A3 AndroidReceipt + artifact/EvidenceBundle continuity
                └── A4 scripted fake-ADB verification
                    └── A5 fixed emulator integration
                        ├── A6 Appium / Maestro
                        └── A7 Mobly / multi-device
```

| Slice | State | Establishes | Must not claim |
|---|---|---|---|
| A1 / #35 | merged | typed bounded Android contract | ADB execution |
| A1b / #37 | merged | canonical stdin/config digest continuity | ADB execution/evidence |
| A1c | next | `HarnessManifest` + `android.adb.v1` compile wiring | real device execution |
| A2a | planned | ADB binary identity, exact device selection, typed argv | subprocess lifecycle completeness |
| A2b | planned | bounded process/output/timeout cleanup boundary | Android evidence completeness |
| A3 | planned | receipt/artifact/EvidenceBundle continuity | emulator verification |
| A4 | planned | scripted fake-ADB verification | real emulator/device verification |
| A5 | planned | emulator verification after executed persisted CI | physical device verification |
| A6 | planned | Appium/Maestro integration | multi-device lab verification |
| A7 | planned | Mobly/multi-device orchestration | production device fleet verification |

Historical Android PRs #31/#34/#33 are stale-ancestry evidence and must not be reused as active stack parents.

Every terminal PR should record:

```text
Stack-ID
Parent-Branch
Parent-Head-At-Open
Slice
Depends-On
Establishes-State
Does-Not-Claim
```

After squash-merging a parent, rebuild or retarget children to the new `main` and obtain fresh CI. Do not infer correctness from an old merge-ref.

See [`docs/STACKED_DELIVERY.md`](./docs/STACKED_DELIVERY.md) for the complete delivery contract.

---

# How to add a new execution domain

A new Domain should normally be introduced as small trust-boundary slices rather than one large implementation PR:

```text
1. typed contract + deterministic digests
2. compile boundary / canonical input transport
3. HarnessManifest + DomainAdapter registration
4. trusted runner process/protocol boundary
5. trusted receipt + artifact integrity
6. EvidenceBundle + deterministic verifier integration
7. scripted deterministic fixtures
8. real environment integration
9. optional higher-level semantic agent layer
```

The lower layer must be independently testable before the next layer is allowed to claim a stronger verification state.

---

# How to interpret results

A successful command only proves the state explicitly supported by its evidence.

Examples:

```text
FakeRuntime pass
≠ live sandbox pass

local Chromium fixture pass
≠ credentialed production website pass

Android contract tests pass
≠ ADB runner pass

emulator pass
≠ physical device pass

DSSE signature verifies
≠ task correctness

transparency inclusion verifies
≠ safe execution
```

When reporting a result, always include the verification state, immutable identities, evidence/verdict digests, and any known non-claims.

---

# Contribution / Agent handoff rule

Before starting implementation:

```text
AGENTS.md
→ README.md
→ docs/INTEGRATION_STATE.md
→ relevant domain/trust document
→ docs/STATE_MACHINES.md
→ docs/STACKED_DELIVERY.md
→ canonical Issue
→ current PR/workflow evidence
```

After every merge or verification-state change, update the state ledger and any README/stack entry whose status changed.

Source-of-truth order:

```text
persisted runtime/integration evidence
> executed GitHub Actions
> merged commits
> open PR head/checks
> canonical Issues
> documentation
> conversation/Agent memory
```

Do not promote a result beyond the strongest evidence actually captured.
