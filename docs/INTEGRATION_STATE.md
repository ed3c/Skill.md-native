# Integration State Ledger

> Mutable handoff snapshot for humans and coding agents. Read after `AGENTS.md` and `README.md`. Re-check GitHub before relying on any status here.

## Snapshot identity

| Field | Value |
|---|---|
| Repository | `ed3c/Skill.md-native` |
| Snapshot date | 2026-08-14, Asia/Taipei |
| Default branch | `main` |
| Verified main head at snapshot | `49251371eddc36da8b4337eceef4575993ed1824` |
| Main head capability | Browser hardened + Android bounded contract |
| Active Android Issue | #28 |
| Main-target Android PR | #37 |
| Git Town repository config | not detected |

## Source-of-truth order

```text
persisted runtime/integration evidence
> executed GitHub Actions
> merged commit history
> current PR head/checks
> canonical Issue
> documentation
> Agent memory
```

## Merged state

| Capability | Trace | Evidence state |
|---|---|---|
| Cross-domain Harness Kernel | #17 | merged/CI established |
| Coding Agent Harness | #19, #26 | merged/CI established |
| Run Artifact Bundle / Evidence Graph | #22 | merged/CI established |
| DSSE + transparency | #24 | merged/CI established |
| Browser Playwright Harness | #29 | merged; deterministic local Browser integration lineage |
| Browser contract/privacy hardening | #32 | merged; full CI green before merge |
| Android bounded contract | #35 → `49251371...` | merged; current-main unit #133 + integration #54 succeeded before merge |

## Android-28 active delivery state

### A1 — bounded contract

**Merged.** `src/skill_native/android_contract.py` is on main. It establishes typed bounded actions, device constraints, ADB version/SHA constraints, final assertions, artifact budgets, and deterministic contract/action digests.

It does **not** establish ADB execution, HarnessManifest registration, evidence capture, emulator verification, or physical-device verification.

### A1b — compile boundary

Stacked PR #36 established:

```text
AndroidContract
→ AndroidRunnerConfig
→ contract/action/config digest continuity
→ canonical stdin
→ byte-level stdin SHA-256
→ fixed runner argv
```

Its head `1d32ea6f3dc9278645539729c9310efb3090026b` passed:

- unit workflow #134;
- integration workflow #55.

PR #36 merged into its parent feature branch, not directly into main. PR #37 now targets main to land the effective delta. PR #37 head is the same `1d9b85f...` and fresh main-target workflows succeeded:

- unit #136: success;
- integration #56: success;
- schema-sync: skipped by workflow condition.

Until PR #37 is actually merged, do not say `android_compile.py` is on main.

### Next slices

```text
A1c HarnessManifest + android.adb.v1 wiring
→ A2a ADB binary/device/typed-argv primitives
→ A2b bounded subprocess lifecycle
→ A3 AndroidReceipt + artifact/EvidenceBundle integration
→ A4 scripted fake-ADB verification
→ A5 fixed emulator CI + persisted evidence
→ A6 Appium/Maestro
→ A7 Mobly/multi-device
```

## Historical/superseded Android lineage

PRs #31, #34 and #33 preserve useful implementation/CI history but are not the active stack. Their parent ancestry predates Browser hotfix #32 and caused unrelated Browser regressions in merge-ref CI. Do not revive those branches as parents for new Android work.

A hardened ADB-primitives prototype exists in historical branch lineage and includes the design intent for `O_NOFOLLOW` binary attestation, strict `adb devices -l` parsing, exact-online-device selection and typed argv compilation. Re-implement/rebase it only after the active parent is clean; do not claim it is merged.

## Browser state

Browser is merged, not open. The merged/hardened path includes canonical stdin-bound configuration, origin constraints, Browser evidence channels, artifact integrity, deterministic assertions, and explicit non-isolated fixture labeling. Public-site, credentialed-site, hosted-browser, or runtime-isolated verification still require their own evidence.

## External evidence gates

The following remain evidence-gated and must not be closed from mocks/configuration alone:

- real OpenShell hostile-runtime evidence;
- brokered inference credential-isolation evidence;
- Cloudflare cold/warm/egress/resource evidence;
- live detector recall/FPR evidence;
- Android emulator/physical-device evidence.

## Verification vocabulary

```text
implemented
CI-verified
scripted-fixture-verified
deterministic-local-integration-verified
emulator-integration-verified
physical-device-verified
runtime-isolated-verified
```

Only claim the strongest state directly supported by persisted evidence.

## Agent handoff checklist

Before continuing work:

1. Fetch current `main` SHA.
2. Fetch Issue #28 and current Android PR metadata.
3. Inspect workflow runs for the exact head SHA.
4. Check whether PR #37 has merged; if yes, update this ledger immediately.
5. Build the next terminal branch from the actual merged parent, not an old feature branch.
6. Keep HarnessManifest wiring, ADB process execution, evidence normalization and emulator CI in separate trust-boundary slices.
7. Update README + this ledger + `STACKED_DELIVERY.md` whenever topology changes.
