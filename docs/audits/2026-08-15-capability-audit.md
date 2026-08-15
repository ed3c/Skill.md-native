# Skill.md-native capability audit baseline — 2026-08-15

## Executive verdict

`Skill.md-native` 不是只有 README 與介面骨架。基準 `main` 已具有可執行的 cross-domain Harness Kernel、Coding 與 Browser contracts、Android contract/compile primitives、EvidenceBundle／HarnessVerdict persistence、Run Artifact graph、security evaluator、provider routing contracts、local DSSE signing、verifier policy 與 local transparency log。

但較強的產品命題——「任何使用者的 Agent 開箱即用，能在真實 runtime 得到可驗證結果」——只完成了一部分。

基準 subject：

```text
repository: ed3c/Skill.md-native
main commit: e4eacef4c84b2833b62aa2f1842b3f885656fd1f
tree: 409f0eae610a92b422b4cd446e32f690274eb447
baseline unit run: 31802810863
baseline Python job: 94774550882
```

基準分類：

```text
core deterministic contracts/pipelines     IMPLEMENTED + HOST-EXECUTED
Browser contract                            IMPLEMENTED
Browser real Chromium in baseline unit      NOT_EXERCISED (4 tests skipped)
Android contract/compile                    IMPLEMENTED + HOST-EXECUTED
Android trusted ADB/emulator/device          NOT_IMPLEMENTED / NOT_EXERCISED
public GitHub immutable ingestion           CONFIGURED; Issue #42 executes it
hardened generic container                  added by Issue #42 runtime probe
NVIDIA OpenShell live runtime               NOT_EXERCISED
Cloudflare account-backed runtime           NOT_EXERCISED
provider-backed inference isolation         NOT_EXERCISED
multi-cell live compatibility/ranking       NOT_EXERCISED
local signature/transparency mechanism      IMPLEMENTED + HOST-EXECUTED
GitHub OIDC/keyless attestation             NOT PROVEN BY CURRENT PATH
public witnessed transparency               NOT_IMPLEMENTED
production readiness                        NOT PROVEN
```

這個 repository 可以合理聲明「已實作一套實質可執行的驗證框架」。目前不能合理聲明 universal compatibility、production verification、OpenShell／Cloudflare live runtime、provider credential isolation、Android device runtime 或統計充分的 ranking。

Issue #42 新增的 GitHub Actions artifact 是本輪 executable audit 的 authority；本文件只是 baseline 與解讀規則，不硬寫會自我變動的 feature-branch head。

---

## Original product question

目標命題：

> Any user's Agent can use this repository out of the box and obtain a verifiable output result.

它至少需要同時滿足：

1. fresh Agent 找得到 canonical entrypoint；
2. clean install 不依賴 owner-local path；
3. 一個命令可跑完整 vertical slice；
4. exact commit/tree/runtime identity 被綁定；
5. output 是 machine-readable；
6. raw logs/evidence 在 teardown 後仍存在；
7. positive/negative controls 能區分真正 enforcement 與壞掉的環境；
8. 未抵達的外部能力保持 non-PASS；
9. reviewer 不用 producer chat history 即可重跑或反證；
10. GitHub 可直接看到 run、artifact 與 exact-head receipt。

Issue #42 之前，這些能力散落在多個 CLI、tests、workflows 與文件中，沒有單一 full-audit receipt。新增 `audit/` contract 使它們成為一條可執行交付鏈。

---

## Source-of-truth order

```text
persisted runtime/integration artifact
→ executed GitHub Actions job and raw log
→ exact merged code/schema/test
→ open PR head and observed checks
→ canonical Issue checklist
→ README/docs prose
→ prior Agent memory
```

本審計沒有從 Issue checkbox、檔名、test 名稱、workflow 已配置或 README 敘述直接升級 evidence state。

---

## Baseline findings

### 1. GitHub-hosted unit execution is real but incomplete for Browser

`main@e4eace...` 的 `unit` workflow 在 GitHub-hosted Ubuntu/Python 3.11 執行並回報：

```text
Ran 121 tests
OK (skipped=4)
```

