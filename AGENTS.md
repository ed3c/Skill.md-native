# Skill.md-native — Agent Execution Contract

> Canonical operating contract for coding agents. Read this file first, then `README.md`, `docs/INTEGRATION_STATE.md`, the relevant domain document, and `docs/STACKED_DELIVERY.md` before changing code, Issues, PRs, CI, schemas, runtime adapters, evaluators, or documentation.

## Mission

Build Skill.md-native into a cross-registry, runtime-verified trust and evaluation layer for `SKILL.md` / Agent Skill workflows. A ranking or compatibility claim is valid only when it can be traced to immutable provenance, an exact execution plan, captured evidence, deterministic verification, and an explicit security gate.

The repository is not primarily a marketplace. Discovery is an input; the durable asset is the evidence + evaluation + security + compatibility + outcome-ranking layer.

## Current integration state — 2026-08-14

Do not infer state from old conversation history. Re-check GitHub before editing this section.

- `main@49251371eddc36da8b4337eceef4575993ed1824` contains Browser Harness hardening plus the bounded Android contract primitive from PR #35.
- Browser implementation is merged. Issue #27 is completed. Do not describe Browser as an open Draft feature.
- Android Issue #28 is active.
- PR #35 is merged and established the Android compile-time action/device/ADB contract on current main.
- Stacked PR #36 was CI-green and merged into its parent feature branch, not directly into `main`; its compile-boundary delta is being landed through PR #37.
- PR #37 targets `main`, is non-Draft and has fresh successful `unit #136` and `integration #56` evidence. Until PR #37 is actually merged, `android_compile.py` is not a main-branch capability.
- Historical PRs #31, #34 and #33 were based on stale Browser ancestry. Preserve them as evidence/history; do not use them as the active Android stack.
- Repository-level Git Town configuration is not detected. Use the explicit parent/PR ledger in `docs/STACKED_DELIVERY.md`.

Verification vocabulary is strict:

```text
implemented
!= CI verified
!= scripted-fixture verified
!= emulator-integration verified
!= physical-device verified
!= runtime-isolated verified
```

Never upgrade a state without persisted evidence for that stronger state.

## Required reading order

```text
AGENTS.md
→ README.md
→ docs/INTEGRATION_STATE.md
→ relevant domain/trust document
→ docs/STATE_MACHINES.md
→ docs/STACKED_DELIVERY.md
→ canonical Issue
→ current PR metadata + workflow evidence
```

If these disagree, use this evidence priority:

```text
persisted runtime/integration evidence
> executed GitHub Actions
> merged commit history
> current PR head/checks
> canonical Issue
> documentation snapshot
> Agent memory/conversation history
```

Then repair the stale documentation in the same delivery chain.

## Trust model

Treat every third-party Skill, child agent, page, app, device, tool response, network response, downloaded artifact, stdout/stderr stream, and model output as untrusted.

The trusted control plane owns:

- immutable provenance and content digests;
- manifest and RunSpec validation;
- DomainAdapter selection;
- runtime capability and evidence profiles;
- command/stdin compilation;
- process lifecycle and policy enforcement;
- evidence collection and content addressing;
- deterministic verifier execution;
- security-gate aggregation;
- Run Artifact derivation;
- signing/trust policy/transparency publication.

A package-supplied assertion is not authoritative merely because it passes.

## Evidence invariant

Every important claim should be traceable through:

```text
ranking/report claim
→ scorecard / compatibility cell
→ HarnessVerdict
→ verifier check
→ EvidenceBundle / evidence_id
→ domain/runtime receipt and raw artifact digest
→ HarnessPlan
→ RunSpec
→ immutable provenance digest
→ exact Skill artifact
```

High/Critical security findings are non-compensable. Task success, signature validity, publication, popularity, stars, or model confidence cannot override a failed security gate.

## Cross-domain Harness contract

Portable execution unit:

```text
SKILL.md
+ harness.yaml
+ immutable RunSpec
+ DomainAdapter
+ runtime capability/evidence profile
+ executable assertions
+ EvidenceBundle
+ HarnessVerdict
+ RunArtifactBundle
+ optional DSSE/transparency publication
```

Current domain progression:

