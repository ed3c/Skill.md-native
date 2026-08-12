# Coding Agent Harness v0.1

## Status

`coding.agent.v1` is the first domain-specific adapter implemented on top of the
cross-domain Harness Kernel.

Implemented and covered by deterministic CI:

- a versioned `coding` block in `harness.yaml`;
- a trusted wrapper process, `skill-native-coding-runner`;
- task delivery over standard input rather than argv;
- a digest-addressed Coding Agent receipt;
- bounded stdout/stderr capture;
- structured JSON or JSONL event validation;
- workspace snapshots and a normalized change receipt;
- protected-path, allowed-path, changed-file, changed-byte, symlink, timeout,
  output-size, and descendant-process checks;
- deterministic test commands that run outside the child agent process;
- command, input, manifest, provenance, runtime, evidence, and receipt
  continuity checks;
- OpenShell stdin and command-continuity bridging;
- Cloudflare command-continuity evidence without claiming stdin support;
- a local no-model fixture that reaches a complete `HarnessVerdict`.

Not established by this increment:

- a live Codex, Gemini CLI, Qwen Code, OpenHands, or other model-backed run;
- account-backed OpenShell execution;
- Cloudflare stdin transport;
- cryptographic signing of receipts;
- driver binary or package supply-chain attestation;
- autonomous GitHub PR creation or merge;
- Dagger, Temporal, or OpenTelemetry integration.

A green deterministic fixture proves the contract, runner, evidence
normalization, and verifier implementation. It must not be reported as live
model or production sandbox verification.

## Data flow

```text
Pinned Skill + immutable RunSpec
          │
          ▼
HarnessManifest(coding.agent.v1)
          │
          ├── pinned driver declaration
          ├── child argv template
          ├── task SHA-256
          ├── deterministic test argv
          ├── workspace policy
          └── budgets
          │
          ▼
Digest-addressed HarnessPlan
          │
          ├── argv: skill-native-coding-runner --config-b64 ... -- <child>
          └── stdin: task text (plan stores only its digest)
          │
          ▼
Trusted Coding Agent runner
          │
          ├── snapshot workspace
          ├── verify declared driver version
          ├── execute untrusted child agent
          ├── capture and normalize structured events
          ├── terminate remaining descendants
          ├── snapshot and classify workspace changes
          ├── execute independent test commands
          └── emit exactly one self-validating JSON receipt
          │
          ▼
Runtime EvidenceBundle
          │
          ├── command + stdin continuity
          ├── coding_receipt
          ├── agent_events
          ├── workspace_diff
          └── test_results
          │
          ▼
Kernel-owned domain checks + security gate
          │
          ▼
Digest-addressed HarnessVerdict
```

## Trust boundaries

### Trusted

- `HarnessKernel` and the registered `CodingAgentAdapter`;
- `skill-native-coding-runner`;
- runtime controllers outside the sandbox;
- the verifier registry and security evaluator;
- immutable provenance and artifact persistence;
- an operator-approved policy overlay when that capability is implemented.

### Untrusted

- the Skill package and package-supplied manifest claims;
- the child coding agent and its natural-language answer;
- child stdout, stderr, JSON events, and exit code;
- version and test commands requested by a package manifest;
- files produced inside the workspace;
- external model and tool responses.

The wrapper does not trust an agent statement such as “tests pass.” Success is
computed from independent process results, workspace policy checks, receipt
continuity, required evidence, and the non-compensable security gate.

## Task and output privacy

The scenario task is not interpolated into the child argv. It is streamed to the
trusted wrapper over stdin, then forwarded to the child process over stdin. The
plan and runtime command evidence store only the SHA-256 digest of the task.

The child process cannot inject a second top-level receipt: its stdout is read by
the wrapper and becomes nested evidence. The wrapper owns its stdout and emits
one JSON object.

Raw child output excerpts are disabled in contract v1. A package manifest cannot
turn them on because that would allow an untrusted package to widen evidence
retention. A future trusted operator overlay may add an explicit, auditable
retention decision. Version and test excerpts remain bounded for diagnostics;
secret redaction is still the responsibility of the runtime and policy layer.

## Coding contract

```yaml
execution:
  adapter: coding.agent.v1
  command: [codex, exec, --json, -]

coding:
  driver: codex
  driver_version: 0.0.0-pinned
  output_format: jsonl
  require_structured_events: true
  workspace: .
  version_command: [codex, --version]
  test_commands:
    - [python3, -m, pytest, -q]
  allowed_change_globs:
    - src/**
    - tests/**
  max_changed_files: 50
  max_changed_bytes: 2000000
```

