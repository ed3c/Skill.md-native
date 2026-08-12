# Architecture

## Goal

Build a cross-registry trust and runtime-validation layer for Agent Skills. The system must answer not only whether a skill can be installed, but whether it behaves correctly, safely, reproducibly, and portably under real agent execution.

## Data flow

```text
[Registry adapters]
      |
      v
[Normalized Skill Artifact]
      |
      +--> [Provenance + license + dependency inspection]
      |
      v
[Static analyzers]
      |
      v
[HarnessManifest + immutable RunSpec]
      |
      v
[Harness compiler]
      |
      +--> domain adapter registry
      +--> runtime capability/evidence negotiation
      +--> policy and budget checks
      |
      v
[Digest-addressed HarnessPlan]
      |
      v
[Execution planner]
      |
      +--> OpenShell backend
      +--> Cloudflare Sandbox backend
      +--> Enroot compatibility backend
      +--> future backends
      |
      v
[Agent Harness]
  Claude Code / Codex / OpenCode / compatible harnesses
      |
      v
[LLM Provider Router]
  official free tier | local/open-weight endpoint
      |
      v
[Evidence collectors]
  command / process / fs / network / tool / model / assertion traces
      |
      v
[Deterministic verifier + security evaluator]
      |
      v
[Digest-addressed HarnessVerdict]
      |
      v
[Evidence Ledger + Compatibility Matrix + Outcome Ranking]
```

## Cross-domain Harness Kernel

`SKILL.md` remains the human/agent instruction entrypoint. It is not the complete executable evaluation contract. A portable harness package combines:

```text
SKILL.md
+ harness.yaml
+ immutable RunSpec
+ trusted domain adapter
+ trusted runtime capability/evidence profile
+ deterministic assertions
+ EvidenceBundle
+ HarnessVerdict
```

The v0.1 manifest vocabulary recognizes Coding, Browser, Android, Desktop, SRE, Documents, Voice, Robotics, and custom domains. Recognition does not imply implementation: an unknown or unregistered domain adapter fails closed.

The compiler rejects execution before provisioning when any of these conditions hold:

- the Skill is not linked to immutable provenance;
- the selected runtime is outside the manifest allowlist;
- required runtime capabilities are unavailable;
- requested evidence cannot be collected by the trusted adapter;
- effective network, filesystem, or secret policy is weaker or different;
- the RunSpec exceeds manifest budgets;
- the verifier type is unknown;
- replay requires snapshot/restore but the runtime does not support it.

A plan includes the complete RunSpec, exact manifest and policy digests, compiled typed action, runtime capability profile, evidence requirements, verifiers, and a self-validating plan digest. A verdict preserves plan, evidence, provenance, runtime, security, and failure continuity through its own digest.

The detailed extension and trust contract is in [`HARNESS_KERNEL.md`](./HARNESS_KERNEL.md).

## Trust boundaries

### Untrusted

- Registry metadata
- Skill instructions
- Package-supplied `harness.yaml` claims
- Scripts and binaries bundled by skills
- Downloaded dependencies
- Runtime-generated code
- Agent-generated shell commands
- Remote responses returned to a skill

### Trusted computing base

Keep this deliberately small:

- immutable ingestion/provenance code
- approved HarnessManifest/operator policy overlay
- domain adapter registry
- runtime backend controller
- runtime capability and evidence profiles
- sandbox policy compiler
- evidence collector outside the sandbox
- deterministic evaluator assertions
- security evaluator
- artifact hashing/signing code
- provider credential injector

A package-supplied manifest requests capabilities. It cannot grant itself a runtime, policy exception, secret, evidence exemption, or verifier implementation.

## Runtime backend contract

Each backend implements:

```text
prepare(run_spec) -> sandbox_id
execute(sandbox_id, command, env_ref) -> execution_id
collect(execution_id) -> evidence_bundle
snapshot(sandbox_id) -> snapshot_ref
restore(snapshot_ref) -> sandbox_id
destroy(sandbox_id)
```

The current Python adapter contract exposes prepare, execute, collect, and destroy. Snapshot/restore remains an explicit capability and must not be claimed until implemented by the adapter.

A backend capability descriptor records whether it supports:

- kernel or VM isolation
- network deny-by-default
- L7 HTTP policy
- filesystem policy
- secret injection without exposing raw credentials
- syscall/process telemetry
- network telemetry
- snapshot/rollback
- persistent filesystem
- GPU
- nested containers
- deterministic image pinning

