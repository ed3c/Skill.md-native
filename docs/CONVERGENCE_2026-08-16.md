# Stacked Delivery and Convergence Ledger

## Purpose

This file records delivery topology without treating an open branch as product truth. Git history, exact workflow subjects, and persisted artifacts remain authoritative.

## Current convergence

```text
main@17eb098187d329b45a13954120319d32e25d8465
└── agent/converge-open-prs-2026-08-16
    ├── reconstruct unique Android contract tests/docs from PR #31
    ├── reconstruct and harden ADB primitives from PR #33
    ├── reconstruct current integration/public docs from PR #39
    └── reconstruct bilingual/community-health baseline from PR #41
```

The convergence branch is intentionally based on current `main`. It does not rebase, force-push, or merge stale branch ancestry. Only reviewed, path-owned content is reconstructed.

## Supersession map

| Historical PR | Disposition | Reason |
|---|---|---|
| #31 | superseded after convergence | current `android_contract.py` already landed; only tests/docs were still unique |
| #33 | superseded after convergence | ADB primitives are reconstructed with added deterministic negative tests |
| #34 | closed | PR #37 already landed the same compile-owned files on current `main` |
| #39 | superseded after convergence | documentation is reconstructed against current code and PR #43 audit truth |
| #41 | superseded after convergence | bilingual/community files are reconstructed without overwriting current `AGENTS.md` or workflows |

Closing a superseded PR must not delete its branch or erase evidence. It means the branch must not be merged independently.

## CI economy contract

For a repository convergence:

```text
inventory all open PRs and issues
→ classify merged-equivalent / unique / negative diagnostic / blocked external
→ reconstruct all admissible unique paths on one current-main head
→ open one PR
→ allow one natural exact-head Actions cycle
→ inspect failed jobs once
→ change only owned root causes
→ never no-op push or blind rerun
→ merge only exact green head
→ close superseded PRs without CI
```

A second Actions cycle is justified only when the first exact-head run reveals a hidden repository contract that could not be proven from the checked-in files. Every additional push must repair a bounded root cause; it must not merely retry infrastructure or consume budget.

## Merge admission

A convergence PR may merge only when:

- its head is still the reviewed exact SHA;
- all repository-owned required workflows are successful;
- no unresolved review thread remains;
- external capability claims remain explicit non-claims;
- current `main` has not moved outside the reviewed mergeability state;
- the merge method preserves evidence-bearing ancestry where required.

## Git Town state

No repository-owned Git Town configuration is detected. This ledger describes stack ancestry but does not authorize `git town` commands or fabricate Git Town metadata.

## External gates

Owner merge authority cannot substitute for runtime, billing, device, provider, account, legal, or production evidence. Those PRs remain blocked or diagnostic until the named environment produces a persisted receipt.
