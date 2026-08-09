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
[Evaluator]
      |
      v
[Evidence Ledger + Compatibility Matrix + Outcome Ranking]
```

## Trust boundaries

### Untrusted

- Registry metadata
- Skill instructions
- Scripts and binaries bundled by skills
- Downloaded dependencies
- Runtime-generated code
- Agent-generated shell commands
- Remote responses returned to a skill

### Trusted computing base

Keep this deliberately small:

- runtime backend controller
- sandbox policy compiler
- evidence collector outside the sandbox
- evaluator assertions
- artifact hashing/signing code
- provider credential injector

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

A backend capability descriptor records whether it supports:

- kernel or VM isolation
- network deny-by-default
- L7 HTTP policy
- filesystem policy
- secret injection without exposing raw credentials
- syscall/process telemetry
- snapshot/rollback
- persistent filesystem
- GPU
- nested containers
- deterministic image pinning

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
