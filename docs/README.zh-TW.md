<!-- i18n-key: DOCS_INDEX; locale: zh-TW; reviewed: 2026-08-16 -->
[English](README.md) · [繁體中文](README.zh-TW.md)

# Skill.md-native 文件

先閱讀 [專案 README](../README.zh-TW.md)。其中說明 Supported entrypoint、成熟度、Evidence boundary、Quick start 與 Non-goals。

## Evidence 與目前狀態

- [Integration state](INTEGRATION_STATE.md) — 目前 Domain／Evidence ledger 與 Supersession map。
- [Executable capability audit](../audit/README.md) — One-command exact-subject evidence packet。
- [2026-08-15 capability audit interpretation](audits/2026-08-15-capability-audit.md) — Baseline findings 與明確 External gaps。
- [2026-08-16 convergence ledger](CONVERGENCE_2026-08-16.md) — Current-main reconstruction、CI economy、Merge admission 與 Supersession contract。
- [Historical stacked delivery](STACKED_DELIVERY.md) — 原始 Branch、PR、Slice 與 Handoff history，保留且不改寫。

## 技術文件

- [Architecture](ARCHITECTURE.md) — System 與 Trust-boundary architecture。
- [State Machines](STATE_MACHINES.md) — Ingestion、Compilation、Runtime、Verdict、Attestation 與 Delivery states。
- [Harness Kernel](HARNESS_KERNEL.md) — Compiler、Capability、Evidence 與 Verifier contracts。
- [Coding Agent Harness](CODING_AGENT_HARNESS.md) — Bounded coding-agent task 與 Receipt model。
- [Android Harness](ANDROID_HARNESS.md) — Contract、ADB primitives、剩餘 Runner／Evidence gates 與 Verification levels。
- [Run Artifacts](RUN_ARTIFACTS.md) — Evidence Graph、Replay、Trace 與 Scorecard。
- [Attestations](ATTESTATIONS.md) — DSSE、Key policy 與 Transparency publication。
- [Evaluation contract](EVALUATION_CONTRACT.md) — Outcome 與 Security evaluation rules。

## 專案與社群文件

- [文件語言政策](I18N.zh-TW.md)
- [Open-source readiness checklist](OPEN_SOURCE_CHECKLIST.zh-TW.md)
- [參與貢獻](../CONTRIBUTING.zh-TW.md)
- [安全政策](../SECURITY.zh-TW.md)
- [支援](../SUPPORT.zh-TW.md)
- [治理](../GOVERNANCE.zh-TW.md)
- [Maintainers](../MAINTAINERS.zh-TW.md)
- [行為準則](../CODE_OF_CONDUCT.zh-TW.md)
- [變更紀錄](../CHANGELOG.zh-TW.md)
- [Release process](../RELEASING.zh-TW.md)

## Source of truth 順序

文件不一致時，依下列順序判定：

```text
persisted exact-subject runtime/integration artifact
> executed workflow 與 raw logs
> merged code、contracts、tests 與 repository policy
> current implementation/status ledger
> architecture 與 runbooks
> README summaries
> Issues、Pull Requests 與 conversational summaries
```

Open Pull Request、Configured workflow、Example、Fixture、Signature 或 Prose statement，都不能單獨提升 `main` 的 Implementation 或 Verification state。
