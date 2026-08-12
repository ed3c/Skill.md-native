# Cross-domain Harness Kernel v0.1

## Status

This document defines the first implemented cross-domain Harness Kernel contract in Skill.md-native.

The implemented vertical slice covers:

- versioned `harness.yaml` manifests;
- an explicit domain-adapter registry;
- deterministic compilation into a digest-addressed execution plan;
- runtime capability and evidence-capability negotiation;
- deterministic verifier primitives;
- provenance, runtime, evidence, and security continuity checks;
- digest-addressed verdicts;
- a reference `coding.command.v1` adapter;
- deterministic `FakeRuntime` execution for contract CI.

Only the Coding command adapter and deterministic fake execution are implemented by this increment. Browser, Android, Desktop, SRE, Documents, Voice, Robotics, orchestration, and production telemetry remain follow-on adapters. Their names are part of the versioned domain vocabulary, but they fail closed until an adapter is explicitly registered.

## Why a Harness Kernel is needed

`SKILL.md` alone describes instructions. It does not prove:

- which immutable artifact ran;
- which Agent, Model, Runtime, policy, and budget were used;
- whether the runtime possessed the capabilities the task depended on;
- whether required evidence was actually collected;
- whether the result passed deterministic assertions;
- whether severe security findings occurred;
- whether a report can be recomputed without rerunning the task.

The portable evaluation unit is therefore:

```text
SKILL.md
+ harness.yaml
+ immutable RunSpec
+ runtime capability profile
+ executable verifier checks
+ EvidenceBundle
+ HarnessVerdict
```

## Data flow

```text
Pinned Skill artifact + provenance digest
                 |
                 v
          HarnessManifest
                 |
                 +---- DomainAdapterRegistry
                 |
                 +---- RuntimeCapabilities
                 |
                 +---- Runtime evidence profile
                 |
                 v
          HarnessKernel.compile
                 |
                 v
     digest-addressed HarnessPlan
                 |
                 v
        trusted RuntimeAdapter
                 |
                 v
           EvidenceBundle
                 |
                 +---- provenance continuity
                 +---- runtime continuity
                 +---- mandatory evidence checks
                 +---- deterministic verifier checks
                 +---- non-compensable security gate
                 |
                 v
    digest-addressed HarnessVerdict
```

Compilation performs no LLM judgment. Unknown adapters, unsupported runtime capabilities, unsupported evidence kinds, policy mismatches, mutable Skill references, missing provenance, and excessive budgets are rejected before execution.

## Package layout

A future registry-ready Harness package should use this shape:

```text
my-skill/
├── SKILL.md
├── harness.yaml
├── assertions/
├── fixtures/
├── policies/
├── evals/
├── known-failures.md
└── LICENSE
```

The first executable example is under `examples/harnesses/coding/`.

## `harness.yaml` contract

The committed machine-readable source of truth is `schemas/harness.schema.json`.

### Identity

```yaml
identity:
  id: coding.skill-smoke
  version: "0.1.0"
  domain: coding
```

Supported domain identifiers are:

```text
coding
browser
android
desktop
sre
documents
voice
robotics
custom
```

A domain identifier does not imply implementation. The adapter named by `execution.adapter` must exist in the trusted adapter registry and must declare the same domain.

### Licensing declaration

```yaml
licensing:
  code: MIT
  models: []
  datasets: []
  dependencies: []
```

This is a package declaration, not trusted license evidence. Cross-registry provenance, detected license files, dependency manifests, SBOMs, model licenses, and dataset licenses remain the evidence source of truth. A declaration must never override contradictory provenance evidence.

### Environment and policy

```yaml
environment:
  allowed_runtimes: [fake]
  required_capabilities:
    - network_deny_by_default
    - filesystem_policy
    - brokered_secrets
  network: deny-by-default
  filesystem: ephemeral
  secrets: brokered
```

The compiler performs two independent checks:

1. The selected runtime must be in `allowed_runtimes`.
2. Its trusted capability profile must satisfy every `required_capabilities` entry.

The manifest policy must exactly match the effective `RunSpec.policy` for network, filesystem, and secrets. This prevents a caller from compiling a strict manifest and executing it with weaker settings.

Current runtime capabilities include:

```text
kernel_or_vm_isolation
network_deny_by_default
l7_http_policy
filesystem_policy
brokered_secrets
process_telemetry
network_telemetry
snapshot_restore
persistent_filesystem
gpu
```

