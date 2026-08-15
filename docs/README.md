<!-- i18n-key: DOCS_INDEX; locale: en; reviewed: 2026-08-15 -->
[English](README.md) · [繁體中文](README.zh-TW.md)

# Skill.md-native documentation

Start with the [project README](../README.md). It explains the supported entrypoints, current maturity, evidence boundaries, quick start, and non-goals.

## Technical documentation

- [Integration state](INTEGRATION_STATE.md) — Exact domain and evidence-state ledger.
- [Architecture](ARCHITECTURE.md) — System and trust-boundary architecture.
- [State Machines](STATE_MACHINES.md) — Ingestion, compilation, runtime, verdict, attestation, and delivery states.
- [Harness Kernel](HARNESS_KERNEL.md) — Compiler, capability, evidence, and verifier contracts.
- [Coding Agent Harness](CODING_AGENT_HARNESS.md) — Bounded coding-agent task and receipt model.
- [Run Artifacts](RUN_ARTIFACTS.md) — Evidence Graph, replay, trace, and scorecard.
- [Attestations](ATTESTATIONS.md) — DSSE, key policy, and transparency publication.
- [Evaluation contract](EVALUATION_CONTRACT.md) — Outcome and security evaluation rules.
- [Stacked delivery](STACKED_DELIVERY.md) — Branch, PR, evidence, and handoff lineage.

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
merged code and repository policy
> current machine-readable contracts and tests
> current implementation/status ledger
> architecture and runbooks
> README summaries
> Issues, Pull Requests, and conversational summaries
```

An open Pull Request, configured workflow, example, fixture, generated report, or signed receipt cannot upgrade the implementation or verification state of `main` by itself.
