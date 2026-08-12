# Integration State Ledger

> Canonical handoff snapshot for humans and coding agents. Read this file after [`AGENTS.md`](../AGENTS.md) and [`README.md`](../README.md), before planning or changing an integration.

## Snapshot identity

| Field | Value |
|---|---|
| Repository | `ed3c/Skill.md-native` |
| Snapshot date | 2026-08-12, Asia/Taipei |
| Default branch | `main` |
| Verified `main` head | `032a933d15f3770b93be24aa9abfed98b9a2a898` |
| Head feature | signed Run Artifact attestations and local transparency publication |
| Open feature PR | #29, `agent/27-browser-playwright-harness` |
| Repository-level Git Town config | **not detected** |

This file is a snapshot, not an oracle. Before editing it, re-read GitHub Issues, PR metadata, branch heads, and workflow results. Never copy an old status forward merely because the code still exists.

## Source-of-truth order

When sources disagree, use this order:

1. Persisted runtime or integration evidence linked to immutable artifact/runtime identity.
2. Executed GitHub Actions jobs and their artifacts/logs.
3. Merged code, schemas, tests, and exact commit history.
4. Open PR head plus its executed checks.
5. Canonical Issue checklist.
6. Documentation prose.
7. Agent memory or prior conversation summaries.

An Issue checkbox or PR description is not proof that a job executed. A configured workflow is not a passing workflow. A local fixture is not account-backed runtime verification.

## Delivery history on `main`

| Layer | PR | Result on `main` | Evidence state |
|---|---:|---|---|
| Runtime evidence lab bootstrap | #7 | Ingestion, provenance, OpenShell/Cloudflare contracts, inference broker, security benchmark, compatibility/ranking MVP | implemented; public GitHub ingestion integration-verified; account-backed runtime gates remain open |
| Cross-domain Harness Kernel | #17 | `HarnessManifest`, `HarnessPlan`, `HarnessVerdict`, capability/evidence profiles, fail-closed compiler | implemented and CI-verified |
| Coding Agent Harness | #19 | `coding.agent.v1`, trusted runner, stdin task delivery, workspace/test receipt | implemented; no live model-backed claim |
| Run Artifact Bundle | #22 | evaluator authority, Evidence Graph, Replay Manifest, Logical Trace, evidence-first scorecard | implemented and CI-verified |
| Coding stdin backpressure hotfix | #26 | timeout begins immediately; stdin writer cannot block the trusted wrapper indefinitely | merged security hardening |
| Attestation and transparency | #24 | canonical statement, DSSE Ed25519, verifier policy, hash-chain/Merkle log, inclusion receipt | implemented and CI-verified; local log is not a public witnessed log |

The current `main` chain is therefore:

```text
source/provenance
→ Harness Kernel
→ Coding domain receipt
→ evaluator-authorized Run Artifact Bundle
→ DSSE signature and verifier-owned policy
→ local transparency inclusion receipt
```

## Current open work

### Browser Harness — Issue #27 / Draft PR #29

| Field | State |
|---|---|
| Branch | `agent/27-browser-playwright-harness` |
| Head | `c58cbef0ac5f21356ccf454cd1bf1c6396e0049d` |
| Base | `main@032a933d15f3770b93be24aa9abfed98b9a2a898` |
| PR state | open, Draft, mergeable |
| Scope | `browser.playwright.v1`, deterministic action grammar, origin policy, trusted runner, Browser receipt, content-addressed artifacts, loopback Chromium fixture |
| Workflow state at snapshot | `unit`, `integration`, and `schema-sync-pr` concluded `action_required`; no workflow jobs were returned for the unit run |
| Allowed claim | implementation exists on the PR branch; Issue #27 records deterministic local Browser verification |
| Forbidden claim | merged, GitHub Actions green, public-site verified, credentialed-site verified, hosted-browser verified, or isolated-runtime verified |

Files on PR #29 include Browser contract/runner/adapter/runtime modules, Browser schemas, loopback examples, tests, and schema-sync workflow changes. The PR does not change `README.md`, so this documentation PR can remain independent.

