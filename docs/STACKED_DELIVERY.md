# Stacked Delivery and Traceability Ledger

This document defines how terminal implementation slices are decomposed, reviewed, merged, and traced.

## Git Town detection status

At the 2026-08-12 snapshot, the repository tree does **not** contain any of these repository-level configuration files:

```text
.git-branches.toml
git-town.toml
.git-town.toml
```

No path containing `git-town` was detected on `main`. Therefore:

- do not claim that the repository is currently managed by Git Town;
- do not infer parent branches from branch names alone;
- record every stack parent explicitly in this ledger and in PR bodies;
- treat any Git Town configuration local to a developer machine as non-portable until committed intentionally.

If Git Town is adopted later, add its repository configuration in a dedicated infrastructure PR. Do not mix tool adoption with a Browser, Android, runtime, or scoring feature PR.

## Traceability vocabulary

```text
actual
  Branch or PR exists on GitHub and its exact head/base can be inspected.

conceptual-slice
  Independently reviewable responsibility inside an existing larger PR; no separate branch/PR is claimed.

planned
  Proposed child branch/PR; it does not exist yet.

merged
  PR merged; the merge commit is part of main history.

blocked-infrastructure
  External workflow/account/runner state prevented execution.
```

## Current actual branch graph

```text
main@032a933d15f3770b93be24aa9abfed98b9a2a898
├── agent/27-browser-playwright-harness@c58cbef0ac5f21356ccf454cd1bf1c6396e0049d
│   └── PR #29 → Issue #27
│       state: open / Draft / mergeable
│       workflows: action_required at snapshot
└── agent/docs-integration-state-machine-index
    └── PR #30
        state: open / Draft
        scope: documentation-only state, data-flow, and Stack index
```

These are independent `main`-based branches, not a parent/child stack. PR #30 must not be retargeted onto PR #29 because its purpose is to describe both merged `main` and open work without depending on the Browser implementation branch.

## Merged implementation chain

The major merged dependency chain is:

```text
PR #7  runtime evidence lab bootstrap
  ↓
PR #17 cross-domain Harness Kernel
  ↓
PR #19 Coding Agent Harness
  ↓
PR #22 evaluator-authorized Run Artifact Bundle
  ↓
PR #26 Coding stdin timeout hardening
  ↓
PR #24 signed attestations and local transparency publication
  ↓
main@032a933d15f3770b93be24aa9abfed98b9a2a898
```

This chain is historical dependency context, not an active branch stack. The old remote branches still exist, but their PRs are merged.

## PR #29 conceptual atomic slices

PR #29 currently combines the following terminal slices. They are indexed for review and future maintenance, but no separate PR is claimed.

| Slice | Files or area | State transition owned | Independent review question |
|---|---|---|---|
| B1 contract | `browser_contract.py`, Harness contract/schema changes | Browser manifest → validated deterministic action plan | Can untrusted manifest input escape the bounded grammar or weaken budgets/origin policy? |
| B2 adapter | `browser_adapter.py`, Harness adapter registration | Harness plan/raw evidence → normalized Browser evidence | Does the adapter preserve plan, driver, receipt, and artifact continuity? |
| B3 runner | `browser_runner.py`, `browser_entrypoint.py` | action plan → BrowserReceipt | Does trusted stdout ownership prevent page/console receipt injection and fail closed on side effects? |
| B4 artifact boundary | Browser artifact descriptors and validation | browser output → content-addressed DOM/ARIA/screenshot/download evidence | Are traversal, symlink, special-file, size, and digest substitutions rejected? |
| B5 fixture runtime | `browser_fixture_runtime.py`, loopback fixture | local process → explicitly non-isolated evidence | Is it impossible to mislabel the local fixture as OpenShell/Cloudflare or production verification? |
| B6 graph/schema integration | `models.py`, `run_artifact_graph.py`, schemas | Browser evidence → Run Artifact lineage | Can every Browser claim be traced without copying sensitive raw content? |
| B7 tests | `tests/test_browser_harness.py` | expected transition → executable proof | Are success, origin denial, failed assertion, side effects, forged output, and artifact tampering covered? |
| B8 workflow automation | `schema-sync-pr.yml` | schema change → regenerated schema commit/check | Does automation preserve branch authorship/trust and actually execute under repository policy? |

Before PR #29 is merged, the PR body and Issue #27 should link each slice to observed checks. `action_required` is not green CI.

## PR #30 documentation slice

PR #30 is a standalone documentation slice based on `main`.

```text
State transition owned:
repository knowledge scattered across README, Issues, branches, and PRs
→ indexed Agent-readable integration state and delivery graph
```

It changes no runtime, public schema, evaluator, security gate, or verification code. Therefore its legitimate state transition is:

```text
traceability documentation absent/incomplete
→ traceability documentation implemented
```

It must not be used to upgrade Browser, Android, OpenShell, Cloudflare, or ranking evidence states.

## Planned Android Git Town-compatible stack

Issue #28 should be implemented as a bottom-up stack. The names below are **planned**, not existing branches.

```text
main
└── agent/28-android-contract
    └── agent/28-android-runner
        └── agent/28-android-evidence
            └── agent/28-android-scripted-fixtures
                └── agent/28-android-emulator-ci
```

### A1 — `agent/28-android-contract`

Base: `main`.

Scope:

- strict `AndroidContract` and bounded action grammar;
- `android.adb.v1` registration and cross-field manifest validation;
- device constraint, budget, assertion, and ADB identity fields;
- compile-only plan digest tests;
- generated schema changes.

Must not include:

- subprocess execution;
- real ADB calls;
- emulator workflow;
- artifact files.

Independent acceptance:

