# Android Harness

> Status: A1 contract primitive. This document does **not** claim a trusted ADB runner, emulator execution, physical-device execution, Appium, Maestro, Mobly, or runtime-isolated Android verification.

## Goal

The Android domain extends the cross-domain Harness Kernel without exposing arbitrary device shell access to an untrusted Skill manifest.

The planned vertical chain is:

```text
AndroidContract
→ android.adb.v1 manifest integration
→ trusted ADB runner
→ AndroidReceipt
→ content-addressed device/UI artifacts
→ normalized EvidenceBundle
→ deterministic Android checks
→ HarnessVerdict
→ RunArtifactBundle
→ attestation / transparency publication
```

A1 defines only the first contract boundary. Later slices must preserve it rather than widening the action surface for convenience.

## Threat model

Treat all of these as untrusted:

```text
Skill instructions
scenario task
Android application
connected device state
UI text
logcat
package/activity state
screenshots
UIAutomator XML
ADB stdout/stderr
```

The trusted wrapper must own process construction, stdout receipt emission, artifact validation, timeouts, device selection, and final-state verification.

## Explicitly forbidden manifest capabilities

Contract v1 intentionally has no action for:

```text
arbitrary adb shell
free-form shell command
input text
install / uninstall
push / pull
root / unroot
remount
bootloader / fastboot
SELinux mutation
package-manager mutation
arbitrary file reads
arbitrary environment reads
```

Future features that need one of these operations require a new bounded primitive and security review. They must not be added as an escape hatch such as `shell: string`.

## A1 action grammar

`src/skill_native/android_contract.py` permits only:

```text
start_activity
keyevent
tap
swipe
wait
wait_for_package
wait_for_activity
wait_for_ui_text
capture_ui_hierarchy
capture_screenshot
```

Every process-bound identifier uses a constrained type. Package, activity, ABI, serial, artifact names, coordinates, durations, and byte budgets have explicit bounds.

`wait_for_ui_text` is observation matching, not text injection. There is intentionally no `input_text` action in v1.

## Device identity contract

The contract can constrain:

```text
serial
minimum / maximum API level
allowed ABI set
model
product
build ID
fingerprint
```

The trusted runner slice must later resolve exactly one online device and fail closed when the selected device does not satisfy every declared constraint.

ADB itself is also an identity input:

```text
adb_version
adb_sha256
```

A2 must verify the actual executable path/version/digest before executing device actions. A package-supplied string claiming an ADB version is not evidence.

## Digest semantics

A1 exports two deterministic helpers:

```text
android_contract_digest(contract)
android_action_plan_digest(actions)
```

Changing device constraints, ADB identity, action parameters, assertions, artifact limits, or any other contract field changes the contract digest. Changing only actions changes the action-plan digest.

When Android is integrated into `HarnessManifest`, both identities must participate in the compiled-plan continuity chain.

## Artifact policy

The contract declares a safe relative `artifact_root` and explicit byte limits for:

```text
UI hierarchy
screenshot
logcat
total artifacts
```

A3 must additionally enforce filesystem reality:

```text
root is trusted
no traversal
no symlink
no special file
file exists
size matches receipt
SHA-256 matches receipt
aggregate budget holds
```

Declaring a safe string path at A1 is necessary but not sufficient evidence of artifact integrity.

## Final-state assertions

The contract requires at least one deterministic final assertion. Initial assertion types are:

```text
package
activity
ui_text
```

A successful process exit must never substitute for final-state success.

## Planned stacked delivery

```text
A1 contract primitive / manifest integration
  ↓
A2 trusted ADB runner
  ↓
A3 evidence + artifact integrity
  ↓
A4 scripted fake-ADB fixtures
  ↓
A5 hosted emulator CI
```

Each slice must be independently reviewable and must state its verification level precisely.

## Verification vocabulary

```text
contract-implemented
  Strict Android models and negative tests exist.

scripted-fixture-verified
  A controlled fake ADB process exercised the trusted runner and evidence path.

emulator-integration-verified
  A real Android emulator produced persisted device/UI evidence.

physical-device-verified
  A pinned physical device produced persisted evidence.

runtime-isolated-android-verified
  Android control executed through a declared isolated runtime boundary with persisted isolation evidence.
```

No weaker state implies a stronger one.

## A1 acceptance

A1 is acceptable when deterministic tests prove at minimum:

```text
valid bounded contracts load
arbitrary shell action is rejected
free-form text-input action is rejected
unsafe package/serial tokens are rejected
artifact traversal is rejected
duplicate artifact/assertion identifiers are rejected
API and wait bounds fail closed
digests change when trust inputs change
extra fields are rejected
```

A1 does not execute ADB and does not establish Android runtime evidence.
