# Skill.md-native — Agent Execution Contract

> This file is the canonical requirements and execution context for coding agents working in this repository. Read it before changing code, Issues, CI, runtime adapters, evaluation logic, or documentation.

## 1. Mission

Build **Skill.md-native** into a cross-registry, runtime-verified trust and evaluation layer for Agent Skills / `SKILL.md` workflows.

The system MUST answer, with reproducible evidence:

1. What exact Skill artifact was evaluated?
2. Where did it come from and can its provenance be reproduced?
3. What code/instructions/resources did it contain?
4. What runtime, agent harness, model and policy executed it?
5. What filesystem/process/network/tool/inference behavior occurred?
6. Did the Skill violate declared permissions or attempt credential/control-plane abuse?
7. Did it actually complete the task?
8. Is the result reproducible across agents, runtimes and models?
9. What did the run cost in latency, tokens, money and compute resources?
10. Can every ranking claim be traced back to immutable evidence?

This repository is **not** primarily another Skill marketplace. Discovery is an input. The product moat is the cross-registry **evidence + evaluation + security + compatibility + outcome ranking layer**.

## 2. Product thesis

Registries such as Skills.sh, GitHub, OpenAI plugin/skill distribution and other marketplaces can provide discovery and distribution. Existing connector/runtime vendors can provide OAuth, actions or execution. Skill.md-native sits above/between these layers and independently verifies what a Skill does.

Target pipeline:

```text
Registry / Repository / Plugin source
        ↓
Immutable ingestion + provenance
        ↓
Static inspection + dependency/SBOM/license evidence
        ↓
Isolated runtime execution
        ↓
Runtime evidence collection
        ↓
Security evaluator
        ↓
Task/outcome evaluator
        ↓
Skill × Agent × Runtime × Model compatibility matrix
        ↓
Versioned scoring policy + uncertainty
        ↓
Digest-addressed score/report artifacts
```

## 3. Canonical roadmap

GitHub Issues **#1–#6 are the canonical roadmap**. Do not create duplicate implementation Issues unless there is a genuinely independent new workstream.

- **#1 OpenShell hostile runtime + OCSF evidence**
- **#2 Governed free-tier/local inference broker**
- **#3 Cloudflare Sandbox / Dynamic Workers runtime**
- **#4 Cross-registry immutable provenance**
- **#5 Runtime security/adversarial benchmark**
- **#6 Compatibility matrix + evidence-first outcome ranking**

When implementing work:

1. Read the relevant canonical Issue.
2. Inspect existing implementation before adding another abstraction.
3. Add/modify tests with the implementation.
4. Update the canonical Issue checklist to reflect reality.
5. Never mark a live-runtime criterion complete from mocks alone.

## 4. Trust model

Treat every third-party Skill as an **untrusted executable supply-chain artifact**.

Assume a Skill may contain:

- prompt injection;
- code injection;
- malicious scripts or dependencies;
- undeclared network access;
- credential discovery/exfiltration attempts;
- persistence attempts;
- modification of `AGENTS.md`, `CLAUDE.md`, `.codex`, `.claude`, settings or other agent control files;
- sandbox escape attempts;
- misleading assertions designed to game evaluation;
- model-specific or agent-specific behavior.

A Skill's popularity, publisher reputation, stars, downloads or registry rank MUST NOT substitute for runtime verification.

## 5. Evidence invariant

Every important claim must be traceable through a chain similar to:

```text
ranking/report claim
    ↓
score artifact digest
    ↓
exact ScorePolicy
    ↓
raw metrics + uncertainty
    ↓
EvidenceBundle digest
    ↓
runtime/inference/security evidence objects
    ↓
RunSpec
    ↓
provenance digest
    ↓
immutable Skill artifact digest + source attestation
```

Evidence must be content-addressable where practical. Findings should reference immutable `evidence_id` values instead of relying only on copied text.

Never silently discard provenance, model, agent or runtime identifiers.

## 6. Immutable ingestion requirements

A benchmark artifact MUST NOT be pinned only to mutable names such as `main`, `master`, `HEAD` or `latest`.

For GitHub ingestion:

```text
mutable branch/tag
    ↓ resolve
immutable commit SHA
    ↓
download exact archive
    ↓
extract only requested Skill subtree
    ↓
validate entrypoint
    ↓
content SHA-256
    ↓
provenance record
```

