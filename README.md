# Skill.md-native

Runtime-verified evidence, security, compatibility, and outcome ranking for Agent Skills across registries and execution domains.

> **Coding/AI Agents:** read [`AGENTS.md`](./AGENTS.md) before changing code, Issues, CI, runtime adapters, evaluation logic, or documentation. The cross-domain execution contract is in [`docs/HARNESS_KERNEL.md`](./docs/HARNESS_KERNEL.md), Coding Agent trust boundaries are in [`docs/CODING_AGENT_HARNESS.md`](./docs/CODING_AGENT_HARNESS.md), and evaluator authority/Evidence Graph/replay/scorecard contracts are in [`docs/RUN_ARTIFACTS.md`](./docs/RUN_ARTIFACTS.md).

## Mission

Every third-party `SKILL.md` package is treated as an untrusted executable supply-chain artifact. The project pins its origin, executes it through isolated runtimes, captures content-addressed evidence, evaluates security and task outcomes, and ranks results without silently mixing Agent, Runtime, Model, Skill, or evaluator confounders.

```text
Registry / Repository / Plugin source
  -> immutable Skill provenance + SBOM
  -> RunSpec
  -> HarnessManifest + DomainAdapter
  -> explicit EvaluatorAuthority sidecar
  -> digest-addressed HarnessPlan
  -> OpenShell | Cloudflare Sandbox | Dynamic Worker | Fake
  -> governed inference broker
  -> EvidenceBundle + collector attestation + evidence IDs
  -> deterministic verifiers + non-compensable security gate
  -> digest-addressed HarnessVerdict
  -> EvidenceGraph + ReplayManifest + LogicalTrace
  -> evidence-first OutcomeScorecard
  -> Skill x Agent x Runtime x Model compatibility matrix
  -> digest-addressed reports and ranking artifacts
```

## Cross-domain Harness Kernel

The v0.1 Harness Kernel makes the portable evaluation unit explicit:

```text
SKILL.md
+ harness.yaml
+ immutable RunSpec
+ runtime capability/evidence profile
+ executable assertions
+ EvidenceBundle
+ HarnessVerdict
```

The manifest vocabulary covers Coding, Browser, Android, Desktop, SRE, Documents, Voice, Robotics, and custom domains. The implemented adapters are:

```text
coding.command.v1
coding.agent.v1
```

`coding.command.v1` is the deterministic command vertical slice. `coding.agent.v1` adds a trusted wrapper, structured agent events, workspace change policy, deterministic test evidence, bounded output, task delivery over stdin, and a digest-addressed `CodingAgentReceipt`. Live Codex, Gemini CLI, Qwen Code, OpenHands, Browser, Android, and other domain execution are not implied by the vocabulary alone.

Unknown adapters, unsupported capabilities, unsupported evidence, weaker policies, mutable Skill references, missing provenance, malformed receipts, and budget overruns fail closed.

```bash
skill-native validate-harness examples/harnesses/coding/harness.yaml

skill-native plan-harness \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml

skill-native validate-harness examples/harnesses/coding-agent/harness.yaml

skill-native plan-harness \
  examples/harnesses/coding-agent/harness.yaml \
  examples/harnesses/coding-agent/run.fake.yaml
```

The committed JSON Schemas are under [`schemas/`](./schemas). Schema generation is deterministic and CI compares generated outputs with committed files to prevent drift.

A passing fake-runtime verdict is **implemented deterministic contract evidence**, not live model, sandbox, or cross-agent verification.

## Evaluator authority and Run Artifact Bundle

A package-supplied test command or assertion is not automatically trusted. `skill-native-run-artifacts` requires a separate `EvaluatorAuthority` sidecar that pins the evaluator repository/artifact and binds it to the exact `manifest_digest` compiled into the plan.

```text
EvaluatorAuthority
+ HarnessPlan
+ EvidenceBundle
+ HarnessVerdict
        │
        ▼
RunArtifactBundle
├── EvidenceGraph
├── ReplayManifest
├── LogicalTrace
└── OutcomeScorecard
```

