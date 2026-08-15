# Executable capability audit

This directory turns repository capability claims into a zero-access evidence packet. It is intentionally stricter than the root documentation: prose defines the question, while executed commands, runtime identities, receipts, and persisted files define the answer.

## One-command full audit

Prerequisites:

- Python 3.11 or newer;
- Docker Engine with permission to run containers;
- outbound HTTPS for package/bootstrap downloads and the public GitHub ingestion probe;
- enough local disk for Chromium and the audit container image.

Run:

```bash
./audit/run.sh
```

The wrapper creates a dedicated virtual environment, installs `.[browser]`, installs Chromium, and executes the full contract. Override the output or bootstrap behavior with:

```bash
SKILL_NATIVE_AUDIT_OUTPUT=/absolute/output \
SKILL_NATIVE_AUDIT_BOOTSTRAP=0 \
PYTHON_BIN=/path/to/python \
./audit/run.sh
```

When the environment is already provisioned:

```bash
python audit/run.py \
  --output .skill-native/capability-audit \
  --clean \
  --full
```

Partial probes are supported for diagnosis:

```bash
python audit/run.py --clean --with-browser
python audit/run.py --clean --with-github-ingestion
python audit/run.py --clean --with-docker
```

A partial run does not weaken the full contract. Capabilities that were not reached remain `NOT_EXERCISED`, and required full-audit capabilities prevent an overall PASS.

## What the audit executes

```text
exact git commit + tree
        ↓
package CLI + dependency snapshot
        ↓
full unit/integration suite with Playwright installed
        ↓
Cloudflare Worker + Dynamic Worker TypeScript contract checks
        ↓
schema regeneration + adversarial fixture materialization
        ↓
Coding Harness → FakeRuntime EvidenceBundle → HarnessVerdict
        ↓
Run Artifact Bundle
        ↓
ephemeral local Ed25519 signature
        ↓
verifier-owned policy + local transparency inclusion receipt
        ↓
real Chromium loopback runtime
        ↓
live public GitHub immutable ingestion
        ↓
hardened Linux container execution
  ├── positive control: declared tmpfs write succeeds
  ├── negative control: outbound socket exits non-zero
  └── negative control: rootfs write exits non-zero
        ↓
machine-readable capability result + SHA256SUMS
```

The full contract is [`capability-contract.json`](./capability-contract.json). [`run.py`](./run.py) owns the probe sequence; [`audit_core.py`](./audit_core.py) owns the terminal-state, logging, aggregation, and digest contract.

## Output contract

The default output is `.skill-native/capability-audit/`:

```text
.skill-native/capability-audit/
├── capability-audit-result.json   # primary machine contract
├── summary.md                     # zero-access reviewer summary
├── subject.json                   # exact commit/tree/ref identity
├── environment.json               # host and GitHub runner identity
├── SHA256SUMS                     # digest of every published file
├── logs/                          # command, exit, stdout, stderr, timing
└── artifacts/
    ├── coding-evidence/
    ├── coding-verdicts/
    ├── run-artifacts/
    ├── browser-runtime/
    ├── ingested-skill/
    ├── provenance/
    ├── generated-schemas/
    ├── adversarial-fixtures/
    ├── attestation-*.json
    ├── run-artifact.dsse.json
    ├── inclusion-receipt.json
    ├── docker-image-inspect.json
    └── docker-hardened-harness-result.json
```

`capability-audit-result.json` binds each capability to:

- exact subject commit and tree;
- required or optional status;
- minimum evidence level;
- actual command and expected exit semantics;
- actual exit code;
- runtime identity;
- raw log;
- persisted evidence paths;
- explicit non-claims.

The result uses only these terminal states:

```text
PASS
FAIL
ABSENT
NOT_IMPLEMENTED
NOT_EXERCISED
BLOCKED_INFRASTRUCTURE
SKIPPED_BY_POLICY
```

Absence, skipped execution, a configured workflow, a signature, or a successful mock never becomes `PASS`.

## Runtime boundaries

### GitHub-hosted runner

The workflow executes on a clean `ubuntu-24.04` GitHub-hosted runner. The checked-out commit is explicit, and the audit reads the actual `git rev-parse HEAD` and tree SHA rather than trusting event prose.

### Chromium

The Browser fixture launches a real Chromium process through Playwright and persists its result, EvidenceBundle, HarnessVerdict, DOM/accessibility evidence, screenshots, downloads, and network trace.

Its own runtime metadata remains:

```text
verification_state=deterministic-local-browser-integration
isolation=none
network_enforcement=playwright-origin-route-only
```

This proves the Browser vertical slice reaches Chromium. It does not prove hostile-code isolation or production-site compatibility.

### Hardened container

The container probe executes the installed package with:

```text
network=none
rootfs=read-only
capabilities=all dropped
no-new-privileges=true
pids-limit=128
memory=512 MiB
cpu=1
user=65534:65534
/tmp=bounded tmpfs
```

The build resolves an actual content-addressed image ID and persists `docker image inspect`. The runtime uses that image ID, not only the mutable discovery tag.

This is independent runtime/substrate evidence for the audit smoke path. It is not NVIDIA OpenShell and cannot close the OpenShell roadmap gate.

## Credential boundary

The audit removes common tokens, API keys, secrets, and passwords from child-process environments by default. The read-only GitHub token is attached only to the trusted public-ingestion command. The ephemeral signing private key lives in a temporary directory and is deleted before artifact publication.

Do not add production credentials to the audit command, fixture, logs, workflow YAML, Issue, or PR.

## GitHub Actions

The repository workflow is [`.github/workflows/capability-audit.yml`](../.github/workflows/capability-audit.yml). It:

1. checks out the exact branch/PR head;
2. installs the Browser runtime;
3. runs the full audit;
4. writes the zero-access summary to the GitHub job summary;
5. uploads the evidence packet even when a required check fails;
6. fails the job after publication when the full contract is not satisfied.

The artifact name contains the exact workflow subject SHA and run attempt. The PR conversation should additionally record the Actions run URL, artifact name, result state, and unresolved external gates.

## External gates that stay explicit

A successful full audit still does not establish:

- real NVIDIA OpenShell execution and OCSF capture;
- account-backed Cloudflare cold/warm execution;
- provider-backed inference and credential non-exposure;
- Android ADB, emulator, or physical-device execution;
- statistically adequate multi-agent/runtime/model ranking;
- an independently witnessed public transparency log.

Those capabilities remain separate contract rows with non-PASS states until their own admitted runtimes produce persisted evidence.

## Reviewer procedure

A reviewer should not begin from the PR description. Begin from:

```text
capability-audit-result.json
→ subject commit/tree
→ capability state
→ check IDs
→ raw logs and actual exit codes
→ evidence files
→ SHA256SUMS
→ compare declared non-claims with public documentation
```

A negative control is a PASS only when the forbidden action actually exits non-zero. A positive control is required so a broken container or missing interpreter cannot masquerade as enforcement.

## Related reusable prompt

The complete repository capability-auditor system prompt is in:

[`docs/agents/CAPABILITY_AUDITOR_SYSTEM_PROMPT.md`](../docs/agents/CAPABILITY_AUDITOR_SYSTEM_PROMPT.md)