Capability profiles describe implemented adapter behavior, not vendor marketing claims. A runtime with no registered profile fails closed.

### Interfaces

```yaml
interfaces:
  action_schema: urn:skill-native:action:argv:v1
  observation_schema: urn:skill-native:observation:evidence-bundle:v1
  protocols: []
```

These identifiers allow future MCP, A2A, AG-UI, ACP, browser, device, voice, and robotics adapters to declare their action and observation boundaries without changing the core provenance/verdict chain.

### Execution adapter

```yaml
execution:
  adapter: coding.command.v1
  command:
    - skill
    - run
    - "{entrypoint}"
```

`coding.command.v1` compiles an argv array. It does not invoke a shell and does not accept arbitrary Python format expressions. Supported placeholders are:

```text
{entrypoint}
{run_id}
{scenario_id}
{task}
{skill_digest}
```

Unknown placeholders, conversion operators, and format specifications are rejected.

### Evidence contract

```yaml
evidence:
  capture:
    - exit_code
    - stdout
    - stderr
    - commands
    - assertions
    - runtime_metadata
  required:
    - exit_code
    - stdout
    - stderr
    - commands
    - assertions
    - runtime_metadata
```

Every runtime adapter declares a trusted evidence profile. Compilation rejects a manifest that asks the selected runtime to capture evidence the adapter cannot collect. This prevents a backend from silently ignoring an evidence requirement.

`required` must be a subset of `capture`. Every verifier dependency must also be mandatory evidence.

Empty evidence can still be meaningful. A clean `stderr` or an empty network event stream counts only when the trusted adapter records an evidence-collector attestation in:

```json
{
  "runtime_metadata": {
    "evidence_contract": {
      "schema_version": "1.0",
      "captured": ["stderr"]
    }
  }
}
```

Without this attestation, an empty value is treated as missing rather than silently passing.

### Deterministic verifiers

Implemented verifier kinds:

```text
exit_code_zero
assertion_true
stdout_contains
stderr_empty
evidence_present
```

Example:

```yaml
verification:
  security_gate: fail-on-high-or-critical
  checks:
    - id: process-exited-cleanly
      kind: exit_code_zero
    - id: runtime-completed
      kind: assertion_true
      assertion: runtime_completed
```

Verifier IDs are unique. Kernel-owned IDs and the `evidence:` prefix are reserved.

The default hierarchy remains:

```text
deterministic assertion
    > statistical verifier
        > model-based critic
            > LLM-as-a-judge
```

This initial contract implements deterministic assertions only. A future semantic verifier must be explicitly typed, versioned, evidence-linked, and unable to bypass deterministic or security failures.

### Budgets

```yaml
budgets:
  timeout_seconds: 60
  max_model_calls: 0
  max_output_tokens: 0
  max_network_requests: 0
```

Every effective `RunSpec.limits` value must be less than or equal to the manifest budget. Compilation fails before execution when a caller requests a larger budget.

### Replay

```yaml
replay:
  supported: false
  snapshot_required: false
```

`snapshot_required=true` requires both `supported=true` and a runtime capability profile with snapshot/restore support. The current adapters do not claim snapshot support through this kernel.

## HarnessPlan

`HarnessKernel.compile()` produces a self-contained plan containing:

- manifest identity and digest;
- immutable provenance digest;
- full `RunSpec`, including Agent, Model, Runtime, policy, scenario, and limits;
- the exact runtime capability profile used during compilation;
- compiled argv;
- mandatory evidence and verifier definitions;
- policy digest;
- plan digest.

The plan validates its own digest when loaded. Modifying the command, RunSpec, capabilities, checks, policy, or evidence requirements without recomputing the plan is rejected.

The committed schema is `schemas/harness-plan.schema.json`.

## HarnessVerdict

The kernel adds invariant checks that a package cannot remove:

```text
provenance-continuity
runtime-continuity
evidence:<required-kind>
security-gate
```

A verdict records:

- manifest digest;
- provenance digest;
- plan digest;
- evidence digest;
- runtime backend;
- every check and failure;
- security findings and gate state;
- verdict digest.

Any failed check produces `status=fail`. Any High or Critical security finding forces `security_gate=fail` and therefore a failed verdict, even when all task assertions pass.

The verdict validates its own digest and ensures `failed_check_ids`, check results, status, and security-gate state agree. The committed schema is `schemas/harness-verdict.schema.json`.

