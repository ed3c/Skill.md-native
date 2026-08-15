<!-- i18n-key: README; locale: en; reviewed: 2026-08-16 -->
[English](README.md) · [繁體中文](README.zh-TW.md)

# Skill.md-native

[![Unit](https://github.com/ed3c/Skill.md-native/actions/workflows/unit.yml/badge.svg)](https://github.com/ed3c/Skill.md-native/actions/workflows/unit.yml)
[![Integration](https://github.com/ed3c/Skill.md-native/actions/workflows/integration.yml/badge.svg)](https://github.com/ed3c/Skill.md-native/actions/workflows/integration.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)

**Runtime-verified identity, evidence, security, replay, compatibility, and outcome ranking for Agent Skills and `SKILL.md` workflows.**

> **Maturity:** alpha research and engineering platform. Deterministic local paths, the cross-domain Harness Kernel, executable capability audit, and the capabilities named in the integration ledger are implemented. A configured adapter, fixture, CI job, signature, registry entry, or owner statement does not prove live sandbox, account-backed runtime, Android device, model-provider, release, or production verification.

## The problem

A Skill can be discoverable, installable, and syntactically valid while still being unsafe, non-reproducible, incompatible with a target Agent, or impossible to rank fairly. Mutable repository references, hidden runtime differences, model changes, missing evidence, and self-authored success claims make comparisons unreliable.

Skill.md-native answers a stricter set of questions:

```text
What exact Skill artifact ran?
Which Agent, Runtime, Model, policy, permissions, and scenario were used?
What commands and inputs were actually executed?
What evidence was captured and persisted?
Did required assertions and negative controls pass?
Did any non-compensable security gate fail?
Can the result be replayed?
Can a ranking claim be traced to immutable evidence?
```

## What the platform provides

| Layer | Responsibility |
|---|---|
| Immutable ingestion | Resolve mutable registry or Git references to pinned artifacts with provenance and supply-chain evidence |
| Harness compilation | Validate `RunSpec`, `HarnessManifest`, DomainAdapter, runtime capabilities, policy, budgets, stdin transport, and required evidence |
| Controlled execution | Run coding, browser, Android, or future domain contracts through bounded runtime adapters |
| Evidence and verdict | Normalize receipts and artifacts, verify identity continuity, execute assertions, and apply a non-compensable security gate |
| Run Artifacts | Derive Evidence Graphs, replay classification, logical traces, outcome scorecards, and a canonical bundle |
| Attestation | Sign canonical statements, verify key policy, and publish transparency inclusion receipts without upgrading a failed verdict |
| Compatibility and ranking | Compare explicit `Skill × Agent × Runtime × Model` cells without silently pooling confounders |
| Capability audit | Execute one exact-subject audit and publish machine-readable results, raw logs, runtime identities, artifacts, and SHA-256 sums |

The verifier-owned layer is the product boundary. Registries, marketplaces, Agent frameworks, model providers, sandboxes, pages, applications, and connected devices are untrusted inputs or execution dependencies.

## End-to-end trust flow

```mermaid
flowchart LR
    A[Registry / repository / plugin] --> B[Immutable provenance]
    B --> C[RunSpec + HarnessManifest]
    C --> D[Trusted DomainAdapter]
    D --> E[Digest-addressed HarnessPlan]
    E --> F[Controlled runtime / domain runner]
    F --> G[EvidenceBundle]
    G --> H[Deterministic verifiers]
    H --> I{Security gate}
    I -->|pass| J[HarnessVerdict]
    I -->|fail| X[Ineligible result]
    J --> K[RunArtifactBundle]
    K --> L[Optional DSSE + transparency]
    L --> M[Compatibility cells and ranking]
```

Core invariants:

```text
mutable discovery reference != evaluated identity
configured workflow != executed evidence
fixture success != live runtime success
signature != correctness
transparency inclusion != runtime verification
contract/primitive implementation != trusted runner execution
emulator verification != physical-device verification
task success cannot compensate for High/Critical security failure
```

## Quick start

### Requirements

- Python 3.11+
- Git
- Optional browser domain: Playwright Chromium
- Optional full audit: Docker Engine, Chromium bootstrap, and outbound HTTPS for public dependencies and the public GitHub ingestion probe
- Optional live runtimes: their own reviewed prerequisites, authorization, and credentials

```bash
git clone https://github.com/ed3c/Skill.md-native.git
cd Skill.md-native

python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

skill-native --help
python -m unittest discover -s tests -v
```

Install the Browser extra:

```bash
python -m pip install -e '.[browser]'
python -m playwright install chromium
```

Validate a run and Harness manifest:

```bash
skill-native validate path/to/run.yaml
skill-native validate-harness examples/harnesses/coding/harness.yaml
```

Compile and execute the deterministic FakeRuntime vertical slice:

```bash
skill-native plan-harness \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml

skill-native run-harness-fake \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml \
  --evidence-dir .skill-native/evidence \
  --verdict-dir .skill-native/verdicts
```

Run the full executable capability audit:

```bash
./audit/run.sh
```

Read [`audit/README.md`](audit/README.md) before using the audit. Its exact result JSON, raw logs, artifacts, runtime identities, checksums, and workflow subject define the admitted state. A partial run leaves unreached capabilities non-PASS.

`deterministic-mock` output must never be reported as live sandbox, hosted runtime, emulator, physical-device, or production evidence.

## Domain and evidence status

The mutable source of truth is [`docs/INTEGRATION_STATE.md`](docs/INTEGRATION_STATE.md). The latest persisted exact-subject audit outranks prose.

| Domain or layer | Current boundary |
|---|---|
| Ingestion, provenance, and supply-chain evidence | Implemented on `main` |
| Cross-domain Harness Kernel | Implemented on `main` |
| Coding Agent Harness | Implemented and hardened |
| Run Artifact, replay, trace, and scorecard | Implemented |
| DSSE signing and local transparency publication | Implemented; not GitHub OIDC/keyless or independently witnessed transparency |
| Playwright Browser Harness | Implemented and hardened for the documented deterministic boundary |
| Executable capability audit | Implemented; exact workflow artifacts determine what was actually exercised |
| Android bounded contract and canonical compile boundary | Implemented |
| ADB binary identity, bounded device selection, and typed argv primitives | Implemented; primitives are not a trusted ADB runtime or device receipt |
| Trusted ADB runner, AndroidReceipt, scripted fixture, emulator, and physical-device verification | Separate stronger states; remain non-PASS until their own evidence exists |
| OpenShell, account-backed Cloudflare, provider isolation, detector quality, release, and production | Only exact persisted external evidence may establish these states |

## Repository map

```text
src/skill_native/
├── ingestion and provenance
├── Harness contracts, compiler, adapters, and verifiers
├── coding, browser, and Android domain contracts/primitives
├── runtime lifecycle and governed inference
├── evidence, security, scoring, and reporting
├── Run Artifact derivation
└── signing and transparency publication

audit/          executable exact-subject capability audit
schemas/        generated public contracts
examples/       deterministic fixtures and reference manifests
tests/          success, failure, tamper, replay, and compatibility proofs
cloudflare/     hosted bridge implementations
docs/           architecture, State Machines, status, audit, and delivery ledgers
```

No repository-owned Git Town configuration is detected. The historical stack remains in [`docs/STACKED_DELIVERY.md`](docs/STACKED_DELIVERY.md); current reconciliation and CI-economy rules are in [`docs/CONVERGENCE_2026-08-16.md`](docs/CONVERGENCE_2026-08-16.md).

## Documentation

- [Documentation index](docs/README.md)
- [Integration state](docs/INTEGRATION_STATE.md)
- [Executable capability audit](audit/README.md)
- [Capability audit interpretation](docs/audits/2026-08-15-capability-audit.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Harness Kernel](docs/HARNESS_KERNEL.md)
- [Coding Agent Harness](docs/CODING_AGENT_HARNESS.md)
- [Android Harness](docs/ANDROID_HARNESS.md)
- [Run Artifacts](docs/RUN_ARTIFACTS.md)
- [Attestations](docs/ATTESTATIONS.md)
- [Evaluation contract](docs/EVALUATION_CONTRACT.md)
- [State Machines](docs/STATE_MACHINES.md)
- [Historical stacked delivery](docs/STACKED_DELIVERY.md)
- [Current convergence ledger](docs/CONVERGENCE_2026-08-16.md)
- [Documentation language policy](docs/I18N.md)
- [Open-source readiness checklist](docs/OPEN_SOURCE_CHECKLIST.md)

`AGENTS.md`, `CLAUDE.md`, `SKILL.md`, generated evidence, fixtures, receipts, and signed artifacts are controlled documentation exceptions. They remain byte-stable or semantics-stable and are explained through bilingual indexes rather than translated automatically.

## Security and privacy

Third-party Skills, prompt packages, pages, applications, connected devices, model output, runtime output, and external artifacts are untrusted data. Trusted code owns identity, policy, permissions, budgets, evaluator authority, process construction, and verdict construction.

Never send private repository content, customer data, credentials, model weights, or restricted artifacts to a model provider, runtime, or external destination without explicit data-and-destination authorization. Report vulnerabilities through [SECURITY.md](SECURITY.md).

## Non-goals and non-claims

This repository does not claim universal Agent compatibility, production readiness, continuous autonomous improvement, Android device execution, OpenShell isolation, account-backed Cloudflare execution, provider credential non-exposure, statistically adequate ranking, public witnessed transparency, release, or deployment unless the exact subject has persisted the required evidence.

## Contributing and governance

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing contracts, evidence semantics, schemas, adapters, or ranking logic. Support boundaries are in [SUPPORT.md](SUPPORT.md), and human authority is defined in [GOVERNANCE.md](GOVERNANCE.md).

## License

Licensed under the [MIT License](LICENSE). Third-party Skills, dependencies, registries, models, runtimes, and test targets remain subject to their own licenses and terms.