### Android Harness — Issue #28

State: **planned; no implementation PR at this snapshot**.

Required initial adapter: `android.adb.v1` with a constrained ADB grammar, explicit device identity, trusted wrapper-owned stdout, content-addressed UI/device artifacts, receipt validation, scripted fixture evidence, and a separately classified emulator evidence level.

Do not expose arbitrary `adb shell`, install/uninstall, root/remount, bootloader commands, or unrestricted file transfer through the manifest.

## Environment-backed verification gates intentionally still open

| Issue | Implemented portion | Missing evidence required before closing |
|---:|---|---|
| #1 OpenShell | adapter, policy compiler, OCSF/evidence controller, live workflow entrypoint | persisted real OpenShell benign, denied-network, L7, and runtime identity evidence |
| #2 Inference broker | provider routing, budgets, receipt ledger, broker attachment | real OpenShell proof that brokered inference works while raw provider credentials remain unreadable |
| #3 Cloudflare | Python controller, Worker bridge, Dynamic Worker contracts | real account cold/warm execution, denied egress, resource/storage evidence, credential non-exposure |
| #5 adversarial benchmark | executable corpus, evaluator, security gate, hidden variants | detector recall/FPR measured from persisted real OpenShell/Cloudflare runs |

These are not code TODOs only. They are evidence-state gates. Do not close them from mocks, typechecks, merge status, or configured workflows.

## Verification vocabulary

Use exactly these states where applicable:

```text
planned
  Requirement exists; implementation has not landed.

implemented
  Code, schemas, fixtures, and deterministic tests exist.

content-addressed
  Object and nested continuity digests validate.

cryptographically-signed
  An authorized key signed the exact canonical payload.

policy-verified
  Derived key identity and signed claims match verifier-owned policy.

transparency-published
  The policy-verified envelope has an inclusion receipt for a specific log prefix.

integration-verified
  A real external source/service produced persisted evidence.

runtime-verified
  The pinned artifact executed in the declared isolated runtime and satisfied required assertions.

blocked-infrastructure
  Required external account, runner, approval, billing, or service state prevented execution.
```

A state can coexist with another state. For example, a run may be content-addressed and signed but still fail task verification. Signing cannot upgrade a failed verdict.

## Immediate requirements

1. Keep `main` aligned with the exact merged truth above.
2. Resolve PR #29's `action_required` workflow state before claiming hosted CI.
3. Merge Browser only after its PR description, Issue #27, schemas, tests, and observed workflow evidence agree.
4. Implement Android through atomic, independently reviewable stack slices described in [`STACKED_DELIVERY.md`](./STACKED_DELIVERY.md).
5. Preserve the same authority → evidence → verdict → Run Artifact → attestation chain for every new domain.
6. Persist external runtime evidence before upgrading Issues #1, #2, #3, or #5.
7. Update this ledger whenever a PR merges, a branch is retargeted, or a verification state changes.

## Agent handoff checklist

Before coding:

```text
[ ] Read AGENTS.md.
[ ] Read README.md directory/state-machine map.
[ ] Read this ledger.
[ ] Read the relevant domain/trust document.
[ ] Read the canonical Issue and current PR, if any.
[ ] Confirm the exact base/head SHA and workflow state.
[ ] Identify which verification state the change may legitimately establish.
```

Before publishing:

```text
[ ] Keep the PR atomic and independently testable.
[ ] Update schemas and schema-drift checks when contracts change.
[ ] Add failure-path and tamper regressions.
[ ] Update the Issue checklist from observed evidence.
[ ] Update README stack/index entries.
[ ] Update this ledger with PR/branch/head/workflow evidence.
[ ] State non-claims explicitly.
```

## Traceability key

Every integration entry should be reconstructable from:

```text
Issue
→ branch and parent branch
→ PR and exact head SHA
→ changed directories/files
→ executed checks and artifacts
→ merge commit
→ verification-state transition
→ documentation and schema version
```

When any link is absent, record it as absent rather than inferring it.