<!-- i18n-key: DOCS_INDEX; locale: zh-TW; reviewed: 2026-08-15 -->
[English](README.md) · [繁體中文](README.zh-TW.md)

# Skill.md-native 文件

先閱讀 [專案 README](../README.zh-TW.md)。其中說明支援的 Entrypoint、目前成熟度、Evidence boundary、Quick start 與 Non-goals。

## 技術文件

- [Integration state](INTEGRATION_STATE.md) — Exact domain 與 Evidence-state ledger。
- [Architecture](ARCHITECTURE.md) — System 與 Trust-boundary architecture。
- [State Machines](STATE_MACHINES.md) — Ingestion、Compilation、Runtime、Verdict、Attestation 與 Delivery state。
- [Harness Kernel](HARNESS_KERNEL.md) — Compiler、Capability、Evidence 與 Verifier contract。
- [Coding Agent Harness](CODING_AGENT_HARNESS.md) — Bounded coding-agent task 與 Receipt model。
- [Run Artifacts](RUN_ARTIFACTS.md) — Evidence Graph、Replay、Trace 與 Scorecard。
- [Attestations](ATTESTATIONS.md) — DSSE、Key policy 與 Transparency publication。
- [Evaluation contract](EVALUATION_CONTRACT.md) — Outcome 與 Security evaluation rule。
- [Stacked delivery](STACKED_DELIVERY.md) — Branch、PR、Evidence 與 Handoff lineage。

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
已合併 Code 與 Repository policy
> 目前 Machine-readable contracts 與 Tests
> 目前 Implementation/status ledger
> Architecture 與 Runbooks
> README summaries
> Issues、Pull Requests 與 Conversational summaries
```

Open Pull Request、Configured workflow、Example、Fixture、Generated report 或 Signed receipt，都不能單獨提升 `main` 的 Implementation 或 Verification state。
