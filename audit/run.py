#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from audit_core import Audit, ROOT, identity

def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-first repository capability audit")
    parser.add_argument("--output", type=Path, default=ROOT / ".skill-native/capability-audit")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--with-browser", action="store_true")
    parser.add_argument("--with-docker", action="store_true")
    parser.add_argument("--with-github-ingestion", action="store_true")
    args = parser.parse_args()
    if args.full:
        args.with_browser = args.with_docker = args.with_github_ingestion = True
    subject, env = identity()  # bind before creating output files
    audit = Audit(args.output, args.clean)
    a = audit.artifacts
    py = sys.executable

    audit.run("package-cli-help", "package.cli.installable", "Installed CLI responds", ["skill-native", "--help"])
    audit.run("dependency-snapshot", "environment.dependency.snapshot", "Dependencies captured", [py, "-m", "pip", "freeze"], stdout_artifact="artifacts/pip-freeze.txt")
    audit.run("full-python-suite", "tests.full_suite", "Full Python suite", [py, "-m", "unittest", "discover", "-s", "tests", "-v"], timeout=1200, runtime={"kind": "github-hosted-runner" if env["github_actions"] else "local-host"}, notes=["Playwright must be installed so Browser integration tests do not skip."])
    audit.run("android-compile-tests", "android.compile.contract", "Android compile boundary", [py, "-m", "unittest", "tests.test_android_compile", "-v"])
    audit.run("cloudflare-worker-typecheck", "cloudflare.contracts.typecheck", "Cloudflare Sandbox Worker contracts", ["/bin/bash", "-lc", "cd cloudflare/worker && npm install --ignore-scripts && npm run typecheck"], timeout=600)
    audit.run("cloudflare-dynamic-worker-typecheck", "cloudflare.contracts.typecheck", "Cloudflare Dynamic Worker contracts", ["/bin/bash", "-lc", "cd cloudflare/dynamic-worker && npm install --ignore-scripts && npm run typecheck"], timeout=600)
    audit.run("schema-sync", "schemas.deterministic.sync", "Generated schemas match", ["/bin/bash", "-lc", "rm -rf \"$1\"; skill-native export-harness-schemas \"$1\"; skill-native-run-artifacts export-schemas \"$1\"; skill-native-attest export-schemas \"$1\"; diff -ru schemas \"$1\"", "schema", str(a / "generated-schemas")], evidence=[a / "generated-schemas"])
    audit.run("materialize-fixtures", "security.fixtures.materialized", "Adversarial fixtures materialize", ["skill-native", "materialize-fixtures", str(a / "adversarial-fixtures")], stdout_artifact="artifacts/adversarial-fixtures.json", evidence=[a / "adversarial-fixtures"])
    audit.run("validate-coding-harness", "harness.coding.fake", "Coding manifest validates", ["skill-native", "validate-harness", "examples/harnesses/coding/harness.yaml"], stdout_artifact="artifacts/coding-harness-manifest.json")
    audit.run("plan-coding-harness", "harness.coding.fake", "Coding plan compiles", ["skill-native", "plan-harness", "examples/harnesses/coding/harness.yaml", "examples/harnesses/coding/run.fake.yaml"], stdout_artifact="artifacts/coding-harness-plan.json")
    audit.run("run-coding-fake", "harness.coding.fake", "FakeRuntime evidence/verdict", ["skill-native", "run-harness-fake", "examples/harnesses/coding/harness.yaml", "examples/harnesses/coding/run.fake.yaml", "--evidence-dir", str(a / "coding-evidence"), "--verdict-dir", str(a / "coding-verdicts")], stdout_artifact="artifacts/coding-harness-result.json", evidence=[a / "coding-evidence", a / "coding-verdicts"], runtime={"kind": "deterministic-fixture", "backend": "fake", "isolation": "none"})
    bundle = audit.run("build-run-artifacts", "run_artifact.bundle", "Run Artifact Bundle", ["skill-native-run-artifacts", "build", "--authority", "examples/run-artifacts/authority.json", "--plan", "examples/run-artifacts/plan.json", "--evidence", "examples/run-artifacts/evidence.json", "--verdict", "examples/run-artifacts/verdict.json", "--output", str(a / "run-artifacts")], stdout_artifact="artifacts/run-artifacts-build.json", evidence=[a / "run-artifacts"])

    if bundle.status == "PASS":
        bundle_path = Path(json.loads((a / "run-artifacts-build.json").read_text())["bundle_path"])
        if not bundle_path.is_absolute():
            bundle_path = ROOT / bundle_path
        commit = subject["commit_sha"] if subject["commit_sha"] and len(subject["commit_sha"]) == 40 else "0" * 40
        repo = subject["repository"]
        workflow_ref = f"{repo}/.github/workflows/capability-audit.yml@{commit}"
        ident = {
            "issuer": "skill-native.local-ephemeral-key",
            "subject": f"audit-run:{env.get('github_run_id') or 'local'}:attempt:{env.get('github_run_attempt') or 'local'}",
            "repository": repo, "workflow_ref": workflow_ref,
            "commit_sha": commit,
            "environment": "github-hosted-audit-local-key" if env["github_actions"] else "local-audit-local-key",
        }
        ident_path, pub = a / "attestation-identity.json", a / "ephemeral-public-key.pem"
        policy, envelope = a / "attestation-policy.json", a / "run-artifact.dsse.json"
        verify, log, receipt = a / "attestation-verification.json", a / "transparency-log.jsonl", a / "inclusion-receipt.json"
        ident_path.write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n")
        with tempfile.TemporaryDirectory(prefix="skill-native-audit-key-") as td:
            private = Path(td) / "private.pem"
            key = audit.run("attest-key", "attestation.ephemeral_local_key", "Ephemeral Ed25519 key", ["skill-native-attest", "generate-key", "--private-key", str(private), "--public-key", str(pub)], stdout_artifact="artifacts/key-generation.json", notes=["Private key is deleted before publication."])
            if key.status == "PASS":
                audit.run("attest-policy", "attestation.ephemeral_local_key", "Exact-commit trust policy", ["skill-native-attest", "create-policy", "--policy-id", "skill-native.capability-audit", "--public-key", str(pub), "--expected-issuer", ident["issuer"], "--expected-subject", ident["subject"], "--expected-repository", repo, "--expected-workflow-ref", workflow_ref, "--expected-commit-sha", commit, "--require-rank-eligible", "--output", str(policy)])
                audit.run("attest-sign", "attestation.ephemeral_local_key", "DSSE sign exact bundle", ["skill-native-attest", "sign", "--bundle", str(bundle_path), "--identity", str(ident_path), "--private-key", str(private), "--output", str(envelope)], notes=["Local key, not GitHub OIDC/keyless identity."])
                audit.run("attest-verify", "attestation.ephemeral_local_key", "Verify DSSE and policy", ["skill-native-attest", "verify", "--bundle", str(bundle_path), "--envelope", str(envelope), "--public-key", str(pub), "--policy", str(policy), "--output", str(verify)])
                audit.run("transparency-append", "attestation.ephemeral_local_key", "Append local transparency log", ["skill-native-attest", "log-append", "--bundle", str(bundle_path), "--envelope", str(envelope), "--public-key", str(pub), "--policy", str(policy), "--log", str(log), "--log-id", "skill-native.capability-audit", "--receipt-output", str(receipt)], notes=["Local log is not independently witnessed."])
                audit.run("transparency-receipt", "attestation.ephemeral_local_key", "Verify inclusion receipt", ["skill-native-attest", "receipt-verify", "--log", str(log), "--log-id", "skill-native.capability-audit", "--receipt", str(receipt)], stdout_artifact="artifacts/transparency-receipt-verification.json", evidence=[ident_path, pub, policy, envelope, verify, log, receipt])
    else:
        audit.declare("attestation.ephemeral_local_key", "NOT_EXERCISED", "Run Artifact build failed.")

    if args.with_browser:
        audit.run("browser-runtime", "browser.chromium.loopback", "Real Chromium loopback", [py, "examples/harnesses/browser/run_fixture.py", "--output-dir", str(a / "browser-runtime")], timeout=600, stdout_artifact="artifacts/browser-runtime-result.json", evidence=[a / "browser-runtime"], runtime={"kind": "real-browser-process", "browser": "chromium", "isolation": "none"}, notes=["Real Chromium, deterministic local loopback, no hostile-code isolation."])
    else:
        audit.declare("browser.chromium.loopback", "NOT_EXERCISED", "Run --with-browser or --full.")

    if args.with_github_ingestion:
        token = os.environ.get("GITHUB_TOKEN")
        audit.run("github-ingestion", "integration.github.ingestion", "Public GitHub immutable ingestion", ["skill-native", "ingest-github", "https://github.com/vercel-labs/agent-skills", "--ref", "main", "--skill-path", "skills/react-best-practices", "--output", str(a / "ingested-skill"), "--provenance-dir", str(a / "provenance")], timeout=300, stdout_artifact="artifacts/github-ingestion-result.json", evidence=[a / "ingested-skill", a / "provenance"], env={"GITHUB_TOKEN": token} if token else None, runtime={"kind": "external-public-integration", "service": "github.com"})
    else:
        audit.declare("integration.github.ingestion", "NOT_EXERCISED", "Run --with-github-ingestion or --full.")

    if args.with_docker:
        tag = f"skill-native-capability-audit:{(subject['commit_sha'] or 'unknown')[:12]}"
        built = audit.run("docker-build", "sandbox.container.execution", "Build audit image", ["docker", "build", "--pull", "-f", "audit/Dockerfile", "-t", tag, "."], timeout=1200, runtime={"kind": "docker-build"})
        if built.status == "PASS":
            inspected = audit.run("docker-inspect", "sandbox.container.execution", "Capture image identity", ["docker", "image", "inspect", tag], stdout_artifact="artifacts/docker-image-inspect.json")
            image = json.loads((a / "docker-image-inspect.json").read_text())[0]["Id"] if inspected.status == "PASS" else tag
            common = ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "128", "--memory", "512m", "--cpus", "1", "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m", "--user", "65534:65534", "--env", "PYTHONDONTWRITEBYTECODE=1"]
            audit.run("docker-harness", "sandbox.container.execution", "Harness in hardened container", [*common, "--entrypoint", "/bin/sh", image, "-lc", "skill-native run-harness-fake examples/harnesses/coding/harness.yaml examples/harnesses/coding/run.fake.yaml --evidence-dir /tmp/evidence --verdict-dir /tmp/verdicts >/tmp/result.json && test \"$(find /tmp/evidence -type f | wc -l)\" -eq 1 && test \"$(find /tmp/verdicts -type f | wc -l)\" -eq 1 && cat /tmp/result.json"], stdout_artifact="artifacts/docker-hardened-harness-result.json", runtime={"kind": "real-linux-container", "image_id": image, "network": "none", "rootfs": "read-only", "capabilities": "all-dropped"}, notes=["Generic Docker boundary, not OpenShell."])
            audit.run("docker-tmpfs", "sandbox.container.tmpfs_write", "Writable declared tmpfs", [*common, "--entrypoint", "python", image, "-c", "from pathlib import Path; p=Path('/tmp/allowed'); p.write_text('ok'); assert p.read_text()=='ok'"], runtime={"kind": "real-linux-container", "image_id": image})
            audit.run("docker-egress", "sandbox.container.egress_denied", "Denied outbound socket", [*common, "--entrypoint", "python", image, "-c", "import socket; socket.create_connection(('1.1.1.1',53),2)"], expectation="nonzero", runtime={"kind": "real-linux-container", "image_id": image, "network": "none"}, notes=["PASS requires a real attempted connection to exit non-zero."])
            root_common = [x for x in common if x not in {"65534:65534"}]
            root_common[root_common.index("--user") + 1] = "0:0"
            audit.run("docker-rootfs", "sandbox.container.rootfs_write_denied", "Read-only rootfs denial", [*root_common, "--entrypoint", "python", image, "-c", "from pathlib import Path; Path('/app/forbidden').write_text('x')"], expectation="nonzero", runtime={"kind": "real-linux-container", "image_id": image, "rootfs": "read-only", "user": "root-with-caps-dropped"}, notes=["Root user isolates read-only filesystem enforcement from ordinary directory permissions."])
    else:
        for cid in ("sandbox.container.execution", "sandbox.container.tmpfs_write", "sandbox.container.egress_denied", "sandbox.container.rootfs_write_denied"):
            audit.declare(cid, "NOT_EXERCISED", "Run --with-docker or --full.")

    audit.declare("runtime.openshell.live", "NOT_EXERCISED", "No real OpenShell gateway/runner admitted.", "Docker is not OpenShell.")
    audit.declare("runtime.cloudflare.live", "NOT_EXERCISED", "No admitted account endpoint/credentials; typecheck is not runtime evidence.")
    audit.declare("inference.provider.live", "NOT_EXERCISED", "No provider credential or local inference endpoint admitted.")
    audit.declare("android.adb.runtime", "NOT_IMPLEMENTED", "Android contract/compile exists; trusted ADB runner/evidence/emulator/device path is absent.")
    audit.declare("ranking.multicell.runtime_samples", "NOT_EXERCISED", "No adequate live Skill × Agent × Runtime × Model matrix executed.")
    audit.declare("transparency.public_witness", "NOT_IMPLEMENTED", "Local log is not independently witnessed or equivalent to Rekor.")
    (audit.output / "subject.json").write_text(json.dumps(subject, indent=2, sort_keys=True) + "\n")
    (audit.output / "environment.json").write_text(json.dumps(env, indent=2, sort_keys=True) + "\n")
    return audit.finish(subject, env)


if __name__ == "__main__":
    raise SystemExit(main())
