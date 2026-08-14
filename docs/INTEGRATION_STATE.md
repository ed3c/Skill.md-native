# Integration State Ledger

> Mutable handoff snapshot. Read after `AGENTS.md` and `README.md`; re-check GitHub before relying on status.

## Snapshot — 2026-08-14 Asia/Taipei

| Field | Value |
|---|---|
| Repository | `ed3c/Skill.md-native` |
| Default branch | `main` |
| Verified main head | `afbab914ba09fa5743bead3f059316c3ece7fcab` |
| Browser | merged/hardened |
| Android Issue | #28 active |
| Android main state | bounded contract + compile boundary merged |
| Git Town config | not detected |

## Evidence priority

```text
persisted runtime/integration evidence
> executed Actions
> merged commits
> current PR head/checks
> canonical Issue
> docs
> Agent memory
```

## Merged capabilities

- Cross-domain Harness Kernel: #17.
- Coding Agent Harness: #19, #26.
- Run Artifact / Evidence Graph / replay / scorecard: #22.
- DSSE + transparency: #24.
- Browser Playwright Harness: #29; contract/privacy continuity hardening #32.
- Android bounded contract: #35 → `49251371eddc36da8b4337eceef4575993ed1824`; pre-merge unit #133 and integration #54 succeeded.
- Android compile boundary: #37 → `afbab914ba09fa5743bead3f059316c3ece7fcab`; main-target unit #136 and integration #56 succeeded before merge.

## Android current state

Main contains the compile-time chain:

```text
AndroidContract
→ contract/action digests
→ AndroidRunnerConfig
→ config digest
→ canonical stdin
→ byte-level stdin SHA-256
→ fixed runner argv
```

This establishes privacy/continuity before any ADB process exists.

Not yet established:

- `android.adb.v1` registration in HarnessManifest/DomainAdapter registry;
- real ADB binary/process execution;
- exact device attestation at runtime;
- AndroidReceipt;
- UI hierarchy/screenshot/logcat/package/window evidence normalization;
- scripted fake-ADB verdict;
- emulator evidence;
- physical-device evidence;
- isolated Android runtime evidence.

## Next terminal slices

```text
A1c HarnessManifest + android.adb.v1 wiring
→ A2a ADB binary/device/typed-argv primitives
→ A2b bounded subprocess lifecycle
→ A3 AndroidReceipt + artifact/EvidenceBundle
→ A4 scripted fake-ADB verification
→ A5 fixed emulator CI + persisted evidence
→ A6 Appium/Maestro
→ A7 Mobly/multi-device
```

## Historical Android branches

PRs #31/#34/#33 are stale-ancestry history. They predate Browser hotfix #32 in their parent chain and must not be used as parents for new work. Port useful design/tests only after re-review onto the active main lineage.

PR #36 is useful stacked-delivery history: it verified the compile boundary on the feature parent. PR #37 is the authoritative main landing.

## External evidence gates

Do not close or upgrade these from mocks/configuration alone:

- OpenShell hostile-runtime evidence;
- brokered credential-isolation evidence;
- Cloudflare cold/warm/egress/resource evidence;
- detector recall/FPR evidence;
- Android scripted/emulator/physical-device evidence.

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

## Agent handoff

1. Fetch current main SHA and Issue #28.
2. Start A1c from actual main, not an old Android feature branch.
3. Keep manifest wiring, ADB primitives, process lifecycle, evidence, scripted fixture, and emulator CI as separate trust-boundary slices.
4. For each PR record parent SHA, exact head, workflow evidence, establishes-state and non-claims.
5. Update README/AGENTS/integration/stack ledgers after topology changes.
