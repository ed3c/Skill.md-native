from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence import canonical_digest


_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_MUTABLE_VERSIONS = frozenset({"latest", "main", "master", "head", "*", "unknown"})
_MANDATORY_PROTECTED_GLOBS = frozenset(
    {
        ".git",
        ".git/**",
        ".skill-native",
        ".skill-native/**",
        "AGENTS.md",
        "**/AGENTS.md",
        "CLAUDE.md",
        "**/CLAUDE.md",
        ".codex",
        ".codex/**",
        "**/.codex/**",
        ".claude",
        ".claude/**",
        "**/.claude/**",
    }
)
_SAFE_IGNORED_GLOBS = frozenset(
    {
        "__pycache__",
        "**/__pycache__/**",
        "*.pyc",
        "**/*.pyc",
        ".pytest_cache",
        ".pytest_cache/**",
        "**/.pytest_cache/**",
    }
)
_POLICY_CHECK_IDS = frozenset(
    {
        "driver_version_verified",
        "agent_exit_zero",
        "structured_events_valid",
        "tests_passed",
        "allowed_changes",
        "protected_paths_unchanged",
        "changed_file_budget",
        "changed_byte_budget",
        "symlink_safe",
        "output_within_limit",
        "process_trees_terminated",
        "version_probe_preserved_workspace",
        "tests_preserved_workspace",
    }
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CodingAgentDriver(str, Enum):
    GENERIC = "generic"
    CODEX = "codex"
    GEMINI = "gemini"
    QWEN = "qwen"
    OPENHANDS = "openhands"


class CodingOutputFormat(str, Enum):
    JSONL = "jsonl"
    JSON = "json"
    TEXT = "text"


class CodingAgentContract(_StrictModel):
    """Trusted wrapper policy for one coding-agent execution.

    The child command still comes from ``execution.command``. This contract defines
    how the trusted runner verifies the child, workspace and deterministic tests.
    """

    driver: CodingAgentDriver
    driver_version: str = Field(min_length=1)
    output_format: CodingOutputFormat = CodingOutputFormat.JSONL
    require_structured_events: bool = True
    workspace: str = "."
    version_command: list[str] = Field(min_length=1)
    test_commands: list[list[str]] = Field(min_length=1)
    allowed_change_globs: list[str] = Field(default_factory=lambda: ["**"], min_length=1)
    protected_change_globs: list[str] = Field(
        default_factory=lambda: sorted(_MANDATORY_PROTECTED_GLOBS)
    )
    ignored_globs: list[str] = Field(
        default_factory=lambda: sorted(_SAFE_IGNORED_GLOBS)
    )
    max_changed_files: int = Field(default=50, ge=0)
    max_changed_bytes: int = Field(default=2_000_000, ge=0)
    max_task_bytes: int = Field(default=200_000, ge=1)
    max_capture_bytes: int = Field(default=2_000_000, ge=1)
    max_output_excerpt_chars: int = Field(default=2_000, ge=0, le=20_000)
    capture_agent_output_excerpts: bool = False
    max_events: int = Field(default=2_000, ge=1, le=100_000)
    agent_timeout_seconds: int = Field(default=600, ge=1)
    version_timeout_seconds: int = Field(default=30, ge=1)
    test_timeout_seconds: int = Field(default=300, ge=1)

    @model_validator(mode="after")
    def validate_contract(self) -> "CodingAgentContract":
        if self.driver_version.strip().lower() in _MUTABLE_VERSIONS:
            raise ValueError("coding.driver_version must be pinned, not mutable")
        workspace = PurePosixPath(self.workspace)
        if workspace.is_absolute() or ".." in workspace.parts:
            raise ValueError("coding.workspace must stay relative to the runtime working directory")
        for name, command in [
            ("version_command", self.version_command),
            *[(f"test_commands[{index}]", command) for index, command in enumerate(self.test_commands)],
        ]:
            if not command or any(value == "" for value in command):
                raise ValueError(f"coding.{name} must contain non-empty argv strings")
        for name, globs in (
            ("allowed_change_globs", self.allowed_change_globs),
            ("protected_change_globs", self.protected_change_globs),
            ("ignored_globs", self.ignored_globs),
        ):
            if len(set(globs)) != len(globs):
                raise ValueError(f"coding.{name} must not contain duplicates")
            for pattern in globs:
                parts = PurePosixPath(pattern).parts
                if not pattern or pattern.startswith("/") or ".." in parts:
                    raise ValueError(f"coding.{name} contains an unsafe pattern: {pattern!r}")
        missing_protected = _MANDATORY_PROTECTED_GLOBS - set(
            self.protected_change_globs
        )
        if missing_protected:
            raise ValueError(
                "coding.protected_change_globs cannot remove mandatory paths: "
                + ", ".join(sorted(missing_protected))
            )
        unsafe_ignored = set(self.ignored_globs) - _SAFE_IGNORED_GLOBS
        if unsafe_ignored:
            raise ValueError(
                "coding.ignored_globs may only contain trusted cache patterns: "
                + ", ".join(sorted(unsafe_ignored))
            )
        if self.capture_agent_output_excerpts:
            raise ValueError(
                "capture_agent_output_excerpts requires a trusted operator overlay, "
                "which is not implemented in contract v1"
            )
        if self.require_structured_events and self.output_format is CodingOutputFormat.TEXT:
            raise ValueError(
                "coding.output_format=text cannot satisfy require_structured_events=true"
            )
        return self


class CodingFileChange(_StrictModel):
    path: str = Field(min_length=1)
    status: Literal["added", "removed", "modified"]
    before_kind: Literal["file", "symlink"] | None = None
    after_kind: Literal["file", "symlink"] | None = None
    before_sha256: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    after_sha256: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    before_size: int = Field(default=0, ge=0)
    after_size: int = Field(default=0, ge=0)
    bytes_changed: int = Field(default=0, ge=0)
    symlink_target: str | None = None


class CodingWorkspaceDiff(_StrictModel):
    before_digest: str = Field(pattern=_DIGEST_PATTERN)
    after_digest: str = Field(pattern=_DIGEST_PATTERN)
    changes: list[CodingFileChange] = Field(default_factory=list)
    changed_files: int = Field(ge=0)
    changed_bytes: int = Field(ge=0)
    disallowed_paths: list[str] = Field(default_factory=list)
    protected_paths: list[str] = Field(default_factory=list)
    unsafe_symlinks: list[str] = Field(default_factory=list)
    diff_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_diff(self) -> "CodingWorkspaceDiff":
        if self.changed_files != len(self.changes):
            raise ValueError("workspace changed_files does not match changes")
        if self.changed_bytes != sum(change.bytes_changed for change in self.changes):
            raise ValueError("workspace changed_bytes does not match changes")
        for name, values in (
            ("disallowed_paths", self.disallowed_paths),
            ("protected_paths", self.protected_paths),
            ("unsafe_symlinks", self.unsafe_symlinks),
        ):
            if values != sorted(set(values)):
                raise ValueError(f"workspace {name} must be sorted and unique")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"diff_digest"}))
        if expected != self.diff_digest:
            raise ValueError("workspace diff digest does not match payload")
        return self


