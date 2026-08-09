# Skill.md-native

Runtime-verified evidence, evaluation, security, compatibility, and outcome ranking for Agent Skills across registries.

## Mission

This repository treats every third-party `SKILL.md` package as an untrusted executable supply-chain artifact. It ingests skills from multiple registries, executes them in isolated runtimes, captures evidence, evaluates behavior, and ranks outcomes across agent/runtime combinations.

## Core pipeline

```text
Registry Sources
  -> Ingestion + provenance
  -> Static inspection
  -> Runtime sandbox execution
  -> Evidence capture
  -> Security evaluation
  -> Compatibility matrix
  -> Outcome scoring
  -> Ranked evidence ledger
```

## Runtime strategy

- **NVIDIA OpenShell**: primary security/reference runtime. Declarative network/filesystem policy, credential isolation, and structured observability.
- **Cloudflare Sandboxes / Dynamic Workers**: cloud runtime backend for scalable and low-cost experiments.
- **NVIDIA Enroot**: performance-oriented compatibility backend only. It is intentionally not treated as the main security boundary for untrusted skills.
- Additional runtimes can implement the backend interface without changing the evaluation contract.

## OpenShell implementation

The OpenShell adapter is implemented around the current non-interactive CLI surface:

- compile a `RunSpec` into OpenShell policy schema v1;
- enforce `deny-by-default` networking;
- default legacy `allowed_hosts` to read-only REST access;
- require explicit `network_rules` for mutating access;
- use Landlock `hard_requirement` by default;
- create a named sandbox and capture machine-readable sandbox metadata;
- enable OCSF JSON export;
- execute one-shot commands with `openshell sandbox exec`;
- capture the effective policy, sandbox logs, process/network/finding OCSF events, stdout/stderr, exit status, and policy digest;
- fail closed when mandatory evidence channels are missing.

OpenShell remains alpha software, so production evaluation should pin the CLI/runtime version and sandbox image digest.

### CLI

Validate a run specification:

```bash
skill-native validate examples/run.openshell.yaml
```

Preview the exact OpenShell policy before executing anything:

```bash
skill-native compile-openshell-policy examples/run.openshell.yaml
```

Run a command in an OpenShell sandbox and emit normalized evidence JSON:

```bash
skill-native run-openshell examples/run.openshell.yaml -- /bin/sh -lc 'echo runtime-ok'
```

The adapter refuses to emit a successful evidence bundle if effective policy, sandbox logs, or OCSF JSON evidence cannot be collected.

## LLM inference strategy

The runtime uses a provider router with explicit quotas and policy. Only official, user-authorized free tiers or local/open-weight inference are eligible for the default `free` pool. No credential harvesting, account rotation, quota bypass, or unauthorized proxying is allowed.

Initial candidates:

- Groq Free Plan
- Gemini Developer API Free Tier
- Cloudflare Workers AI free daily allocation
- local/self-hosted OpenAI-compatible endpoints

The router records provider, model, latency, token usage, rate-limit metadata, and failure reason for every call so model availability cannot silently bias benchmark results.

## Evidence contract

Every run produces an immutable run manifest containing:

- skill source and commit/digest
- registry and publisher metadata
- runtime backend + image digest
- agent harness and version
- model provider/model
- sandbox policy hash
- filesystem diff
- process/command trace
- network destinations and denied requests
- stdout/stderr
- tool calls
- exit status
- task assertions
- latency/token/cost accounting
- security findings
- reproducibility metadata

## Ranking dimensions

1. Task success
2. Reproducibility
3. Security behavior
4. Permission minimization
5. Cross-agent compatibility
6. Cross-runtime compatibility
7. Latency
8. Token efficiency
9. Monetary cost
10. Failure recovery

A skill is never ranked highly from stars/downloads alone.

## Status

OpenShell runtime adapter v0 is implemented with deterministic unit tests. Live OpenShell integration still requires a host/gateway with OpenShell installed; CI can validate the compiler and controller behavior without privileged runtime access.

See `docs/ARCHITECTURE.md`, `docs/EVALUATION_CONTRACT.md`, and GitHub Issues for the implementation roadmap.
