# Integration State Ledger

> Mutable handoff snapshot for 2026-08-16 Asia/Taipei. Read after `AGENTS.md` and `README.md`; resolve the current `main` SHA and exact workflow subject before relying on a state.

## Convergence baseline

| Field | Value |
|---|---|
| Repository | `ed3c/Skill.md-native` |
| Default branch | `main` |
| Convergence base | `17eb098187d329b45a13954120319d32e25d8465` |
| Base meaning | PR #43 capability-audit merge, preserving its evidence ancestry |
| Git Town config | not detected; no Git Town commands are assumed |
| Open Android authority | Issue #28 |

## Evidence priority

```text
persisted runtime/integration artifact
> exact executed Actions subject and raw logs
> merged code, contracts, and tests
> current PR head and observed checks
> canonical Issue acceptance contract
> current documentation
> Agent memory or conversational summary
```

A configured workflow, fixture, signature, branch, or prose statement cannot upgrade an unexecuted capability.

## Merged and carried-forward capabilities

- Cross-domain Harness Kernel, Coding Agent Harness, Run Artifact/Evidence Graph/replay/scorecard, DSSE/local transparency, Browser contract/runtime path, Android bounded contract, and Android canonical compile boundary are present on the convergence base.
- PR #43 added an executable capability-audit contract. Its admitted exact-head run exercised the full Python suite with Chromium installed, public GitHub immutable ingestion, Cloudflare TypeScript contract checks, deterministic Harness/evidence/verdict/Run Artifact flow, local cryptographic verification, and a hardened generic Docker container with positive and negative controls.
- That audit does not establish NVIDIA OpenShell, account-backed Cloudflare runtime, provider credential isolation, Android device execution, universal compatibility, production ranking, keyless identity, or publicly witnessed transparency.

The machine-readable audit artifact and exact workflow subject outrank this ledger. See `audit/README.md` and `docs/audits/2026-08-15-capability-audit.md`.

## Android current state

This convergence ports the useful portions of stale PRs #31 and #33 onto the current main lineage without rebasing or merging their obsolete ancestry.

```text
AndroidContract
→ contract/action digests
→ AndroidRunnerConfig
→ config digest
→ canonical stdin
→ byte-level stdin SHA-256
→ fixed runner argv
→ ADB executable identity primitive
→ bounded adb devices parser
→ exact online-device selector
→ typed action-to-argv compiler
```

Established state after the convergence head passes CI:

```text
bounded-contract-implemented
canonical-compile-boundary-host-executed
adb-primitives-unit-verified
```

Not established:

- `android.adb.v1` registration in HarnessManifest/DomainAdapter registry;
- trusted bounded subprocess lifecycle;
- proof that the executed ADB object equals the attested object;
- AndroidReceipt and artifact descriptors;
- UI hierarchy/screenshot/logcat/package/window evidence normalization;
- scripted fake-ADB HarnessVerdict;
- emulator evidence;
- physical-device evidence;
- isolated Android runtime evidence.

Issue #28 therefore remains open.

## Active terminal slices

```text
A1c HarnessManifest + android.adb.v1 wiring
→ A2b bounded subprocess lifecycle
→ A3 AndroidReceipt + artifact/EvidenceBundle integrity
→ A4 scripted fake-ADB verification
→ A5 fixed emulator CI + persisted evidence
→ A6 optional Appium/Maestro
→ A7 optional Mobly/multi-device
```

## Historical PR reconciliation

- PR #34 was closed because PR #37 already landed the same compile-owned files on current `main`.
- PRs #31 and #33 remain historical sources only; their useful contract tests, documentation, and ADB primitives are reconstructed on the convergence head.
- PRs #39 and #41 remain historical documentation-stack sources only; their public documentation and community-health files are reconstructed on the convergence head while current `AGENTS.md` and PR #43 audit code remain authoritative.
- After the convergence PR lands, #31, #33, #39, and #41 should be closed as superseded without additional CI.

## External evidence gates

Do not close or upgrade these from mocks, configuration, or owner authority alone:

- OpenShell hostile-runtime and OCSF evidence;
- brokered provider credential-isolation evidence;
- account-backed Cloudflare cold/warm/egress/resource evidence;
- detector recall/FPR evidence;
- Android scripted/emulator/physical-device evidence;
- production release or deployment evidence.

## Verification vocabulary

```text
implemented
unit-verified
CI-verified
scripted-fixture-verified
deterministic-local-integration-verified
emulator-integration-verified
physical-device-verified
runtime-isolated-verified
production-verified
```

No weaker state implies a stronger state.

## Agent handoff

1. Fetch current `main`, Issue #28, and the latest exact audit artifact.
2. Start new Android work from actual `main`, never from PRs #31/#33/#34.
3. Keep manifest wiring, process lifecycle, receipt/artifacts, scripted fixture, emulator, and physical device as separate trust-boundary slices.
4. Record parent SHA, exact head, workflow run, persisted artifacts, established state, and explicit non-claims for every PR.
5. Do not rerun failed CI without changing the owned root cause, and do not weaken gates to obtain green status.