Each backend also declares an evidence profile. Empty output is valid evidence only when the trusted collector records that the evidence channel was captured. Unsupported evidence is rejected at compile time rather than represented by an empty placeholder.

## OpenShell backend

OpenShell is the primary reference backend because it exposes explicit sandbox policy and outbound controls suitable for validating untrusted agents. The implementation should pin OpenShell versions because the project is alpha and behavior may change.

Required evidence:

- applied policy and hash
- denied network requests
- allowed network requests
- commands/processes
- sandbox logs/OCSF records when available
- runtime version and image digest

## Cloudflare backend

Use Cloudflare Sandboxes for scalable cloud execution and Dynamic Workers / `@cloudflare/shell` for lightweight code-mode tests where a full Linux environment is unnecessary.

Cloudflare-specific experiments should measure:

- cold/warm start
- persistence/snapshot behavior
- outbound credential injection
- filesystem changes
- egress destinations
- active CPU/runtime consumption

Do not assume Cloudflare is permanently free. Treat free allocations and temporary-account capabilities as discoverable quota sources with explicit expiry/limit metadata.

## Enroot backend

Enroot is a compatibility/performance backend, not a primary hostile-code isolation boundary. Enroot's own design intentionally provides little isolation. Use it to answer questions such as:

- Does the skill rely on Docker-specific behavior?
- Does it run in an unprivileged user namespace?
- What overhead does stronger isolation add?

Untrusted network access should therefore be additionally constrained outside Enroot or the test must be marked `unsafe_for_adversarial_skill=true`.

The Harness Kernel intentionally has no Enroot capability/evidence profile in v0.1; compilation therefore fails closed until a truthful adapter profile is implemented.

## Inference router

The provider router borrows the architecture of an API gateway/token broker, but never harvests or rotates third-party credentials to bypass quotas.

```text
Agent -> local OpenAI-compatible gateway
      -> policy engine
      -> provider adapter
           -> Groq free plan
           -> Gemini free tier
           -> Cloudflare Workers AI allocation
           -> local OpenAI-compatible model
```

Provider policy inputs:

- model capability requirements
- remaining official quota
- data-retention/privacy constraints
- context length
- tool/function calling support
- expected cost
- benchmark reproducibility constraints

Every request stores a normalized inference receipt:

```json
{
  "provider": "...",
  "model": "...",
  "request_hash": "...",
  "input_tokens": 0,
  "output_tokens": 0,
  "latency_ms": 0,
  "price_usd": 0,
  "quota_class": "free|paid|local",
  "rate_limit_headers": {},
  "error": null
}
```

## Registry layer

Adapters should be independent modules. Initial targets:

- GitHub repositories containing Agent Skills
- skills.sh metadata/API where permitted
- OpenAI Plugin/Skill metadata where accessible
- other public registries with stable APIs or documented pages

Store the original source URL plus immutable Git commit/digest. Never benchmark an unpinned mutable `main` reference as if it were reproducible.

## Ranking model

Ranking is evidence-first and multi-dimensional. Keep raw measurements separate from policy weights.

Suggested normalized vector:

```text
success
reproducibility
security
least_privilege
agent_compatibility
runtime_compatibility
latency
token_efficiency
cost
recovery
```

Published scores should include confidence and sample count. A single successful run cannot establish compatibility.

## Anti-gaming requirements

- hidden evaluation tasks
- repeated runs
- clean-room run plus warm-state run
- registry popularity excluded from correctness/security score
- model/provider recorded as a confounder
- runtime backend recorded as a confounder
- detect network-based benchmark answer retrieval
- distinguish `task_success` from `policy_violation`
- keep private evaluator logic outside the untrusted workspace
- reject manifest-defined verifier types that the trusted kernel has not registered

## Initial implementation milestones

1. Canonical run/evidence schemas
2. Local fake runtime for deterministic unit tests
3. OpenShell adapter
4. Provider router with official free-tier adapters
5. GitHub Skill ingestion
6. Static scanner
7. Runtime trace collector
8. Evaluator + ranking prototype
9. Cloudflare backend
10. Cross-agent compatibility matrix
11. Malicious-skill benchmark integration
12. Evidence viewer/dashboard
13. Cross-domain HarnessManifest, HarnessPlan, and HarnessVerdict contracts
14. Coding Agent adapter
15. Browser adapter
16. Android/device adapter
17. Desktop/SRE/Documents adapters
18. Voice/robotics adapters