The example is a contract shape, not a verified statement about a particular
third-party CLI release or its flags. Each driver integration must pin and test
the exact executable contract before it is promoted from `generic` fixture
status.

### Mandatory evidence

A `coding.agent.v1` manifest must require all of these kinds:

```text
exit_code
stdout
stderr
commands
assertions
runtime_metadata
coding_receipt
agent_events
workspace_diff
test_results
```

Domain evidence is advertised by the registered adapter, not globally by the
Kernel. A different adapter cannot claim that it will produce Coding Agent
evidence and pass compilation.

### Protected paths

The following protections cannot be removed by a package manifest:

```text
.git/**
.skill-native/**
AGENTS.md and **/AGENTS.md
CLAUDE.md and **/CLAUDE.md
.codex/** and **/.codex/**
.claude/** and **/.claude/**
```

Additional paths may be protected. The ignore list is restricted to a fixed set
of Python and pytest cache patterns; arbitrary ignore globs are rejected because
they could hide a policy violation.

## Receipt integrity

The receipt binds:

```text
run_id
runner_version
driver + declared version
task_digest
child_command_digest
contract_digest
workspace before/after digests
version probe result
agent process result
normalized event digests
workspace diff digest
test process results
policy checks
outcome
receipt_digest
```

Pydantic validation recomputes nested process, argv, workspace, and receipt
digests after JSON round-trip. The domain adapter then recomputes the expected
contract, child argv, task, version command, test argv, and change-budget results
from the compiled plan. A malformed or altered receipt is not downgraded to
unstructured output; it fails receipt continuity and mandatory-evidence checks.

The digest detects mutation and preserves continuity. It is not a signature. A
future attestation layer should sign the plan, runtime identity, evidence digest,
and verdict with a key unavailable to the sandbox.

## Process and workspace rules

Every version probe, agent process, and test command is started without a TTY.
The trusted runner streams output into a bounded buffer while hashing the full
stream. Output truncation, timeout, or failure to terminate the process tree
forces failure.

The version probe must not change the workspace. Tests run after the agent diff
is captured and must also leave the workspace unchanged. This prevents a test
command from repairing or hiding an agent-produced change before the final
verdict.

Workspace snapshots record files and symlinks without following directory
symlinks. Symlinks resolving outside the workspace fail the policy check.
Current snapshots are deterministic but not yet optimized for very large
monorepos; content-addressed incremental snapshots are a follow-on item.

## Runtime support

### Fake

`FakeRuntime` supports stdin digests and command continuity for plan/compiler
regression. It does not execute `skill-native-coding-runner`, so its ordinary
`run-harness-fake` path cannot establish a Coding Agent receipt. The end-to-end
fixture uses a dedicated temporary-process runtime inside the test suite and is
labelled `deterministic-fixture`.

### OpenShell

`OpenShellHarnessController` adds one-shot stdin streaming around the existing
OpenShell controller and appends the requested child argv plus stdin digest to
runtime command evidence. The default `OpenShellRuntime` uses this controller.
This code path is unit-tested with a scripted runner; account-backed execution
remains unverified until the integration workflow is run with an eligible
OpenShell environment.

### Cloudflare

The current Cloudflare bridge records requested argv continuity but declares
`stdin_stream=false`. `coding.agent.v1` therefore fails compilation for this
backend rather than placing the task in argv or pretending stdin was delivered.

## Deterministic verification

Run the focused suite:

```bash
python -m unittest \
  tests.test_coding_agent \
  tests.test_runtime_harness_controllers \
  -v
```

Validate and compile the committed fixture:

```bash
skill-native validate-harness examples/harnesses/coding-agent/harness.yaml
skill-native plan-harness \
  examples/harnesses/coding-agent/harness.yaml \
  examples/harnesses/coding-agent/run.fake.yaml
```

Regenerate contracts:

```bash
skill-native export-harness-schemas /tmp/harness-schemas
diff -ru schemas /tmp/harness-schemas
```

## Next increments

1. Add tested driver profiles for Codex, Gemini CLI, Qwen Code, and OpenHands,
   including executable/package digests and canonical event adapters.
2. Add a real `run-harness-openshell` CLI path and account-backed integration
   workflow without exposing provider credentials.
3. Package repository setup, patch artifacts, test reports, and Git metadata as
   content-addressed evidence.
4. Add OpenTelemetry/OpenInference spans keyed by `run_id`, `plan_digest`, and
   `receipt_digest`.
5. Add mutation tests for verifier strength and a hidden evaluator boundary.
6. Add GitHub draft-PR receipts behind explicit policy and human approval.
