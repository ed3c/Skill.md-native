# Stacked Delivery and Traceability Ledger

Terminal implementation slices are decomposed by trust boundary and traced by explicit parent/PR metadata.

## Git Town status

No repository-level `.git-branches.toml`, `git-town.toml`, `.git-town.toml`, or Git Town path is detected as of 2026-08-14. Do not claim Git Town is active. This explicit ledger is Git Town-compatible and remains authoritative for semantic parentage.

## Required metadata

```text
Stack-ID
Parent-Branch
Parent-Head-At-Open
Slice
Depends-On
Establishes-State
Does-Not-Claim
```

## Merge rule

After a parent squash merge, rebuild or retarget children against the new main and obtain fresh merge-ref CI. Never carry stale ancestry forward and fix unrelated regressions inside a child slice.

## Merged chain

```text
#7 runtime/evidence bootstrap
→ #17 Harness Kernel
→ #19 Coding Agent Harness
→ #22 Run Artifact Bundle
→ #26 stdin hardening
→ #24 attestation/transparency
→ #29 Browser Harness
→ #32 Browser hardening
→ #35 Android bounded contract
→ #37 Android compile boundary
→ main@afbab914ba09fa5743bead3f059316c3ece7fcab
```

## Android-28 active stack

```text
main@afbab914...
└── A1c HarnessManifest + android.adb.v1 wiring
    └── A2a ADB binary/device/typed-argv primitives
        └── A2b bounded subprocess lifecycle
            └── A3 AndroidReceipt + artifact/evidence
                └── A4 scripted fake-ADB verification
                    └── A5 fixed emulator CI
                        ├── A6 Appium/Maestro
                        └── A7 Mobly/multi-device
```

### Completed A1 — contract

PR #35, main commit `49251371eddc36da8b4337eceef4575993ed1824`. Pre-merge unit #133 and integration #54 succeeded. Establishes bounded Android actions, device constraints, ADB identity constraints, final assertions, budgets and deterministic digests. Does not establish execution.

### Completed A1b — compile boundary

PR #36 provided stacked CI evidence; PR #37 is the authoritative main landing. Main commit `afbab914ba09fa5743bead3f059316c3ece7fcab`. Main-target unit #136 and integration #56 succeeded before merge.

Establishes `AndroidRunnerConfig`, contract/action/config continuity, canonical stdin, byte-level stdin SHA-256 and fixed trusted runner argv. Does not establish real ADB execution/evidence.

### Next A1c — manifest/domain adapter wiring

Scope only:

- optional Android contract in HarnessManifest;
- `android.adb.v1` requires Android domain;
- other adapters reject Android contract;
- stdin-stream capability;
- trusted adapter registration/command compilation;
- compile-only HarnessPlan tests;
- schema export/drift.

No subprocess or AndroidReceipt.

### A2a — ADB primitives

- no-follow binary attestation;
- exact ADB version/digest;
- strict `adb devices -l` parsing;
- exactly-one-online-device selection;
- typed action → argv;
- no generic shell primitive.

### A2b — subprocess lifecycle

- `shell=False`;
- minimal environment;
- bounded streaming stdout/stderr;
- timeout;
- process-group cleanup;
- runner-owned trusted output channel.

### A3 — receipt/evidence

AndroidReceipt, device/build/package/window state, UIAutomator XML, screenshot, bounded/redacted logcat, content-addressed artifacts, path/symlink/digest/budget checks, EvidenceBundle/EvidenceGraph normalization.

### A4 — scripted fixture

Deterministic fake-ADB success/failure/ambiguity/tamper suite. Establishes scripted-fixture state only.

### A5 — emulator CI

Fixed API/ABI/profile emulator + persisted artifacts/verdict. Establishes emulator verification only after the job actually executes and evidence persists.

### A6/A7

Appium/Maestro and Mobly/multi-device are later adapters.

## Historical stale ancestry

PRs #31/#34/#33 are historical evidence only. Their parent chain predates Browser hotfix #32 and is not an active Android stack. PR #36 is also historical after #37 landed its effective delta to main.

## Verification state

```text
implemented
→ CI-verified
→ scripted-fixture-verified
→ emulator-integration-verified
→ physical-device-verified
→ runtime-isolated-verified
```

These arrows are not automatic promotion; every stronger state requires new evidence.

## Maintenance

After every merge, update parent SHA, merge commit, workflow evidence, planned/actual branch state, README and `docs/INTEGRATION_STATE.md`. Preserve superseded branches as history rather than treating them as active parents.