The builder validates the plan/verdict digest chain and continuity across run, manifest, provenance, runtime, evidence, and verdict before deriving any artifact. Mutable evaluator refs such as `main`, `master`, `HEAD`, or `latest` are rejected.

```bash
skill-native-run-artifacts build \
  --authority examples/run-artifacts/authority.json \
  --plan examples/run-artifacts/plan.json \
  --evidence examples/run-artifacts/evidence.json \
  --verdict examples/run-artifacts/verdict.json \
  --output /tmp/run-artifacts
```

Mandatory evidence coverage is calculated from trusted collector attestation, not from empty default fields. Exact replay requires snapshot capability, a captured snapshot digest, and a SHA-256-pinned runtime image. Logical trace IDs are deterministic, while timing remains explicitly `not-captured` until a real OpenTelemetry/OpenInference exporter supplies timing evidence.

The `evidence-first-v1` scorecard keeps these failures non-compensable:

```text
High/Critical finding or failed security gate
failed HarnessVerdict
missing mandatory evidence
failed verifier
```

See [`docs/RUN_ARTIFACTS.md`](./docs/RUN_ARTIFACTS.md) for the complete trust model, graph relationships, replay classes, score policy, CLI, schemas, and verification vocabulary.

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

A `harness.yaml` licensing block is a declaration only. It never overrides source license files, model/dataset licenses, dependency evidence, or provenance results.

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

Enroot remains a performance/compatibility reference only; it is not used as the primary hostile-code security boundary. The Harness Kernel intentionally has no Enroot capability/evidence profile yet, so Harness compilation fails closed for that backend.

### Fake runtime

`FakeRuntime` validates contracts and CI logic only. Its evidence records `verification_state=deterministic-mock`; it does not establish live runtime behavior.

## Adversarial benchmark

`skill-native materialize-fixtures <dir>` produces executable synthetic Skill packages covering benign writes, prompt/code injection, credential access, undeclared egress, persistence/control-file mutation, and sandbox-boundary probes. Hidden variants use seeded case IDs to reduce hard-coded benchmark behavior. A MalSkillBench-compatible JSONL importer keeps the external corpus and its licensing separate from this repository.

Every derived security finding references an immutable `evidence_id`. High/Critical violations trip a non-compensable security gate even when the task itself succeeds. The Harness Kernel and Run Artifact scorecard preserve the same rule.

## Ranking and reports

`ScorePolicy v0.4` versions the compatibility-matrix aggregate weights:

- correctness: 70%
- reproducibility: 20%
- least privilege: 10%
- any High/Critical security gate failure: aggregate score = 0

The Run Artifact `evidence-first-v1` scorecard is a per-run prerequisite layer. It determines whether a run is eligible to enter cross-run ranking based on mandatory evidence, verifier success, security, and replay classification. It does not replace multi-cell statistical ranking.

Latency, tokens, estimated cost, recovery, denied-network counts, and other measurements remain visible as raw dimensions. Reports add Wilson confidence intervals and multi-axis verification: a Skill is not globally `verified` from repeated runs in one cell; the default policy requires coverage across at least two Agents, two Runtimes, and two Models with sufficient samples in every cell.

```bash
skill-native build-report matrix-input.jsonl --output report.json
```

## Verification

`.github/workflows/unit.yml` defines Python regression, Coding Agent fixture, Run Artifact fixture, schema-drift, and Cloudflare TypeScript contract checks. `.github/workflows/integration.yml` performs a live public GitHub ingestion on pull requests and exposes explicit dispatch jobs for real OpenShell and Cloudflare account-backed validation.

The project distinguishes four states:

- **implemented**: code, schemas, and deterministic tests exist;
- **integration-verified**: a real external adapter/service produced persisted evidence;
- **runtime-verified**: the pinned artifact ran in the declared isolated runtime and all required assertions passed;
- **cryptographically attested**: a trusted signing identity covered the relevant digests.

A configured workflow is not a passing workflow. Jobs that fail to start because of repository/account infrastructure are recorded as blocked infrastructure, not test evidence.

## License

The repository source is licensed under the [MIT License](./LICENSE). Model weights, datasets, third-party Skills, generated artifacts, and dependencies may carry separate licenses and must be evaluated independently.
