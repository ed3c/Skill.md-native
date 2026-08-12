# Documentation Index

Use this page to choose the smallest authoritative document for the task. Do not read one domain document and infer repository-wide state from it.

## Mandatory Agent read order

1. [`../AGENTS.md`](../AGENTS.md) — repository policy, trust model, evidence rules, and working constraints.
2. [`../README.md`](../README.md) — current topology, state-machine summary, data flow, delivery and traceability index.
3. [`INTEGRATION_STATE.md`](./INTEGRATION_STATE.md) — exact merged/open/planned/blocked snapshot.
4. The relevant architecture/domain document below.
5. [`STACKED_DELIVERY.md`](./STACKED_DELIVERY.md) before creating branches or PRs.

## Core architecture

| Document | Authority |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | overall product architecture and trust boundaries |
| [`EVALUATION_CONTRACT.md`](./EVALUATION_CONTRACT.md) | evaluation/evidence semantics |
| [`HARNESS_KERNEL.md`](./HARNESS_KERNEL.md) | manifest, plan, runtime capability/evidence, verification contracts |
| [`STATE_MACHINES.md`](./STATE_MACHINES.md) | directory ownership, transitions, and end-to-end data flow |

## Domain execution

| Document | State |
|---|---|
| [`CODING_AGENT_HARNESS.md`](./CODING_AGENT_HARNESS.md) | merged implementation for `coding.agent.v1` |
| Browser documentation | currently lives on Draft PR #29 branch; not merged on the snapshot main |
| Android documentation | planned by Issue #28; no implementation document on main yet |

## Post-run trust and publication

| Document | Authority |
|---|---|
| [`RUN_ARTIFACTS.md`](./RUN_ARTIFACTS.md) | evaluator authority, Evidence Graph, Replay Manifest, Logical Trace, scorecard, bundle |
| [`ATTESTATIONS.md`](./ATTESTATIONS.md) | canonical statement, DSSE Ed25519, verifier policy, local transparency log and receipts |

## Current delivery state

| Document | Use |
|---|---|
| [`INTEGRATION_STATE.md`](./INTEGRATION_STATE.md) | merged/open/planned/blocked ledger and immediate requirements |
| [`STACKED_DELIVERY.md`](./STACKED_DELIVERY.md) | branch parentage, Stack PR slices, Git Town detection, merge/retarget protocol |

## Evidence rule

Documentation records what was observed; it does not create evidence. When prose conflicts with executed workflow artifacts, persisted runtime evidence, or immutable code history, update the prose rather than weakening the evidence standard.