```text
Coding  → merged execution/evidence vertical slice
Browser → merged Playwright deterministic vertical slice
Android → contract merged; compile boundary in PR #37; runner/evidence/emulator pending
Desktop / SRE / Documents / Voice / Robotics → vocabulary/roadmap unless code + evidence says otherwise
```

Unknown adapters, mutable provenance, unsupported evidence, unavailable capabilities, policy mismatch, malformed receipts, digest discontinuity, or budget overruns fail closed.

## Android Issue #28 delivery contract

Active terminal sequence:

```text
A1  bounded Android contract                  MERGED via #35
A1b canonical runner config/stdin continuity PR #37 → main
A1c HarnessManifest + android.adb.v1 wiring  NEXT
A2a ADB binary/device/typed-argv primitives  NEXT after A1c ancestry is clean
A2b bounded subprocess lifecycle             PENDING
A3  AndroidReceipt + artifact/evidence       PENDING
A4  scripted fake-ADB verification           PENDING
A5  fixed emulator CI + persisted evidence   PENDING
A6  Appium/Maestro                           FUTURE
A7  Mobly/multi-device                       FUTURE
```

Android v1 must not expose arbitrary shell, arbitrary ADB commands, install/uninstall, root/remount, unrestricted push/pull, bootloader mutation, or free-form text injection. New capabilities require typed bounded primitives.

The trusted Android runner must eventually prove exact ADB binary identity, exact device selection, bounded argv, timeout/process cleanup, bounded output, final-state assertions, artifact integrity, and a single trusted receipt before emulator claims are allowed.

## Runtime strategy

- OpenShell: hostile-code/reference security runtime; live claims require real runtime evidence.
- Cloudflare Sandbox/Dynamic Workers: cloud execution backends; configured workflows are not live verification.
- Fake/domain fixture runtimes: contract and deterministic integration evidence only.
- Enroot or similar performance runtimes must not be represented as equivalent hostile-code isolation.

Credentials remain brokered. Never implement credential discovery, stolen/shared key rotation, quota circumvention, account farming, or provider ToS bypass.

## State ownership rule

Each module should own one clear transition. See `README.md` and `docs/STATE_MACHINES.md` for the directory map. In general:

```text
ingestion/provenance → immutable artifact identity
contracts/compiler   → validated HarnessPlan
domain runner        → trusted domain receipt
runtime collector    → raw evidence
evidence/security    → normalized evidence + findings
verifiers/kernel     → HarnessVerdict
run_artifacts        → graph/replay/trace/scorecard
attestation          → signed/published artifact
compatibility        → cross-run cells/ranking
```

Do not move trust decisions into untrusted runners merely to simplify an interface.

## Delivery and stacked PR rules

A terminal PR should change one trust boundary and establish one independently reviewable state transition.

Every stacked PR body or ledger entry must record:

```text
Stack-ID
Parent-Branch
Parent-Head-At-Open
Slice
Depends-On
Establishes-State
Does-Not-Claim
```

If a parent is squash-merged, rebuild or retarget children against the new `main`; do not keep stale merge ancestry and then repair unrelated regressions inside child PRs.

Before merge:

1. inspect current PR head and base;
2. verify expected head SHA;
3. inspect current workflow conclusions;
4. check unresolved review threads;
5. distinguish skipped/account-gated jobs from successful jobs;
6. merge only the intended slice;
7. immediately update `README.md`, `docs/INTEGRATION_STATE.md`, and `docs/STACKED_DELIVERY.md` when topology/state changed.

## Documentation rule

Documentation is executable coordination state. Never leave README/AGENTS claiming an old PR is open after it merged, or claiming a planned branch exists when it does not.

Use exact SHAs and workflow run numbers for short-lived handoff state in `docs/INTEGRATION_STATE.md`; keep long-lived invariants here.

## Non-negotiable safety rules

- Never expose API keys or raw provider credentials to a Skill or sandbox.
- Never silently weaken network/filesystem/secret policies.
- Never use mutable refs as evaluated artifact identity.
- Never let child stdout/page/device output inject a trusted top-level receipt.
- Never accept missing mandatory evidence as success.
- Never call a configured workflow a verified runtime.
- Never call a mock/fixture run production verification.
- Never merge unrelated trust-boundary changes merely to make CI green.
- Never bypass GitHub safety gates with force ref updates or low-level Git object writes.