Provenance should preserve, where available:

- registry/source type;
- source URL;
- immutable commit/digest/hash;
- publisher/owner identity;
- retrieval timestamp;
- content SHA-256;
- entrypoint;
- license evidence, including missing/ambiguous states;
- dependency manifests/lockfiles;
- CycloneDX-compatible SBOM evidence;
- publisher consistency/signature status when the source exposes it.

Identical content from multiple registries should deduplicate by artifact digest while retaining all source attestations.

Adapters currently/strategically include:

- GitHub;
- Skills.sh where API/terms permit;
- OpenAI Plugin/Skill first-party metadata where accessible;
- future registries through the same provenance contract.

Do not scrape around access controls or invent undocumented endpoints.

## 7. Runtime strategy

### 7.1 NVIDIA OpenShell

OpenShell is the primary hostile-code/reference security runtime.

Required properties:

- deny-by-default outbound network;
- Landlock hard requirement by default where supported;
- explicit filesystem policy;
- explicit mutating network rules;
- L7 REST/MCP/JSON-RPC restrictions where supported;
- non-interactive execution;
- effective policy capture;
- gateway/sandbox/runtime attestation;
- OCSF process/network/finding evidence;
- filesystem before/after SHA-256 manifests and diff;
- stdout/stderr/exit status;
- fail-closed behavior when mandatory evidence is missing;
- runtime/image pin mismatch rejection.

OpenShell is evolving software. Pin versions and verify current official interfaces before changing CLI/schema assumptions.

### 7.2 Cloudflare Sandbox

Cloudflare Sandbox is the scalable cloud Linux backend.

Security invariant:

- Internet access is disabled by default.
- Allowed hosts are explicit.
- Provider credentials remain in the Worker/control plane.
- The sandbox receives only brokered capability/access, never raw upstream secrets.
- Capture cold/warm state, execution metadata, filesystem changes, egress events and resource/cost evidence when the platform exposes them.

Cloudflare Sandbox may require a paid Workers plan. Never label it permanently free unless current official pricing proves that claim.

### 7.3 Dynamic Workers

Use Dynamic Workers for lightweight Code Mode / JavaScript execution when full Linux is unnecessary.

Default to no global outbound network. Bind only the minimum required capabilities.

### 7.4 NVIDIA Enroot

Enroot is a performance/compatibility comparison backend, **not** the primary security boundary for hostile Skills. Do not represent it as equivalent isolation to OpenShell.

### 7.5 Fake runtime

Fake/deterministic runtimes exist to validate contracts and CI logic. Their results MUST be labeled deterministic/mock evidence and MUST NOT be presented as live sandbox verification.

## 8. Governed inference broker

The Agent/Sandbox should talk to one OpenAI-compatible local/control-plane endpoint rather than holding raw provider credentials.

Conceptual path:

```text
Skill / Claude Code / Codex
          ↓
Skill-native inference gateway
          ↓
policy + budget + capability routing
     ├── local/open-weight model
     ├── Groq official free plan
     ├── Gemini official free tier
     └── Cloudflare Workers AI official allocation
```

Only use:

- operator-owned credentials;
- documented official free tiers/credits;
- local/open-weight inference;
- explicitly authorized paid providers.

Never implement:

- credential scraping/discovery;
- shared stolen API keys;
- account farming;
- key/account rotation to bypass quotas;
- unauthorized token proxying;
- provider ToS circumvention.

The broker must record an inference receipt for every attempt, including at minimum:

- parent `run_id`;
- provider;
- model;
- quota class;
- request hash;
- input/output tokens;
- latency;
- estimated price/cost;
- normalized rate-limit/quota headers when available;
- error/fallback reason.

Provider capability metadata should cover tool calling, structured output, context length and privacy/data-use characteristics where they can be sourced reliably.

Provider/model fallback is allowed only under explicit policy. A benchmark-pinned provider/model must never silently change.

## 9. Credential isolation invariant

Raw upstream credentials MUST remain outside the untrusted Skill workspace.

Tests should attempt to read common environment variables and secret locations. Passing means the Skill cannot recover the raw secret value while still being able to use the explicitly brokered capability.

This invariant applies across OpenShell and Cloudflare backends.

## 10. EvidenceBundle contract

A runtime run should capture, where applicable:

- `run_id`;
- provenance digest;
- runtime backend/version/image digest;
- agent harness/version;
- provider/model;
- sandbox policy hash;
- commands;
- process events;
- network requests and denials;
- filesystem before/after + diff;
- inference receipts;
- stdout/stderr;
- tool calls;
- assertions;
- security findings;
- runtime metadata;
- effective policy;
- OCSF/raw structured events;
- resource/cost metadata.

Missing mandatory evidence must lower verification status or fail closed; it must not be silently treated as success.

## 11. Security evaluator and adversarial corpus

The evaluator must separate **task success** from **policy compliance**.

High/Critical violations are non-compensable. A Skill cannot offset credential exfiltration or sandbox-policy violations with high task accuracy.

Maintain matched benign/malicious cases for at least:

- undeclared network;
- allowed network;
- credential access/exposure;
- benign authentication discussion;
- agent-control-file mutation;
- normal workspace writes;
- prompt injection;
- code injection;
- persistence;
- sandbox-evasion attempts.

Executable synthetic Skills should be materializable and runnable through multiple runtime adapters.

Support hidden/seeded variants to reduce benchmark gaming.

MalSkillBench-compatible imports may be supported only where dataset/code licensing permits. Never copy restricted corpus content without permission.

Detector reporting should include at minimum:

- TP;
- FP;
- TN;
- FN;
- recall;
- false-positive rate;
- concrete evidence IDs for findings.

## 12. Compatibility matrix

Never silently pool results across confounders.

The minimum cell key is:

```text
Skill artifact digest
× Agent harness/version
× Runtime/version
× Model/provider
```

Examples of agents include Claude Code, Codex, OpenCode and other explicitly supported harnesses.

A cell should retain its sample count, score, uncertainty and security state.

Coverage reporting should expose which agents/runtimes/models have actually been tested, not imply universal compatibility from one successful configuration.

## 13. Scoring and ranking

Scoring MUST be recomputable from persisted evidence without rerunning the Skill.

Raw dimensions should remain visible even when an aggregate score exists.

Current target dimensions include:

- task success;
- assertion pass rate;
- reproducibility;
- security behavior;
- least privilege;
- cross-agent coverage;
- cross-runtime coverage;
- latency p50/p95;
- input/output tokens;
- token efficiency;
- estimated monetary cost;
- resource consumption where available;
- failure recovery.

Score weights MUST be versioned in `ScorePolicy`. Do not change weighting semantics without a policy version change.

Security gate rule:

```text
High/Critical runtime security violation
        ⇒ security_gate = fail
        ⇒ aggregate ranking cannot compensate for it
```

Expose statistical uncertainty. At minimum task success uses a confidence interval; assertion/reproducibility uncertainty should also be retained where implemented.

A single successful run is exploratory, not verified.

Verified status should require both adequate samples and multi-axis coverage according to a versioned verification policy.

## 14. Report/API requirements

Reports must expose both aggregate and raw dimensions.

At minimum a report should provide:

- compatibility cells;
- score/security state;
- sample counts;
- confidence intervals;
- coverage across agents/runtimes/models;
- provenance/evidence references;
- verification status and reason.

Machine-readable JSON is the primary contract. Human-facing dashboards can be added later without changing evidence semantics.

## 15. Verification states

Use these terms precisely:

### Implemented
Code and deterministic tests exist.

### Integration-verified
The integration has run against a real external service/source, such as live GitHub ingestion.

### Runtime-verified
A real OpenShell/Cloudflare runtime executed the fixture and produced persisted runtime evidence.

Do not collapse these states into one word such as "done" when reporting evidence quality.

## 16. CI strategy

Required CI layers:

### Unit CI
Runs on every PR and validates:

- Python unit tests;
- OpenShell policy compiler/controller contract;
- provider routing/policy/ledger;
- provenance/security/scoring/report contracts;
- Cloudflare TypeScript bridge typecheck/build contracts.

### Live public integration CI
May run on PRs when no secret is required. Example: ingest a public GitHub Skill, resolve the mutable branch to an immutable SHA, generate provenance and assert digest linkage.

### Account-backed runtime CI
Use `workflow_dispatch` or explicitly configured runners/secrets for OpenShell/Cloudflare. These jobs must fail rather than fabricate evidence when the required environment is absent.

Persist runtime evidence artifacts from successful live runs.

## 17. Definition of Done for an Issue

An Issue is complete only when all applicable items are true:

- implementation exists;
- deterministic/unit tests exist;
- relevant CI is green;
- docs/contracts are updated;
- evidence semantics are preserved;
- no mock result is represented as live verification;
- canonical Issue checklist matches actual state.

If a requirement needs external credentials/infrastructure, the implementation and executable live verification harness may be complete while the external run remains an environment-dependent verification state. State this explicitly.

## 18. Agent working rules

When an Agent works in this repo:

1. Read this `AGENTS.md` first.
2. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/EVALUATION_CONTRACT.md` and the relevant canonical Issue.
3. Inspect existing code before introducing new abstractions.
4. Prefer extending shared evidence/provenance/runtime contracts over backend-specific one-offs.
5. Preserve backward-compatible evidence whenever practical.
6. Never weaken deny-by-default or credential-isolation defaults merely to make a test pass.
7. Never add real API keys, access tokens or secrets to the repository, fixtures, logs, Issues or PR text.
8. Keep official free-tier support policy-compliant; do not build quota-evasion mechanisms.
9. Add tests for every security-sensitive behavior.
10. Run/review CI after changes.
11. Update canonical Issue status and PR description after substantial implementation changes.
12. If current official APIs differ from assumptions, update the adapter and documentation rather than emulating obsolete behavior.
13. Fail closed when evidence required for a "verified" claim cannot be obtained.

## 19. Architecture invariants

Do not violate these without an explicit architecture decision:

- **Immutable artifact first**: runtime evaluation references pinned content.
- **Evidence before ranking**: ranking never invents missing runtime facts.
- **Security is non-compensable**: severe policy violations dominate score.
- **No silent confounder pooling**: agent/runtime/model remain explicit.
- **Secrets stay outside Skills**: capabilities are brokered.
- **Deny by default**: network and privileges are opt-in.
- **Mocks are not live evidence**.
- **Official/free/local resources only**: no quota or credential abuse.
- **Content-addressed traceability**: provenance, evidence and score artifacts should be digest-linked.
- **Recomputable ranking**: persisted evidence is sufficient to regenerate scores.

## 20. Immediate repository objective

The implemented MVP from PR #7 is merged to `main`. Keep `main` stable and advance verification quality without overstating evidence.

Current priority order:

```text
stable merged MVP
        ↓
account-backed OpenShell execution
        ↓
account-backed Cloudflare execution
        ↓
persist immutable runtime evidence
        ↓
measure live adversarial detector quality
        ↓
upgrade eligible compatibility cells from implemented/integration-verified to runtime-verified
```

Open Issues #1, #2, #3, and #5 are intentionally retained as environment-backed runtime-verification gates. Do not close them from mocks, typechecks, contract tests, or merge status alone. When real runtime evidence becomes available, persist it first, link it to immutable provenance and exact runtime/model/policy metadata, then update the corresponding Issue and verification state.

## 21. Success criterion

The MVP succeeds when a reviewer can start from a ranked Skill and independently answer:

> **Why is this Skill ranked here, exactly what artifact ran, under which Agent/Runtime/Model/policy, what did it do at runtime, what evidence proves that, and can the result be reproduced?**

If the system cannot answer that chain without hidden assumptions, the work is not complete.

<!-- BEGIN SHARED RUNTIME IDENTITY -->
## Shared runtime identity and dual-forge preflight
Canonical contract: `ed3c/skills-shared/skills/dual-forge-repository-loop/references/runtime-identity-contract.md`.
Before mutating delivery state, classify runtime from evidence: `CHATGPT_GITHUB_CONNECTOR | GITHUB_ACTIONS | CLAUDE_CODE_LOCAL | CODEX_CLI_LOCAL | CHATGPT_DESKTOP_WORKTREE | UNKNOWN`.
Connector ≠ Actions ≠ local worktree. Local claims require observed checkout/remotes/branch/HEAD; Forgejo requires a resolved local binding; Desktop requires an actually created worktree. `UNKNOWN` fails closed. Runtime, model family, and forge authority are separate. One mutable branch has one writer; runtime/HEAD changes require evidence rebinding.
Dual-forge order: `runtime bind → GitHub ingress → local/Forgejo issue+worktree → verified Forgejo PR → local main → GitHub reconciliation → exact-head Actions → GitHub publication`.
Three qualifying failures trigger fresh diagnosis + new worktree; no fourth blind patch.
<!-- END SHARED RUNTIME IDENTITY -->