```text
existing Coding/Browser/command manifests remain valid
arbitrary shell/meta-character tokens are rejected
plan digest changes for every Android trust input
schema generation is deterministic
```

### A2 — `agent/28-android-runner`

Parent: `agent/28-android-contract`.

Scope:

- trusted runner-owned stdout;
- ADB executable path/version/SHA-256 identity;
- online-device enumeration and exact serial selection;
- constrained process invocations for start/tap/swipe/key/wait/capture;
- self-validating Android receipt;
- timeout and process cleanup.

Must not include:

- Harness EvidenceBundle normalization;
- emulator CI;
- broad artifact persistence beyond minimal receipt fixtures.

Independent acceptance:

```text
ambiguous/offline/unauthorized devices fail closed
untrusted device output cannot inject a top-level receipt
unsafe tokens never cross the ADB argv boundary
receipt detects mutation after JSON round-trip
```

### A3 — `agent/28-android-evidence`

Parent: `agent/28-android-runner`.

Scope:

- content-addressed UIAutomator XML, screenshot, bounded logcat, and device-state descriptors;
- safe artifact root/path/symlink/special-file/budget checks;
- Android EvidenceBundle channels and collector attestation;
- DomainAdapter normalization/domain checks;
- Run Artifact Evidence Graph integration.

Independent acceptance:

```text
missing or modified artifacts fail continuity
failure-path evidence is preserved
scripted fixture state is not promoted to emulator/physical-device state
security gate remains non-compensable
```

### A4 — `agent/28-android-scripted-fixtures`

Parent: `agent/28-android-evidence`.

Scope:

- scripted fake ADB executable;
- deterministic success/failure/device ambiguity/action/assertion/tamper cases;
- executable example and Android architecture document;
- full regression without requiring an Android SDK.

Independent acceptance:

```text
scripted fixture yields a passing verdict only under scripted-fixture state
all negative paths fail closed
no external device/account is required
```

### A5 — `agent/28-android-emulator-ci`

Parent: `agent/28-android-scripted-fixtures`.

Scope:

- fixed API/ABI/profile emulator job;
- target built-in application and deterministic final-state assertions;
- persisted emulator artifacts and exact runtime/device identity;
- Issue/README/Integration State update based on observed workflow evidence.

Independent acceptance:

```text
job actually starts and completes
artifacts are persisted
emulator state is distinct from scripted and physical-device state
no physical-device or production claim is made
```

If hosted Actions remain blocked, A5 may merge only as an implemented workflow with state `blocked-infrastructure`; it cannot establish emulator verification.

## Stack PR contract

Every actual stacked PR must include this header in its description:

```text
Stack-ID: <issue-or-workstream>
Parent-Branch: <exact-parent>
Parent-Head-At-Open: <sha>
Slice: <contract|runner|evidence|fixtures|integration>
Depends-On: <PR number or none>
Establishes-State: <planned|implemented|integration-verified|runtime-verified>
Does-Not-Claim: <explicit non-claims>
```

Every child PR must be reviewable against its parent without requiring uncommitted local files or another sibling branch.

## Merge and retarget protocol

1. Merge from the bottom of the dependency graph upward: parent before child.
2. After a parent merges, retarget or restack the child onto the new parent/main head.
3. Re-run continuity, schemas, and relevant regression after every restack.
4. Update this ledger with the new base/head SHA and PR number.
5. Remove claims that depended on a check that no longer executed after restacking.
6. Do not squash multiple independently security-sensitive slices into one hidden commit after review.

## Atomicity rules

A terminal PR is atomic when:

```text
one trust boundary changes
one state transition becomes executable
its tests fail without that transition
its schemas/docs agree with the code
it can be reverted without corrupting sibling layers
```

Split a PR when it simultaneously changes two or more of:

```text
public contract/schema
trusted runner/process boundary
runtime adapter transport
EvidenceBundle semantics
security evaluator
Run Artifact lineage
external account-backed workflow
ranking policy
```

Exceptions require an explicit explanation in the PR body.

## Ledger schema

Maintain this table in README and this document:

| Stack | Slice | Parent | Branch | Issue | PR | Head SHA | State | Verification | Merge SHA |
|---|---|---|---|---:|---:|---|---|---|---|
| Browser-27 | combined B1–B8 | `main` | `agent/27-browser-playwright-harness` | 27 | 29 | `c58cbef0...` | actual Draft | workflows `action_required`; local evidence recorded in Issue | — |
| Docs-index | integration/state/index | `main` | `agent/docs-integration-state-machine-index` | — | 30 | resolve from PR metadata | actual Draft | documentation metadata review only | — |
| Android-28 | A1 contract | `main` | `agent/28-android-contract` | 28 | — | — | planned | — | — |
| Android-28 | A2 runner | A1 | `agent/28-android-runner` | 28 | — | — | planned | — | — |
| Android-28 | A3 evidence | A2 | `agent/28-android-evidence` | 28 | — | — | planned | — | — |
| Android-28 | A4 scripted fixtures | A3 | `agent/28-android-scripted-fixtures` | 28 | — | — | planned | — | — |
| Android-28 | A5 emulator CI | A4 | `agent/28-android-emulator-ci` | 28 | — | — | planned | — | — |

Use full SHA values in PR bodies and the integration ledger. The abbreviated SHA in this table is display-only. A self-referential documentation PR resolves its exact head from PR metadata rather than embedding a SHA that changes when the ledger is updated.

## Documentation update rule

A merge or evidence-state change is incomplete until these remain consistent:

```text
README.md
AGENTS.md when repository policy changes
docs/INTEGRATION_STATE.md
docs/STATE_MACHINES.md when ownership/transitions change
docs/STACKED_DELIVERY.md
canonical Issue
PR body
schemas and executed checks
```

The index is part of the delivery system, not retrospective prose.