class CodingProcessResult(_StrictModel):
    argv: list[str] = Field(min_length=1)
    argv_digest: str = Field(pattern=_DIGEST_PATTERN)
    exit_code: int
    stdout_digest: str = Field(pattern=_DIGEST_PATTERN)
    stderr_digest: str = Field(pattern=_DIGEST_PATTERN)
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""
    stdout_bytes: int = Field(ge=0)
    stderr_bytes: int = Field(ge=0)
    output_truncated: bool = False
    timed_out: bool = False
    process_tree_terminated: bool = True
    duration_ms: float = Field(ge=0)
    passed: bool

    @model_validator(mode="after")
    def validate_process(self) -> "CodingProcessResult":
        if canonical_digest(self.argv) != self.argv_digest:
            raise ValueError("process argv digest does not match argv")
        expected_pass = (
            self.exit_code == 0
            and not self.timed_out
            and not self.output_truncated
            and self.process_tree_terminated
        )
        if self.passed and not expected_pass:
            raise ValueError("process result cannot pass with a failed process invariant")
        return self


class CodingRunnerConfig(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    task_digest: str = Field(pattern=_DIGEST_PATTERN)
    child_command_digest: str = Field(pattern=_DIGEST_PATTERN)
    contract_digest: str = Field(pattern=_DIGEST_PATTERN)
    contract: CodingAgentContract

    @model_validator(mode="after")
    def validate_config(self) -> "CodingRunnerConfig":
        expected = canonical_digest(self.contract.model_dump(mode="json"))
        if expected != self.contract_digest:
            raise ValueError("coding runner contract digest does not match contract")
        return self


class CodingAgentReceipt(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    runner_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    driver: CodingAgentDriver
    driver_version: str = Field(min_length=1)
    task_digest: str = Field(pattern=_DIGEST_PATTERN)
    child_command_digest: str = Field(pattern=_DIGEST_PATTERN)
    contract_digest: str = Field(pattern=_DIGEST_PATTERN)
    baseline_workspace_digest: str = Field(pattern=_DIGEST_PATTERN)
    post_version_workspace_digest: str = Field(pattern=_DIGEST_PATTERN)
    version_probe: CodingProcessResult
    agent_process: CodingProcessResult
    structured_events_valid: bool
    raw_event_count: int = Field(ge=0)
    event_parse_error: str | None = None
    agent_events: list[dict[str, Any]] = Field(default_factory=list)
    workspace_diff: CodingWorkspaceDiff
    post_test_workspace_digest: str = Field(pattern=_DIGEST_PATTERN)
    test_results: list[CodingProcessResult] = Field(min_length=1)
    policy_checks: dict[str, bool]
    outcome: Literal["pass", "fail"]
    receipt_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_receipt(self) -> "CodingAgentReceipt":
        if set(self.policy_checks) != _POLICY_CHECK_IDS:
            missing = sorted(_POLICY_CHECK_IDS - set(self.policy_checks))
            extra = sorted(set(self.policy_checks) - _POLICY_CHECK_IDS)
            raise ValueError(
                f"coding receipt policy checks do not match contract; missing={missing}, extra={extra}"
            )
        if self.structured_events_valid and self.raw_event_count != len(self.agent_events):
            raise ValueError("valid structured event count does not match normalized events")
        expected_checks = {
            "driver_version_verified": self.version_probe.passed,
            "agent_exit_zero": self.agent_process.passed,
            "structured_events_valid": self.structured_events_valid,
            "tests_passed": all(result.passed for result in self.test_results),
            "allowed_changes": not self.workspace_diff.disallowed_paths,
            "protected_paths_unchanged": not self.workspace_diff.protected_paths,
            "symlink_safe": not self.workspace_diff.unsafe_symlinks,
            "output_within_limit": not (
                self.version_probe.output_truncated
                or self.agent_process.output_truncated
                or any(result.output_truncated for result in self.test_results)
            ),
            "process_trees_terminated": (
                self.version_probe.process_tree_terminated
                and self.agent_process.process_tree_terminated
                and all(result.process_tree_terminated for result in self.test_results)
            ),
            "version_probe_preserved_workspace": (
                self.baseline_workspace_digest == self.post_version_workspace_digest
            ),
            "tests_preserved_workspace": (
                self.workspace_diff.after_digest == self.post_test_workspace_digest
            ),
        }
        for check_id, expected_value in expected_checks.items():
            if self.policy_checks[check_id] is not expected_value:
                raise ValueError(f"coding receipt policy check {check_id!r} is inconsistent")
        expected_outcome = (
            "pass"
            if self.version_probe.passed
            and self.agent_process.passed
            and self.structured_events_valid
            and all(result.passed for result in self.test_results)
            and all(self.policy_checks.values())
            else "fail"
        )
        if self.outcome != expected_outcome:
            raise ValueError("coding receipt outcome does not match captured results")
        expected = canonical_digest(self.model_dump(mode="json", exclude={"receipt_digest"}))
        if expected != self.receipt_digest:
            raise ValueError("coding receipt digest does not match payload")
        return self
