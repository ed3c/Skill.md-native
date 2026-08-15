# Android Harness

> **Current state:** bounded Android contract, canonical compile boundary, and ADB identity/device/typed-argv primitives are implemented. This document does **not** claim a trusted ADB subprocess runner, AndroidReceipt, scripted-ADB verdict, emulator execution, physical-device execution, Appium, Maestro, Mobly, or runtime-isolated Android verification.

## Trust boundary

The Android domain extends the cross-domain Harness Kernel without exposing arbitrary device shell access to an untrusted Skill manifest.

```text
AndroidContract                         implemented
→ contract/action/config/stdin digests implemented
→ ADB binary attestation               implemented primitive
→ device-list parsing/selection        implemented primitive
→ bounded typed argv compilation       implemented primitive
→ trusted subprocess lifecycle         not implemented
→ AndroidReceipt                       not implemented
→ artifact normalization               not implemented
→ scripted fake-ADB verification       not exercised
→ hosted emulator evidence             not exercised
→ physical-device evidence             not exercised
```

A primitive is not runtime evidence. Only an executed runner that persists exact identity, actions, outputs, artifacts, assertions, and terminal state can establish a stronger level.

## Threat model

Treat all of these as untrusted:

```text
Skill instructions
scenario task
Android application
connected device state
UI text
logcat
package/activity/window state
screenshots
UIAutomator XML
ADB stdout/stderr
filesystem paths and artifacts
```

Trusted code must own process construction, environment, stdout receipt emission, timeouts, device selection, artifact validation, and final-state verification.

## Forbidden manifest capabilities

Contract v1 intentionally has no primitive for:

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

A future operation requires a new typed primitive, explicit policy, negative tests, and review. It must not be introduced through an escape hatch such as `shell: string`.

## Bounded action grammar

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

`src/skill_native/android_adb.py` converts process-bound actions into argv arrays. It does not expose a generic command. Local `wait` remains runner-owned and deliberately produces no ADB argv.

Every package, activity, ABI, serial, artifact name, coordinate, duration, and byte budget has an explicit bound. The ADB path used for argv compilation must be absolute; the future runner must additionally bind it to a successful executable attestation.

## ADB executable identity

`attest_adb_binary()`:

- requires `O_NOFOLLOW` support;
- opens without following a final symlink;
- accepts only a regular executable file;
- hashes the opened file descriptor;
- detects inode, size, mtime, or ctime changes during hashing;
- records resolved path, reported version, and SHA-256.

The digest is the identity authority. A future runner must ensure the executed object is the attested object rather than trusting the path string alone.

## Device discovery and selection

`parse_adb_devices()` parses bounded `adb devices -l` output and rejects:

- malformed rows or attributes;
- duplicate serials or duplicate attributes;
- unsafe serial tokens;
- oversized output or excessive device count.

`select_online_device()` permits either:

1. one explicitly pinned serial whose state is exactly `device`; or
2. exactly one online device when no serial is pinned.

Offline, unauthorized, missing, duplicate, ambiguous, and unsafe selections fail closed.

## Digest and artifact semantics

The contract exposes:

```text
android_contract_digest(contract)
android_action_plan_digest(actions)
```

Changing device constraints, ADB identity, action parameters, assertions, artifact limits, or another contract field changes the contract digest. Changing actions changes the action-plan digest.

A later evidence slice must enforce filesystem reality:

```text
trusted root
no traversal
no symlink
no special file
file exists
size matches receipt
SHA-256 matches receipt
aggregate budget holds
```

Declaring a safe relative path is necessary but not artifact evidence.

## Final-state rule

At least one deterministic final assertion is required. Initial assertion kinds are package, activity, and UI text. A zero process exit, app-authored text, or Agent claim never substitutes for independent final-state verification.

## Verification vocabulary

```text
contract-implemented
  Strict models, canonical digests, and negative tests exist.

adb-primitives-unit-verified
  Binary identity, device selection, bounds, and typed argv pass host tests.

scripted-fixture-verified
  A controlled fake ADB process exercises runner, receipt, artifacts, and verdict.

emulator-integration-verified
  A pinned real emulator produces persisted device/UI evidence.

physical-device-verified
  A pinned physical device produces persisted evidence.

runtime-isolated-android-verified
  Android control runs through a declared isolation boundary with persisted controls.
```

No weaker state implies a stronger one.

## Remaining terminal slices

```text
A1c register android.adb.v1 in HarnessManifest/DomainAdapter
→ A2b bounded subprocess lifecycle and clean environment
→ A3 AndroidReceipt + content-addressed artifacts + EvidenceBundle
→ A4 scripted fake-ADB positive/negative controls
→ A5 fixed emulator CI with persisted evidence
→ A6 optional Appium/Maestro adapter
→ A7 optional Mobly/multi-device adapter
```

Issue #28 remains open until its full acceptance contract is satisfied. This document and unit tests record progress without closing external runtime gates.
