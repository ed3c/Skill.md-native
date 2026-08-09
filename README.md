# Skill.md-native

Runtime-verified evidence, evaluation, security, compatibility, and outcome ranking for Agent Skills across registries.

## Mission

This repository treats every third-party `SKILL.md` package as an untrusted executable supply-chain artifact. It ingests skills from multiple registries, executes them in isolated runtimes, captures evidence, evaluates behavior, and ranks outcomes across agent/runtime/model combinations.

## Core pipeline

```text
Registry Sources
  -> Immutable ingestion + provenance
  -> Static inspection
  -> Runtime sandbox execution
  -> Evidence capture
  -> Security evaluation
  -> Compatibility matrix
  -> Outcome scoring
  -> Ranked evidence ledger
```

## Immutable GitHub ingestion

Resolve a mutable GitHub ref to an immutable commit, materialize only the requested Skill subtree, and persist a digest-addressed provenance record:

```bash
skill-native ingest-github https://github.com/OWNER/REPO \
  --ref main \
  --skill-path path/to/skill \
  --output .skill-native/artifacts/demo \
  --provenance-dir .skill-native/provenance
```

The provenance record contains the resolved commit SHA, deterministic content SHA-256, source/publisher attestation, license evidence, dependency manifests, and a provenance digest. `RunSpec.skill.provenance_digest` and `EvidenceBundle.provenance_digest` are reserved for linking runtime evidence to that immutable record.

## Governed inference gateway

The gateway supports Groq, Gemini, Cloudflare Workers AI, and local OpenAI-compatible endpoints while keeping provider credentials outside the Skill workspace. It can enforce a strict local-only policy and independent operator budgets:

```bash
skill-native serve-gateway examples/providers.yaml \
  --local-only \
  --receipt-ledger .skill-native/evidence/inference.jsonl \
  --max-daily-requests 100 \
  --max-daily-tokens 100000
```

A sandboxed Agent may include `skill_native_run_id` in its `/v1/chat/completions` request. The returned receipt and append-only ledger entry carry that run id, allowing inference evidence to be joined to the parent runtime run without revealing raw upstream credentials.

No credential harvesting, account rotation, quota bypass, or unauthorized proxying is permitted by project policy.

## Runtime strategy

- **NVIDIA OpenShell**: primary hostile-code security/reference runtime. Deny-by-default networking, Landlock, OCSF evidence, filesystem diff, and gateway/runtime attestation.
- **Cloudflare Sandbox / Dynamic Workers**: cloud runtime path with normalized evidence and explicit resource/cost accounting.
- **NVIDIA Enroot**: compatibility/performance backend only; not treated as a primary hostile-code isolation boundary.
- **Fake runtime**: deterministic contract and CI testing.

## OpenShell implementation

The OpenShell adapter currently:

- compiles `RunSpec` into OpenShell policy schema v1;
- enforces deny-by-default networking and hard Landlock by default;
- requires explicit network rules for mutating access;
- captures sandbox/gateway metadata, effective policy, logs, OCSF events, filesystem before/after manifests, stdout/stderr, exit status, and policy digest;
- fails closed when mandatory evidence channels are unavailable.

Live denied-egress, L7 denial, and credential non-exposure fixtures remain open until a real OpenShell gateway is available.

## Security benchmark

`security_benchmark.py` contains matched synthetic malicious/benign evidence fixtures and reports true positives, false positives, true negatives, false negatives, recall, and false-positive rate. These deterministic fixtures validate the evaluator itself; they do not substitute for live malicious Skill execution or MalSkillBench integration.

The evaluator currently detects denied undeclared network access, agent-control file mutation, and credential exposure markers. High/critical findings form a non-compensable security gate.

## Evidence and ranking

Raw measurements are kept separate from aggregate score. Current scoring dimensions include task success, assertion pass rate, reproducibility rate, least privilege, security violations, latency p50/p95, input/output tokens, token efficiency, estimated cost, and recovery success.

Compatibility cells are keyed by Skill × Agent × Runtime × Model so model/runtime confounders are not silently pooled. Popularity, stars, downloads, and publisher reputation are metadata only and do not increase correctness or security scores.

## Status

Active implementation is tracked in GitHub Issues and Draft PR #7. Deterministic/unit paths are CI-verified. Account-backed OpenShell/Cloudflare claims remain explicitly open until live runtime evidence exists.
