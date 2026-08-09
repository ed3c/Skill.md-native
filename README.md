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

Bootstrap phase. See `docs/ARCHITECTURE.md`, `docs/EVALUATION_CONTRACT.md`, and GitHub Issues for the implementation roadmap.
