#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "audit" / "capability-contract.json"
STATES = {
    "PASS", "FAIL", "ABSENT", "NOT_IMPLEMENTED", "NOT_EXERCISED",
    "BLOCKED_INFRASTRUCTURE", "SKIPPED_BY_POLICY",
}
Expectation = Literal["zero", "nonzero"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def capture(*argv: str) -> str | None:
    try:
        p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def safe_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    exact = {
        "GITHUB_TOKEN", "GH_TOKEN", "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY", "GROQ_API_KEY", "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    }
    for key in list(env):
        upper = key.upper()
        if (
            key in exact or upper.endswith("_API_KEY") or upper.endswith("_SECRET")
            or upper.endswith("_PASSWORD")
            or (upper.endswith("_TOKEN") and key != "GITHUB_ACTIONS")
        ):
            env.pop(key, None)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if extra:
        env.update(extra)
    return env


@dataclass
class Check:
    check_id: str
    capability_id: str
    title: str
    status: str
    expectation: str
    command: list[str]
    exit_code: int | None
    started_at: str
    finished_at: str
    duration_seconds: float
    log_path: str
    evidence_paths: list[str]
    runtime: dict[str, Any]
    notes: list[str]


class Audit:
    def __init__(self, output: Path, clean: bool) -> None:
        self.output = output.resolve()
        if self.output in {ROOT.resolve(), Path.home().resolve(), Path("/")} or (self.output / ".git").exists():
            raise SystemExit(f"unsafe output path: {self.output}")
        if self.output.exists():
            if not clean:
                raise SystemExit(f"output exists; pass --clean: {self.output}")
            shutil.rmtree(self.output)
        self.logs = self.output / "logs"
        self.artifacts = self.output / "artifacts"
        self.logs.mkdir(parents=True)
        self.artifacts.mkdir(parents=True)
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.checks: list[Check] = []
        self.declarations: dict[str, dict[str, Any]] = {}
        self.started_at = now()

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.output).as_posix()

    def run(
        self,
        check_id: str,
        capability_id: str,
        title: str,
        command: list[str],
        *,
        expectation: Expectation = "zero",
        timeout: int = 900,
        stdout_artifact: str | None = None,
        evidence: list[Path] | None = None,
        env: dict[str, str] | None = None,
        runtime: dict[str, Any] | None = None,
        notes: list[str] | None = None,
    ) -> Check:
        started_at, start = now(), time.monotonic()
        code: int | None = None
        out = err = ""
        failure: str | None = None
        try:
            p = subprocess.run(
                command, cwd=ROOT, env=safe_env(env), capture_output=True,
                text=True, timeout=timeout, check=False,
            )
            code, out, err = p.returncode, p.stdout, p.stderr
        except FileNotFoundError as exc:
            failure = f"{type(exc).__name__}: {exc}"
        except subprocess.TimeoutExpired as exc:
            code = 124
            out, err = exc.stdout or "", exc.stderr or ""
            failure = f"timeout after {timeout}s"
        except Exception as exc:  # preserve unexpected audit failures
            failure = f"{type(exc).__name__}: {exc}"
        finished_at = now()
        duration = round(time.monotonic() - start, 6)
        log = self.logs / f"{check_id}.log"
        lines = [
            f"$ {shlex.join(command)}", f"expectation={expectation}",
            f"exit_code={code}", f"started_at={started_at}",
            f"finished_at={finished_at}", f"duration_seconds={duration}",
        ]
        if failure:
            lines += ["", "[execution_error]", failure]
        lines += ["", "[stdout]", out, "", "[stderr]", err]
        log.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        passed = failure is None and code is not None and (
            (expectation == "zero" and code == 0)
            or (expectation == "nonzero" and code != 0)
        )
        paths = [self.rel(log)]
        if stdout_artifact and out:
            target = self.output / stdout_artifact
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(out, encoding="utf-8")
            paths.append(self.rel(target))
        for root in evidence or []:
            if root.is_file():
                paths.append(self.rel(root))
            elif root.is_dir():
                paths.extend(self.rel(p) for p in sorted(root.rglob("*")) if p.is_file())
        item = Check(
            check_id, capability_id, title, "PASS" if passed else "FAIL",
            expectation, command, code, started_at, finished_at, duration,
            self.rel(log), sorted(set(paths)), runtime or {},
            (notes or []) + ([failure] if failure else []),
        )
        self.checks.append(item)
        return item

    def declare(self, capability_id: str, status: str, *notes: str) -> None:
        if status not in STATES:
            raise ValueError(status)
        self.declarations[capability_id] = {"status": status, "notes": list(notes)}

    def finish(self, subject: dict[str, Any], environment: dict[str, Any]) -> int:
        rows: list[dict[str, Any]] = []
        contract_ids = {c["id"] for c in self.contract["capabilities"]}
        observed = {c.capability_id for c in self.checks} | set(self.declarations)
        if observed - contract_ids:
            raise ValueError(f"unknown capability ids: {sorted(observed - contract_ids)}")
        for definition in self.contract["capabilities"]:
            related = [c for c in self.checks if c.capability_id == definition["id"]]
            if related:
                status = "PASS" if all(c.status == "PASS" for c in related) else "FAIL"
                evidence = sorted({p for c in related for p in c.evidence_paths})
                observed_notes = list(definition.get("notes", []))
            elif definition["id"] in self.declarations:
                value = self.declarations[definition["id"]]
                status, evidence, observed_notes = value["status"], [], value["notes"]
            else:
                status, evidence, observed_notes = "ABSENT", [], ["No check or declaration produced."]
            rows.append({
                **definition, "status": status,
                "check_ids": [c.check_id for c in related],
                "evidence_paths": evidence, "observed_notes": observed_notes,
            })
        required = [r for r in rows if r["required_in_full"] and r["status"] != "PASS"]
        gaps = [r for r in rows if not r["required_in_full"] and r["status"] != "PASS"]
        overall = "FAIL" if required else ("PASS_WITH_DECLARED_GAPS" if gaps else "PASS")
        result = {
            "schema_version": "skill-native-capability-audit/v1",
            "contract_digest": hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            "subject": subject, "environment": environment,
            "started_at": self.started_at, "finished_at": now(),
            "overall_status": overall, "capabilities": rows,
            "checks": [asdict(c) for c in self.checks],
            "required_failures": [r["id"] for r in required],
            "declared_gaps": [r["id"] for r in gaps],
            "evidence_law": "Absence, configuration, skipped execution, and prose are never PASS.",
        }
        (self.output / "capability-audit-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        summary = [
            "# Skill.md-native capability audit", "",
            f"- Overall: **{overall}**",
            f"- Subject commit: `{subject.get('commit_sha')}`",
            f"- Subject tree: `{subject.get('tree_sha')}`",
            f"- Required failures: {len(required)}",
            f"- Declared external gaps: {len(gaps)}", "",
            "| Capability | Required | Evidence level | State |",
            "|---|---:|---|---|",
        ]
        summary += [
            f"| `{r['id']}` | {'yes' if r['required_in_full'] else 'no'} | "
            f"{r['minimum_evidence_level']} | **{r['status']}** |" for r in rows
        ]
        summary += ["", "## Non-claims", ""] + [
            f"- {x}" for x in self.contract["non_claims"]
        ] + ["", "The JSON result and raw logs are authoritative."]
        (self.output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
        manifest = []
        target = self.output / "SHA256SUMS"
        for path in sorted(self.output.rglob("*")):
            if path.is_file() and path != target:
                manifest.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {self.rel(path)}")
        target.write_text("\n".join(manifest) + "\n", encoding="utf-8")
        return 1 if required else 0


def identity() -> tuple[dict[str, Any], dict[str, Any]]:
    subject = {
        "repository": os.environ.get("GITHUB_REPOSITORY", "local/unknown"),
        "commit_sha": capture("git", "rev-parse", "HEAD"),
        "tree_sha": capture("git", "rev-parse", "HEAD^{tree}"),
        "dirty": bool(capture("git", "status", "--porcelain=v1")),
        "github_ref": os.environ.get("GITHUB_REF"),
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
    }
    environment = {
        "python": sys.version, "platform": platform.platform(),
        "machine": platform.machine(),
        "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_workflow": os.environ.get("GITHUB_WORKFLOW"),
        "runner_os": os.environ.get("RUNNER_OS"),
        "runner_arch": os.environ.get("RUNNER_ARCH"),
        "docker_available": shutil.which("docker") is not None,
        "docker_version": capture("docker", "--version"),
        "node_available": shutil.which("node") is not None,
        "node_version": capture("node", "--version"),
        "npm_version": capture("npm", "--version"),
    }
    return subject, environment