它同時執行 Coding Agent、runtime controller、Run Artifact、attestation/transparency tests、OpenShell policy compile、adversarial fixture materialization、schema exact diff、FakeRuntime Harness、Run Artifact build、local Ed25519 sign/verify 與 local transparency receipt。

這是有效的 host execution，不是 account-backed vendor runtime execution。

四個 skipped tests 是 Playwright Browser integration class，因 baseline workflow 沒安裝 optional Playwright runtime。因此 baseline 能證明 Browser contracts，不能證明 Chromium 已被抵達。Issue #42 的 full audit 安裝 Chromium，並將 Browser result、EvidenceBundle、HarnessVerdict、DOM/ARIA/screenshot/download/network artifacts 保存到 artifact。

### 2. Android has a compile boundary, not a complete runtime path

最近 merged code 已包含 Android bounded contract、compile boundary、ADB identity/argv primitives 與 deterministic tests。尚未觀察到完整 trusted ADB runner、self-validating receipt、EvidenceBundle adapter、scripted ADB run、emulator run 或 physical-device run。

```text
Android bounded contract      IMPLEMENTED
Android compile boundary      IMPLEMENTED + HOST-EXECUTED
trusted ADB runtime           NOT_IMPLEMENTED
emulator/device evidence      NOT_EXERCISED
```

### 3. Public GitHub ingestion existed as workflow configuration, not observed main evidence

`integration.yml` 定義了 real public GitHub ingestion，將 mutable branch 解析成 immutable commit/provenance；但查詢 baseline `main` 未找到該 workflow 的 executed run，因為它只由 PR 或 manual dispatch 觸發。

Configured job 不是 integration-verified。Issue #42 將 ingestion 納入 full audit 並保存 resolved provenance。

### 4. OpenShell remains a real external gate

Source tree 有 OpenShell policy compiler/controller、OCSF normalization、filesystem diff、runtime identity checks 與 manual workflow entrypoint。仍缺：

```text
real benign sandbox run
real denied undeclared egress
real L7 method/path denial
brokered provider works while raw credential is unreadable
exact gateway/runner/image evidence
```

Generic Docker container 不等價於 NVIDIA OpenShell；Issue #1 應保持 open。

### 5. Cloudflare implementation does not yet equal account-backed execution

已存在 Python controller、Sandbox Worker bridge、Dynamic Worker contracts 與 TypeScript typechecks。現有 manual job 主要完成 deploy handoff；沒有觀察到 deployed endpoint 被實際呼叫並保存 cold/warm、denied-egress、resource/storage 與 credential-isolation evidence。

```text
TypeScript/Python contracts       IMPLEMENTED + HOST-EXECUTED
account deploy path               CONFIGURED
account-backed runtime receipt    NOT_EXERCISED
```

Issue #42 full audit把兩個 TypeScript contract typechecks 放入同一 evidence packet，但仍不會把它們標成 Cloudflare live runtime。

### 6. Attestation is a real local mechanism, not keyless identity

Baseline 能證明 canonical Run Artifact statement、Ed25519 DSSE、public-key verification、verifier-owned policy、local append-only log 和 inclusion receipt。

原 baseline fixture 使用人工 commit/workflow identity，沒有消費 GitHub OIDC token，也沒有 keyless identity。Issue #42 改用本次 exact commit metadata 與 ephemeral local key，但明確標示：

```text
local cryptographic mechanism     PASS when executed
GitHub OIDC/keyless identity      NOT PROVEN
public witnessed transparency    NOT_IMPLEMENTED
```

### 7. Compatibility/ranking data model exists; universal claims do not

Repository 有 compatibility/scoring structures 與 deterministic tests，但本審計沒有發現足夠的：

```text
Skill digest × Agent/version × Runtime/version × Model/provider
```

live sample cells、sample count 與 uncertainty，不能由單一成功 run 推導 universal compatibility 或 production ranking。

### 8. Public documentation is stale relative to code

README 與 `docs/INTEGRATION_STATE.md` 仍是 2026-08-12 snapshot，描述 Browser PR #29 尚未 merged、Android 尚在 planned state；實際 main 已合併 Browser 與 Android compile work。