## Digest chain

```text
immutable Skill content
        |
        v
provenance_digest
        |
        v
RunSpec + HarnessManifest
        |
        v
manifest_digest + policy_digest + plan_digest
        |
        v
EvidenceBundle + evidence_digest
        |
        v
HarnessVerdict + verdict_digest
        |
        v
compatibility matrix + ScorePolicy + report digest
```

The Harness Kernel does not replace existing scoring. It strengthens the evidence input and makes the execution contract independently inspectable.

## CLI

Validate a manifest:

```bash
skill-native validate-harness examples/harnesses/coding/harness.yaml
```

Compile a deterministic plan:

```bash
skill-native plan-harness \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml
```

Run the deterministic contract fixture and persist content-addressed evidence and verdict artifacts:

```bash
skill-native run-harness-fake \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml \
  --evidence-dir /tmp/skill-native-evidence \
  --verdict-dir /tmp/skill-native-verdicts
```

Export schemas:

```bash
skill-native export-harness-schemas /tmp/generated-schemas
```

CI regenerates these schemas and diffs them against `schemas/`, so model changes cannot silently drift from the published contract.

## Trust boundaries

### Untrusted

- `SKILL.md` instructions;
- third-party scripts and dependencies;
- registry metadata;
- package-supplied `harness.yaml` claims;
- Agent-generated commands;
- model outputs;
- network responses;
- files generated inside the sandbox.

### Trusted computing base

- immutable ingestion and provenance generation;
- approved HarnessManifest policy or operator overlay;
- DomainAdapter registry;
- RuntimeAdapter controller and capability/evidence profiles;
- evidence collectors outside the untrusted workspace;
- deterministic verifier implementation;
- security evaluator;
- content-addressing code.

A package-supplied manifest is a requested contract. It cannot grant itself a runtime, capability, network permission, secret, evidence exemption, or verifier type that the trusted kernel has not registered.

## Verification vocabulary

### Implemented

Code, schemas, deterministic tests, and local fake-runtime evidence exist.

### Integration-verified

A real external source or service produced persisted evidence.

### Runtime-verified

A real isolated runtime executed the exact pinned artifact and produced evidence satisfying the required runtime and security assertions.

The example in this increment is **implemented** only. `FakeRuntime` records `verification_state=deterministic-mock`. Its passing verdict must not be described as live OpenShell, Cloudflare, Coding Agent, Browser, Android, Desktop, or model verification.

## Adapter extension rules

A new domain adapter must:

1. use a unique, versioned adapter ID;
2. declare exactly one domain;
3. compile typed actions without implicit shell interpolation;
4. declare required runtime capabilities;
5. declare evidence the trusted backend can actually collect;
6. preserve immutable provenance and the complete RunSpec;
7. produce a normalized EvidenceBundle;
8. add deterministic assertions for final state;
9. preserve the High/Critical non-compensable security gate;
10. include matched positive, negative, and failure fixtures;
11. include reset/replay rules for the environment;
12. distinguish deterministic tests from live runtime evidence.

A new runtime adapter must also publish a truthful capability profile and evidence profile. Unsupported or unavailable evidence must be rejected, not represented by an empty placeholder.

## Follow-on domain sequence

| Priority | Domain | First adapter slice | Deterministic final-state evidence |
|---|---|---|---|
| P1 | Coding | Codex/Gemini/Qwen/OpenHands adapter contract | patch, tests, Git diff, exit status, PR receipt |
| P1 | Browser | Playwright accessibility/DOM executor | URL, DOM, network trace, downloaded artifacts, app state |
| P1 | Android | Appium/Maestro/ADB executor | UI hierarchy, screenshot, logcat, package/app state |
| P2 | Desktop | Windows/UIA or OSWorld executor | accessibility state, filesystem, registry/app state, screenshot |
| P2 | SRE | read-only Kubernetes/observability adapter | query receipts, diagnosis evidence, proposed patch, canary result |
| P2 | Documents | Docling/structured extraction adapter | source hash, page anchors, tables, claim-to-source edges |
| P3 | Voice | realtime media adapter | latency, turn events, interruption, tool receipts, transfer state |
| P3 | Robotics | simulation-first action adapter | joint/sensor state, collision, force, safety-boundary assertions |

Each follow-on adapter should be a separate Issue and Draft PR. Domain breadth must not weaken the core evidence or policy invariants.
