from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from .models import EvidenceBundle, NetworkRule, RunSpec


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, argv: list[str], *, timeout: int | None = None) -> CommandResult: ...


class SubprocessRunner:
    def run(self, argv: list[str], *, timeout: int | None = None) -> CommandResult:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return CommandResult(argv=argv, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


class OpenShellError(RuntimeError):
    pass


class OpenShellPolicyCompiler:
    _SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")

    def compile(self, spec: RunSpec) -> dict:
        if spec.policy.network != "deny-by-default":
            raise ValueError("OpenShell backend requires network=deny-by-default")
        if spec.policy.secrets != "brokered":
            raise ValueError("OpenShell backend requires brokered secrets")
        if spec.policy.landlock_compatibility not in {"best_effort", "hard_requirement"}:
            raise ValueError("unsupported landlock compatibility")

        rules = list(spec.policy.network_rules)
        rules.extend(NetworkRule(host=host) for host in spec.policy.allowed_hosts)
        network_policies: dict[str, dict] = {}
        for index, rule in enumerate(rules):
            key = self._policy_key(index, rule.host)
            endpoint: dict[str, object] = {
                "host": rule.host,
                "port": rule.port,
                "enforcement": "enforce",
            }
            if rule.protocol:
                endpoint["protocol"] = rule.protocol
            if rule.path:
                endpoint["path"] = rule.path
            if rule.protocol in {"mcp", "json-rpc"}:
                raise ValueError(
                    f"{rule.protocol} requires explicit method/tool rules; generic access presets are refused"
                )
            endpoint["access"] = rule.access
            network_policies[key] = {
                "name": key,
                "endpoints": [endpoint],
                "binaries": [{"path": path} for path in rule.binaries],
            }

        return {
            "version": 1,
            "filesystem_policy": {
                "include_workdir": True,
                "read_only": ["/usr", "/lib", "/proc", "/dev/urandom", "/etc", "/var/log"],
                "read_write": ["/sandbox", "/tmp", "/dev/null"],
            },
            "landlock": {"compatibility": spec.policy.landlock_compatibility},
            "process": {"run_as_user": "sandbox", "run_as_group": "sandbox"},
            "network_policies": network_policies,
        }

    def dump(self, spec: RunSpec) -> str:
        return yaml.safe_dump(self.compile(spec), sort_keys=True)

    def digest(self, spec: RunSpec) -> str:
        return hashlib.sha256(self.dump(spec).encode()).hexdigest()

    def _policy_key(self, index: int, host: str) -> str:
        safe_host = self._SAFE_NAME.sub("-", host).strip("-") or "host"
        return f"allow_{index:03d}_{safe_host}"[:120]


class OpenShellController:
    """Fail-closed wrapper around the OpenShell CLI with evidence capture.

    Provider credentials stay in the OpenShell gateway. Attached provider names
    are passed to `sandbox create`; the sandbox receives only OpenShell placeholder
    values which are resolved by the proxy on allowed outbound requests.
    """

    _MANIFEST_CMD = "find /sandbox -xdev -type f -exec sha256sum -- {} + 2>/dev/null | sort || true"
    _PLACEHOLDER_MARKERS = ("openshell:resolve:env:", "OPENSHELL-RESOLVE-ENV-")

    def __init__(self, runner: CommandRunner | None = None, binary: str = "openshell") -> None:
        self.runner = runner or SubprocessRunner()
        self.binary = binary
        self.compiler = OpenShellPolicyCompiler()
        self._runs: dict[str, dict] = {}

    def prepare(self, spec: RunSpec) -> str:
        name = self._sandbox_name(spec.run_id)
        policy_yaml = self.compiler.dump(spec)
        policy_hash = self.compiler.digest(spec)
        tempdir = tempfile.TemporaryDirectory(prefix="skill-native-openshell-")
        policy_path = Path(tempdir.name) / "policy.yaml"
        policy_path.write_text(policy_yaml)

        status = self._json_command([self.binary, "status", "--output", "json"])
        gateway_info = self._json_command([self.binary, "gateway", "info", "-o", "json"])

        create_argv = [self.binary, "sandbox", "create", "--name", name, "--policy", str(policy_path)]
        for provider in spec.policy.provider_names:
            create_argv.extend(["--provider", provider])
        create = self.runner.run(create_argv, timeout=spec.limits.timeout_seconds)
        if create.returncode != 0:
            tempdir.cleanup()
            raise OpenShellError(f"sandbox create failed: {create.stderr.strip()}")

        metadata = self._json_command([self.binary, "sandbox", "get", name, "--output", "json"])
        attestation = self._attest_runtime(spec, status=status, gateway_info=gateway_info, metadata=metadata)
        enable_ocsf = self.runner.run(
            [self.binary, "settings", "set", name, "--key", "ocsf_json_enabled", "--value", "true"],
            timeout=30,
        )
        if enable_ocsf.returncode != 0:
            self._best_effort_delete(name)
            tempdir.cleanup()
            raise OpenShellError(f"failed to enable OCSF JSON export: {enable_ocsf.stderr.strip()}")

        credential_probe = self._credential_probe(name, spec.policy.secret_env_names)
        filesystem_before = self._filesystem_manifest(name)
        self._runs[name] = {
            "spec": spec,
            "tempdir": tempdir,
            "policy_yaml": policy_yaml,
            "policy_hash": policy_hash,
            "metadata": metadata,
            "status": status,
            "gateway_info": gateway_info,
            "attestation": attestation,
            "credential_probe": credential_probe,
            "filesystem_before": filesystem_before,
            "executions": {},
        }
        return name

    def execute(self, sandbox_id: str, command: list[str]) -> str:
        record = self._require_run(sandbox_id)
        spec: RunSpec = record["spec"]
        execution_id = f"{sandbox_id}:exec:{len(record['executions'])}"
        result = self.runner.run(
            [self.binary, "sandbox", "exec", "-n", sandbox_id, "--no-tty", "--timeout",
             str(spec.limits.timeout_seconds), "--", *command],
            timeout=spec.limits.timeout_seconds + 15,
        )
        record["executions"][execution_id] = result
        return execution_id

    def collect(self, run_id: str, execution_id: str) -> EvidenceBundle:
        sandbox_id = execution_id.split(":exec:", 1)[0]
        record = self._require_run(sandbox_id)
        result: CommandResult = record["executions"][execution_id]
        spec: RunSpec = record["spec"]

        filesystem_after = self._filesystem_manifest(sandbox_id)
        filesystem_diff = self._diff_manifests(record["filesystem_before"], filesystem_after)

        effective_policy = self.runner.run([self.binary, "policy", "get", sandbox_id, "--full"], timeout=30)
        if effective_policy.returncode != 0 or not effective_policy.stdout.strip():
            # Compatibility fallback for older alpha CLI revisions.
            effective_policy = self.runner.run(
                [self.binary, "sandbox", "get", sandbox_id, "--policy-only"], timeout=30
            )
        if effective_policy.returncode != 0 or not effective_policy.stdout.strip():
            raise OpenShellError("effective policy evidence unavailable")

        logs = self.runner.run([self.binary, "logs", sandbox_id, "--source", "sandbox"], timeout=30)
        if logs.returncode != 0 or not logs.stdout.strip():
            raise OpenShellError("sandbox log evidence unavailable")

        ocsf_result = self.runner.run(
            [self.binary, "sandbox", "exec", "-n", sandbox_id, "--no-tty", "--",
             "/bin/sh", "-lc", "cat /var/log/openshell-ocsf.*.log 2>/dev/null || true"],
            timeout=30,
        )
        ocsf_events = self._parse_jsonl(ocsf_result.stdout)
        if not ocsf_events:
            raise OpenShellError("OCSF evidence unavailable; refusing verified result")

        processes = [event for event in ocsf_events if event.get("class_uid") == 1007]
        network = [event for event in ocsf_events if event.get("class_uid") in {4001, 4002}]
        findings = [event for event in ocsf_events if event.get("class_uid") == 2004]

        return EvidenceBundle(
            run_id=run_id,
            provenance_digest=spec.skill.provenance_digest,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            commands=[{"execution_id": execution_id, "argv": result.argv, "exit_code": result.returncode}],
            processes=processes,
            network=network,
            findings=findings,
            filesystem_before=record["filesystem_before"],
            filesystem_after={**filesystem_after, "diff": filesystem_diff},
            assertions={
                "runtime_completed": True,
                "effective_policy_captured": True,
                "ocsf_captured": True,
                "filesystem_manifest_captured": True,
                "runtime_attested": True,
                "credential_non_exposure": record["credential_probe"]["passed"],
            },
            runtime_metadata={
                "backend": "openshell",
                "sandbox_id": sandbox_id,
                "sandbox": record["metadata"],
                "gateway_status": record["status"],
                "gateway_info": record["gateway_info"],
                "attestation": record["attestation"],
                "credential_probe": record["credential_probe"],
                "declared_runtime_version": spec.runtime.version,
                "declared_image_digest": spec.runtime.image_digest,
                "policy_sha256": record["policy_hash"],
                "logs": logs.stdout,
            },
            policy={"compiled": yaml.safe_load(record["policy_yaml"]), "effective": effective_policy.stdout},
            ocsf_events=ocsf_events,
        )

    def destroy(self, sandbox_id: str) -> None:
        record = self._runs.pop(sandbox_id, None)
        try:
            result = self.runner.run([self.binary, "sandbox", "delete", sandbox_id], timeout=60)
            if result.returncode != 0:
                raise OpenShellError(f"sandbox delete failed: {result.stderr.strip()}")
        finally:
            if record:
                record["tempdir"].cleanup()

    def _credential_probe(self, sandbox_id: str, env_names: list[str]) -> dict[str, Any]:
        if not env_names:
            return {"passed": True, "checked": [], "reason": "no secret env names declared"}
        script = "\n".join(
            [
                "import json, os",
                f"names={env_names!r}",
                "print(json.dumps({n: os.environ.get(n) for n in names}, sort_keys=True))",
            ]
        )
        result = self.runner.run(
            [self.binary, "sandbox", "exec", "-n", sandbox_id, "--no-tty", "--", "python3", "-c", script],
            timeout=30,
        )
        if result.returncode != 0:
            raise OpenShellError("credential isolation probe failed to execute")
        try:
            values = json.loads(result.stdout.strip() or "{}")
        except json.JSONDecodeError as exc:
            raise OpenShellError("credential isolation probe returned invalid JSON") from exc
        exposed: list[str] = []
        placeholders: list[str] = []
        missing: list[str] = []
        for name in env_names:
            value = values.get(name)
            if value is None:
                missing.append(name)
            elif any(marker in str(value) for marker in self._PLACEHOLDER_MARKERS):
                placeholders.append(name)
            else:
                exposed.append(name)
        if exposed:
            raise OpenShellError(f"raw provider credential visible inside sandbox: {', '.join(exposed)}")
        return {"passed": True, "checked": env_names, "placeholders": placeholders, "missing": missing}

    def _attest_runtime(self, spec: RunSpec, *, status: dict, gateway_info: dict, metadata: dict) -> dict[str, Any]:
        observed_version = self._recursive_value([gateway_info, status], ("version", "gateway_version", "openshell_version"))
        observed_digest = self._recursive_value([metadata], ("image_digest", "digest", "imageDigest"))
        declared_version = spec.runtime.version.strip()
        declared_digest = spec.runtime.image_digest.strip()
        if declared_version and declared_version not in {"latest", "unknown", "*"} and observed_version:
            if declared_version != str(observed_version):
                raise OpenShellError(
                    f"runtime version mismatch: declared={declared_version} observed={observed_version}"
                )
        if declared_digest and declared_digest not in {"latest", "unknown", "*"} and observed_digest:
            if declared_digest != str(observed_digest):
                raise OpenShellError(
                    f"sandbox image digest mismatch: declared={declared_digest} observed={observed_digest}"
                )
        return {
            "declared_version": declared_version,
            "observed_version": observed_version,
            "declared_image_digest": declared_digest,
            "observed_image_digest": observed_digest,
            "version_match": observed_version is None or declared_version in {"latest", "unknown", "*", str(observed_version)},
            "image_match": observed_digest is None or declared_digest in {"latest", "unknown", "*", str(observed_digest)},
        }

    @classmethod
    def _recursive_value(cls, roots: list[Any], keys: tuple[str, ...]) -> Any | None:
        wanted = {k.lower() for k in keys}
        stack = list(roots)
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                for key, child in value.items():
                    if str(key).lower() in wanted and child not in (None, ""):
                        return child
                    stack.append(child)
            elif isinstance(value, list):
                stack.extend(value)
        return None

    def _filesystem_manifest(self, sandbox_id: str) -> dict[str, dict[str, str]]:
        result = self.runner.run(
            [self.binary, "sandbox", "exec", "-n", sandbox_id, "--no-tty", "--",
             "/bin/sh", "-lc", self._MANIFEST_CMD], timeout=60
        )
        if result.returncode != 0:
            raise OpenShellError("filesystem manifest collection failed")
        files: dict[str, dict[str, str]] = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2 or len(parts[0]) != 64:
                continue
            path = parts[1].lstrip("* ")
            files[path] = {"sha256": parts[0]}
        return files

    @staticmethod
    def _diff_manifests(before: dict[str, dict[str, str]], after: dict[str, dict[str, str]]) -> dict:
        before_paths, after_paths = set(before), set(after)
        modified = sorted(
            path for path in before_paths & after_paths
            if before[path].get("sha256") != after[path].get("sha256")
        )
        return {
            "added": sorted(after_paths - before_paths),
            "removed": sorted(before_paths - after_paths),
            "modified": modified,
        }

    def _best_effort_delete(self, sandbox_id: str) -> None:
        self.runner.run([self.binary, "sandbox", "delete", sandbox_id], timeout=60)

    def _require_run(self, sandbox_id: str) -> dict:
        try:
            return self._runs[sandbox_id]
        except KeyError as exc:
            raise OpenShellError(f"unknown sandbox {sandbox_id}") from exc

    def _json_command(self, argv: list[str]) -> dict:
        result = self.runner.run(argv, timeout=30)
        if result.returncode != 0:
            raise OpenShellError(f"command failed: {' '.join(argv)}: {result.stderr.strip()}")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise OpenShellError(f"expected JSON from {' '.join(argv)}") from exc
        if not isinstance(value, dict):
            raise OpenShellError(f"expected JSON object from {' '.join(argv)}")
        return value

    def _parse_jsonl(self, text: str) -> list[dict]:
        events: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return events

    def _sandbox_name(self, run_id: str) -> str:
        clean = re.sub(r"[^a-z0-9-]+", "-", run_id.lower()).strip("-") or "run"
        digest = hashlib.sha256(run_id.encode()).hexdigest()[:8]
        return f"skill-native-{clean[:36]}-{digest}"