風險：fresh Agent 讀到 stale state，選錯 branch/roadmap、重複實作或報出不存在的 gap。Active PR #39/#41 是獨立 docs delivery line；本 audit PR 不應偷偷取代它們，但 evidence packet 必須在 prose 暫時過期時仍保持可判。

---

## Issue #42 executable audit slice

新增：

```text
audit/capability-contract.json
audit/audit_core.py
audit/run.py
audit/run.sh
audit/Dockerfile
audit/README.md
.github/workflows/capability-audit.yml
docs/agents/CAPABILITY_AUDITOR_SYSTEM_PROMPT.md
persistent Browser fixture output support
```

Full path：

```text
exact PR/branch head on ubuntu-24.04
→ Python 3.11 + Node 22
→ install package + Playwright + Chromium
→ full Python suite with Browser tests exercised
→ Cloudflare Worker/Dynamic Worker typechecks
→ schema exact regeneration
→ adversarial fixture materialization
→ Coding Harness → FakeRuntime EvidenceBundle → HarnessVerdict
→ Run Artifact Bundle
→ ephemeral local Ed25519 sign + policy verify + local receipt
→ real Chromium loopback
→ real public GitHub immutable ingestion
→ content-addressed Docker image
→ hardened Linux container
   ├── positive: declared tmpfs write succeeds
   ├── negative: outbound socket exits non-zero
   └── negative: root user cannot write read-only rootfs
→ result JSON + raw logs + runtime metadata + SHA256SUMS
→ artifact upload even on failure
→ final required-state gate
```

Credential rule：all child processes remove ambient tokens/API keys/secrets by default；只有 trusted GitHub ingestion command 可取得 read-only `GITHUB_TOKEN`。Ephemeral private signing key 位於 output 外的 temporary directory，publication 前刪除。

---

## Current out-of-box verdict

### Before Issue #42

**Partially usable, not one-command verifiable.** Fresh Agent 可以安裝並執行許多 deterministic commands，但必須自行知道哪些 commands 應串接、如何安裝 Browser、如何保存 evidence、如何區分 runtime levels，以及哪些 external gates 尚未執行。

### Target after Issue #42 workflow succeeds

**One-command verifiable for the admitted local/GitHub-hosted scope, with declared external gaps.** 可證明：

- clean package/CLI execution；
- full Python and Cloudflare contract checks；
- deterministic Harness/evidence/verdict/Run Artifact path；
- local cryptographic verification path；
- real Chromium loopback；
- public GitHub immutable ingestion；
- hardened generic Linux container positive/negative controls；
- exact-head evidence publication。

仍不代表：

- OpenShell live runtime；
- Cloudflare account-backed cold/warm runtime；
- provider credential-isolation run；
- Android ADB/emulator/device；
- universal compatibility or production ranking；
- public witnessed transparency。

---

## Recommended next atomic roadmap

1. **OpenShell runtime receipt**：real gateway/runner、benign + denied egress + credential non-exposure、persist OCSF/effective policy/image identity。
2. **Cloudflare end-to-end receipt**：deploy 後實際呼叫 endpoint；cold/warm、denied egress、resource/storage、credential isolation；artifact upload。
3. **Android stack**：contract → trusted runner → evidence adapter → scripted ADB → emulator；每層獨立 PR 和 non-claims。
4. **Provider isolation cell**：brokered inference succeeds、raw credential unreadable、run-linked token/latency/quota/cost receipt。
5. **Compatibility sampling**：至少多 Agent/runtime/model cells、sample count、confidence interval；禁止單樣本 universal label。
6. **Public identity/transparency**：在 threat model 需要時，另設 keyless identity 與 independently witnessed log；不可把 local fixture relabel。
7. **Documentation reconciliation**：在 PR #39/#41 解決 main drift，README 顯示 machine-generated/latest audit pointer，而不是手動複製狀態。

每個 slice 都要有：exact subject、falsifier、runtime identity、positive/negative controls、persisted artifact、Issue/PR/run receipt 與 explicit non-claims。
