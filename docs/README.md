<!-- i18n-key: DOCS_INDEX; locale: en; reviewed: 2026-08-16 -->
[English](README.md) · [繁體中文](README.zh-TW.md)

# Skill.md-native documentation

Start with the [project README](../README.md). It explains the supported entrypoints, maturity, evidence boundaries, quick start, and non-goals.

## Evidence and current state

- [Integration state](INTEGRATION_STATE.md) — Current domain/evidence ledger and supersession map.
- [Executable capability audit](../audit/README.md) — One-command exact-subject evidence packet.
- [2026-08-15 capability audit interpretation](audits/2026-08-15-capability-audit.md) — Baseline findings and explicit external gaps.
- [2026-08-16 convergence ledger](CONVERGENCE_2026-08-16.md) — Current-main reconstruction, CI economy, merge admission, and supersession contract.
- [Historical stacked delivery](STACKED_DELIVERY.md) — Original branch, PR, slice, and handoff history retained without rewriting.

## Technical documentation

- [Architecture](ARCHITECTURE.md) — System and trust-boundary architecture.
- [State Machines](STATE_MACHINES.md) — Ingestion, compilation, runtime, verdict, attestation, and delivery states.
- [Harness Kernel](HARNESS_KERNEL.md) — Compiler, capability, evidence, and verifier contracts.
- [Coding Agent Harness](CODING_AGENT_HARNESS.md) — Bounded coding-agent task and receipt model.
- [Android Harness](ANDROID_HARNESS.md) — Contract, ADB primitives, remaining runner/evidence gates, and verification levels.
- [Run Artifacts](RUN_ARTIFACTS.md) — Evidence Graph, replay, trace, and scorecard.
- [Attestations](ATTESTATIONS.md) — DSSE, key policy, and transparency publication.
- [Evaluation contract](EVALUATION_CONTRACT.md) — Outcome and security evaluation rules.

## Project and community documentation

- [Documentation language policy](I18N.md)
- [Open-source readiness checklist](OPEN_SOURCE_CHECKLIST.md)
- [Contributing](../CONTRIBUTING.md)
- [Security](../SECURITY.md)
- [Support](../SUPPORT.md)
- [Governance](../GOVERNANCE.md)
- [Maintainers](../MAINTAINERS.md)
- [Code of Conduct](../CODE_OF_CONDUCT.md)
- [Changelog](../CHANGELOG.md)
- [Release process](../RELEASING.md)

## Source-of-truth order

When documents disagree, use this order:

```text
persisted exact-subject runtime/integration artifact
> executed workflow and raw logs
> merged code, contracts, tests, and repository policy
> current implementation/status ledger
> architecture and runbooks
> README summaries
> Issues, Pull Requests, and conversational summaries
```

An open Pull Request, configured workflow, example, fixture, signature, or prose statement cannot upgrade the implementation or verification state of `main` by itself.
