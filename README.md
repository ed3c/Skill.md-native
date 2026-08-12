# Skill.md-native

Runtime-verified evidence, security, compatibility, and outcome ranking for Agent Skills across registries.

> **Coding/AI Agents:** read [`AGENTS.md`](./AGENTS.md) before making changes. It is the canonical product requirements, security invariants, roadmap, evidence contract, CI rules, and Definition of Done for this repository.

## Mission

Every third-party `SKILL.md` package is treated as an untrusted executable supply-chain artifact. The project pins its origin, executes it through isolated runtimes, captures content-addressed evidence, evaluates security behavior, and ranks results without silently mixing Agent, Runtime, or Model confounders.

```text
Registry
  -> immutable provenance + SBOM
  -> RunSpec
  -> OpenShell | Cloudflare Sandbox | Dynamic Worker | Fake
  -> governed inference broker
  -> EvidenceBundle + evidence IDs
  -> security gate
  -> Skill x Agent x Runtime x Model matrix
  -> ScorePolicy
  -> digest-addressed report / score artifacts
```

## Immutable ingestion

### GitHub

```bash
skill-native ingest-github https://github.com/vercel-labs/agent-skills \
  --ref main \
  --skill-path skills/react-best-practices \
  --output .skill-native/artifacts/react-best-practices \
  --provenance-dir .skill-native/provenance
```

Mutable branch/tag input is resolved to a commit SHA before evaluation. The resulting provenance records content SHA-256, publisher/source attestations, license evidence, dependency manifests, and a deterministic provenance digest. `run_spec_from_provenance()` injects that digest into the generated `RunSpec`; every runtime carries it forward to `EvidenceBundle`.

### skills.sh

`SkillsShAdapter` uses the documented `skills.sh/api/v1` API and requires an operator-owned `VERCEL_OIDC_TOKEN`. It supports search, detail, audit metadata, materialization, and immutable provenance. No UI scraping is used.

### OpenAI Plugin metadata

OpenAI currently documents the Plugin Directory product but not a public directory-catalog API. `JsonMetadataAdapter` therefore accepts only an operator-supplied, accessible first-party JSON manifest/export and pins its canonical digest; it does not scrape authenticated ChatGPT UI.

## Supply-chain evidence

`build_supply_chain_evidence()` records publisher consistency, explicit signature status, and a CycloneDX 1.6 SBOM digest derived from discovered dependency manifests. Missing signatures/licenses remain explicit evidence states rather than inferred trust.

## Governed inference broker

The OpenAI-compatible broker supports Groq, Gemini, Workers AI, and local endpoints. It provides local-only routing, provider pinning, operator request/token/cost ceilings, normalized rate-limit evidence, provider capability/privacy metadata, and an append-only receipt ledger.

```bash
skill-native serve-gateway examples/providers.yaml \
  --local-only \
  --receipt-ledger .skill-native/inference.jsonl \
  --max-daily-requests 100 \
  --max-daily-tokens 100000
```

Requests may include `skill_native_run_id`; runtime execution can then materialize matching ledger receipts directly into `EvidenceBundle.inference`. Provider credentials remain operator-owned. Credential harvesting, account rotation, quota bypass, or unauthorized key pooling are outside the project contract.

## Runtimes

### NVIDIA OpenShell

OpenShell is the hostile-code reference runtime. The adapter provides deny-by-default network policy, hard Landlock, filesystem manifests, OCSF capture, effective-policy capture, gateway/runtime attestation, provider attachment, raw-credential non-exposure probing, and declared runtime/image mismatch rejection. The controller fails closed when mandatory evidence is absent.

Account-backed validation is exposed through `.github/workflows/integration.yml`. A real OpenShell run is never substituted with a mock claim.

### Cloudflare Sandbox

`cloudflare/worker/` is a deployable `@cloudflare/sandbox` Worker bridge. Public internet is disabled by default, allowed hosts are explicit, outbound handlers record egress decisions, and credentials can be injected in trusted Worker code rather than exposed to the container. The Python `CloudflareHttpClient` normalizes cold/warm state, filesystem changes, command results, egress evidence, and execution metadata into the common `EvidenceBundle`.

Cloudflare Sandbox requires an eligible Cloudflare account/plan. The integration workflow therefore requires operator-owned Cloudflare credentials rather than assuming a permanent free allocation.

### Dynamic Workers

`cloudflare/dynamic-worker/` uses the Worker Loader binding for lightweight Code Mode. Every `load()` execution creates an isolated Worker with `globalOutbound: null`, blocking `fetch()` and `connect()` unless the parent deliberately supplies a capability.

### Enroot

Enroot remains a performance/compatibility reference only; it is not used as the primary hostile-code security boundary.

## Adversarial benchmark

`skill-native materialize-fixtures <dir>` produces executable synthetic Skill packages covering benign writes, prompt/code injection, credential access, undeclared egress, persistence/control-file mutation, and sandbox-boundary probes. Hidden variants use seeded case IDs to reduce hard-coded benchmark behavior. A MalSkillBench-compatible JSONL importer keeps the external corpus and its licensing separate from this repository.

Every derived security finding references an immutable `evidence_id`. High/Critical violations trip a non-compensable security gate even when the task itself succeeds.

## Ranking and reports

`ScorePolicy v0.4` versions the aggregate weights:

- correctness: 70%
- reproducibility: 20%
- least privilege: 10%
- any High/Critical security gate failure: aggregate score = 0

Latency, tokens, estimated cost, recovery, denied-network counts, and other measurements remain visible as raw dimensions. Reports add Wilson confidence intervals and multi-axis verification: a Skill is not globally `verified` from repeated runs in one cell; the default policy requires coverage across at least two Agents, two Runtimes, and two Models with sufficient samples in every cell.

```bash
skill-native build-report matrix-input.jsonl --output report.json
```

## Verification

`.github/workflows/unit.yml` verifies the Python evidence/evaluation core and type-checks both Cloudflare runtime projects. `.github/workflows/integration.yml` performs a live public GitHub ingestion on pull requests and exposes explicit dispatch jobs for real OpenShell and Cloudflare account-backed validation.

The project distinguishes three states:

- **implemented**: code + deterministic tests exist;
- **integration-verified**: a real external service/runtime produced evidence;
- **runtime-verified**: the evidence bundle satisfies the security/runtime assertions for that exact pinned artifact.

This distinction prevents a green mock test from being represented as proof that an external sandbox or provider was actually exercised.
