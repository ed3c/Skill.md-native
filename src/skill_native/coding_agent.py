from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

from .coding_contract import (
    CodingAgentContract,
    CodingAgentReceipt,
    CodingFileChange,
    CodingOutputFormat,
    CodingProcessResult,
    CodingRunnerConfig,
    CodingWorkspaceDiff,
)
from .evidence import canonical_digest


RUNNER_VERSION = "1.0"


@dataclass(frozen=True)
class _FileState:
    kind: str
    sha256: str
    size: int
    symlink_target: str | None = None
    unsafe_symlink: bool = False


@dataclass
class _StreamAccumulator:
    max_capture_bytes: int
    digest: Any = field(default_factory=hashlib.sha256)
    captured: bytearray = field(default_factory=bytearray)
    total_bytes: int = 0
    error: str | None = None

    def consume(self, handle: BinaryIO) -> None:
        try:
            while True:
                chunk = handle.read(64 * 1024)
                if not chunk:
                    return
                self.total_bytes += len(chunk)
                self.digest.update(chunk)
                if len(self.captured) < self.max_capture_bytes:
                    remaining = self.max_capture_bytes - len(self.captured)
                    self.captured.extend(chunk[:remaining])
        except Exception as exc:  # noqa: BLE001 - normalized into process evidence
            self.error = f"{type(exc).__name__}: {exc}"

    @property
    def text(self) -> str:
        return bytes(self.captured).decode("utf-8", errors="replace")

    @property
    def truncated(self) -> bool:
        return self.total_bytes > self.max_capture_bytes


@dataclass
class _InputWriter:
    data: bytes
    error: str | None = None

    def write(self, handle: BinaryIO) -> None:
        try:
            handle.write(self.data)
            handle.flush()
        except BrokenPipeError:
            # A child that exits before consuming the full task is handled by its
            # process result; a closed pipe is not itself a harness failure.
            pass
        except Exception as exc:  # noqa: BLE001 - normalized into process evidence
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                handle.close()
            except OSError:
                pass


@dataclass(frozen=True)
class _CapturedProcess:
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    stdout_digest: str
    stderr_digest: str
    stdout_bytes: int
    stderr_bytes: int
    output_truncated: bool
    timed_out: bool
    process_tree_terminated: bool
    duration_ms: float

    def result(self, *, passed: bool | None = None, excerpt_chars: int = 0) -> CodingProcessResult:
        base_passed = (
            self.exit_code == 0
            and not self.timed_out
            and not self.output_truncated
            and self.process_tree_terminated
        )
        effective_passed = base_passed if passed is None else (passed and base_passed)
        return CodingProcessResult(
            argv=self.argv,
            argv_digest=canonical_digest(self.argv),
            exit_code=self.exit_code,
            stdout_digest=self.stdout_digest,
            stderr_digest=self.stderr_digest,
            stdout_excerpt=self.stdout[:excerpt_chars],
            stderr_excerpt=self.stderr[:excerpt_chars],
            stdout_bytes=self.stdout_bytes,
            stderr_bytes=self.stderr_bytes,
            output_truncated=self.output_truncated,
            timed_out=self.timed_out,
            process_tree_terminated=self.process_tree_terminated,
            duration_ms=self.duration_ms,
            passed=effective_passed,
        )


def task_digest(task: str) -> str:
    return hashlib.sha256(task.encode("utf-8")).hexdigest()


def child_command_digest(command: list[str]) -> str:
    return canonical_digest(command)


def contract_digest(contract: CodingAgentContract) -> str:
    return canonical_digest(contract.model_dump(mode="json"))


def encode_runner_config(config: CodingRunnerConfig) -> str:
    payload = config.model_dump_json().encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_runner_config(value: str) -> CodingRunnerConfig:
    try:
        padding = "=" * (-len(value) % 4)
        payload = base64.urlsafe_b64decode((value + padding).encode("ascii"))
        return CodingRunnerConfig.model_validate_json(payload)
    except Exception as exc:  # noqa: BLE001 - normalized into one contract error
        raise ValueError("invalid coding runner configuration") from exc


def parse_coding_receipt(value: str) -> CodingAgentReceipt:
    stripped = value.strip()
    if not stripped:
        raise ValueError("coding runner did not emit a receipt")
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("coding runner stdout is not exactly one JSON receipt") from exc
    if not isinstance(raw, dict):
        raise ValueError("coding runner receipt must be a JSON object")
    return CodingAgentReceipt.model_validate(raw)


def build_runner_config(
    *,
    run_id: str,
    task: str,
    child_command: list[str],
    contract: CodingAgentContract,
) -> CodingRunnerConfig:
    return CodingRunnerConfig(
        run_id=run_id,
        task_digest=task_digest(task),
        child_command_digest=child_command_digest(child_command),
        contract_digest=contract_digest(contract),
        contract=contract,
    )


def execute_coding_agent(
    config: CodingRunnerConfig,
    child_command: list[str],
    task: str,
    *,
    runtime_root: Path | None = None,
) -> CodingAgentReceipt:
    contract = config.contract
    if not child_command or any(value == "" for value in child_command):
        raise ValueError("coding child command must contain non-empty argv strings")
    if task_digest(task) != config.task_digest:
        raise ValueError("coding task digest does not match runner configuration")
    if child_command_digest(child_command) != config.child_command_digest:
        raise ValueError("coding child command digest does not match runner configuration")
    if contract_digest(contract) != config.contract_digest:
        raise ValueError("coding contract digest does not match runner configuration")
    task_bytes = task.encode("utf-8")
    if len(task_bytes) > contract.max_task_bytes:
        raise ValueError("coding task exceeds max_task_bytes")

    root = (runtime_root or Path.cwd()).resolve()
    workspace = (root / contract.workspace).resolve()
    if workspace != root and root not in workspace.parents:
        raise ValueError("coding workspace escapes the runtime working directory")
    if not workspace.is_dir():
        raise ValueError(f"coding workspace does not exist: {workspace}")

    baseline = _snapshot(workspace, contract)
    baseline_digest = _snapshot_digest(baseline)

    version_capture = _run_process(
        contract.version_command,
        cwd=workspace,
        input_text=None,
        timeout_seconds=contract.version_timeout_seconds,
        max_capture_bytes=contract.max_capture_bytes,
    )
    version_output = f"{version_capture.stdout}\n{version_capture.stderr}"
    version_ok = (
        version_capture.exit_code == 0
        and not version_capture.timed_out
        and not version_capture.output_truncated
        and version_capture.process_tree_terminated
        and contract.driver_version in version_output
    )
    version_probe = version_capture.result(
        passed=version_ok,
        excerpt_chars=contract.max_output_excerpt_chars,
    )
    post_version = _snapshot(workspace, contract)
    post_version_digest = _snapshot_digest(post_version)

    agent_capture = _run_process(
        child_command,
        cwd=workspace,
        input_text=task,
        timeout_seconds=contract.agent_timeout_seconds,
        max_capture_bytes=contract.max_capture_bytes,
    )
    agent_process = agent_capture.result(
        excerpt_chars=(
            contract.max_output_excerpt_chars
            if contract.capture_agent_output_excerpts
            else 0
        )
    )
    events, raw_event_count, structured_valid, parse_error = _parse_events(
        agent_capture.stdout,
        output_format=contract.output_format,
        require_structured=contract.require_structured_events,
        max_events=contract.max_events,
        output_truncated=agent_capture.output_truncated,
    )

    after_agent = _snapshot(workspace, contract)
    workspace_diff = _build_workspace_diff(post_version, after_agent, contract)

    test_results: list[CodingProcessResult] = []
    for command in contract.test_commands:
        capture = _run_process(
            command,
            cwd=workspace,
            input_text=None,
            timeout_seconds=contract.test_timeout_seconds,
            max_capture_bytes=contract.max_capture_bytes,
        )
        test_results.append(
            capture.result(excerpt_chars=contract.max_output_excerpt_chars)
        )
    post_test = _snapshot(workspace, contract)
    post_test_digest = _snapshot_digest(post_test)

    tests_passed = all(result.passed for result in test_results)
    output_within_limit = (
        not version_probe.output_truncated
        and not agent_process.output_truncated
        and all(not result.output_truncated for result in test_results)
    )
    process_trees_terminated = (
        version_probe.process_tree_terminated
        and agent_process.process_tree_terminated
        and all(result.process_tree_terminated for result in test_results)
    )
    policy_checks = {
        "driver_version_verified": version_probe.passed,
        "agent_exit_zero": agent_process.passed,
        "structured_events_valid": structured_valid,
        "tests_passed": tests_passed,
        "allowed_changes": not workspace_diff.disallowed_paths,
        "protected_paths_unchanged": not workspace_diff.protected_paths,
        "changed_file_budget": workspace_diff.changed_files <= contract.max_changed_files,
        "changed_byte_budget": workspace_diff.changed_bytes <= contract.max_changed_bytes,
        "symlink_safe": not workspace_diff.unsafe_symlinks,
        "output_within_limit": output_within_limit,
        "process_trees_terminated": process_trees_terminated,
        "version_probe_preserved_workspace": baseline_digest == post_version_digest,
        "tests_preserved_workspace": workspace_diff.after_digest == post_test_digest,
    }
    outcome = "pass" if all(policy_checks.values()) else "fail"
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "runner_version": RUNNER_VERSION,
        "run_id": config.run_id,
        "driver": contract.driver,
        "driver_version": contract.driver_version,
        "task_digest": config.task_digest,
        "child_command_digest": config.child_command_digest,
        "contract_digest": config.contract_digest,
        "baseline_workspace_digest": baseline_digest,
        "post_version_workspace_digest": post_version_digest,
        "version_probe": version_probe,
        "agent_process": agent_process,
        "structured_events_valid": structured_valid,
        "raw_event_count": raw_event_count,
        "event_parse_error": parse_error,
        "agent_events": events,
        "workspace_diff": workspace_diff,
        "post_test_workspace_digest": post_test_digest,
        "test_results": test_results,
        "policy_checks": policy_checks,
        "outcome": outcome,
    }
    normalized = _json_payload(payload)
    return CodingAgentReceipt.model_validate(
        {**normalized, "receipt_digest": canonical_digest(normalized)}
    )


def _run_process(
    argv: list[str],
    *,
    cwd: Path,
    input_text: str | None,
    timeout_seconds: int,
    max_capture_bytes: int,
) -> _CapturedProcess:
    started = time.monotonic()
    timed_out = False
    exit_code = 127
    process_tree_terminated = True
    stdout_capture = _StreamAccumulator(max_capture_bytes=max_capture_bytes)
    stderr_capture = _StreamAccumulator(max_capture_bytes=max_capture_bytes)
    input_writer = _InputWriter(input_text.encode("utf-8")) if input_text is not None else None
    process: subprocess.Popen[bytes] | None = None
    output_threads: list[threading.Thread] = []
    input_thread: threading.Thread | None = None

    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            close_fds=True,
            start_new_session=(os.name == "posix"),
        )
        assert process.stdout is not None
        assert process.stderr is not None
        output_threads = [
            threading.Thread(
                target=stdout_capture.consume,
                args=(process.stdout,),
                name="coding-runner-stdout",
                daemon=True,
            ),
            threading.Thread(
                target=stderr_capture.consume,
                args=(process.stderr,),
                name="coding-runner-stderr",
                daemon=True,
            ),
        ]
        for thread in output_threads:
            thread.start()

        if input_writer is not None and process.stdin is not None:
            input_thread = threading.Thread(
                target=input_writer.write,
                args=(process.stdin,),
                name="coding-runner-stdin",
                daemon=True,
            )
            input_thread.start()

        # Start the timeout immediately after process launch. The task writer runs
        # concurrently, so an agent that never reads stdin cannot block the
        # trusted wrapper before timeout enforcement begins.
        try:
            exit_code = int(process.wait(timeout=timeout_seconds))
        except subprocess.TimeoutExpired:
            timed_out = True
            process_tree_terminated = _terminate_process_tree(process)
            try:
                exit_code = int(process.wait(timeout=5))
            except subprocess.TimeoutExpired:
                process.kill()
                exit_code = int(process.wait(timeout=5))
        else:
            process_tree_terminated = _terminate_process_tree(process)
    except OSError as exc:
        message = str(exc).encode("utf-8", errors="replace")
        stderr_capture.total_bytes = len(message)
        stderr_capture.digest.update(message)
        stderr_capture.captured.extend(message[:max_capture_bytes])
        exit_code = 127
    finally:
        if input_thread is not None:
            input_thread.join(timeout=5)
            if input_thread.is_alive():
                process_tree_terminated = False
        for thread in output_threads:
            thread.join(timeout=5)
        if any(thread.is_alive() for thread in output_threads):
            process_tree_terminated = False
        if process is not None:
            for handle in (process.stdin, process.stdout, process.stderr):
                if handle is not None:
                    try:
                        handle.close()
                    except OSError:
                        pass

    stream_errors = [
        error for error in (stdout_capture.error, stderr_capture.error) if error is not None
    ]
    if input_writer is not None and input_writer.error is not None:
        stream_errors.append(input_writer.error)
    if stream_errors:
        process_tree_terminated = False
        encoded = ("; ".join(stream_errors)).encode("utf-8", errors="replace")
        if stderr_capture.total_bytes == 0:
            stderr_capture.total_bytes = len(encoded)
            stderr_capture.digest.update(encoded)
            stderr_capture.captured.extend(encoded[:max_capture_bytes])

    return _CapturedProcess(
        argv=list(argv),
        exit_code=exit_code,
        stdout=stdout_capture.text,
        stderr=stderr_capture.text,
        stdout_digest=stdout_capture.digest.hexdigest(),
        stderr_digest=stderr_capture.digest.hexdigest(),
        stdout_bytes=stdout_capture.total_bytes,
        stderr_bytes=stderr_capture.total_bytes,
        output_truncated=stdout_capture.truncated or stderr_capture.truncated,
        timed_out=timed_out,
        process_tree_terminated=process_tree_terminated,
        duration_ms=(time.monotonic() - started) * 1000,
    )


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> bool:
    """Ensure descendants do not outlive a verification step.

    The agent and every test are started in a fresh POSIX session. Even after the
    direct child exits, a background descendant may keep the process group alive.
    The runner terminates that group before taking the next workspace snapshot.
    """

    if os.name != "posix":
        if process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                return False
        return True

    pgid = process.pid
    if not _process_group_exists(pgid):
        return True
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if not _process_group_exists(pgid):
            return True
        time.sleep(0.02)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if not _process_group_exists(pgid):
            return True
        time.sleep(0.02)
    return not _process_group_exists(pgid)


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _parse_events(
    stdout: str,
    *,
    output_format: CodingOutputFormat,
    require_structured: bool,
    max_events: int,
    output_truncated: bool,
) -> tuple[list[dict[str, Any]], int, bool, str | None]:
    if output_truncated:
        return [], 0, False, "agent output exceeded max_capture_bytes"
    if output_format is CodingOutputFormat.TEXT:
        return [], 0, not require_structured, (
            "structured events are required but output_format=text"
            if require_structured
            else None
        )
    try:
        if output_format is CodingOutputFormat.JSONL:
            raw_events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        else:
            parsed = json.loads(stdout)
            raw_events = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError as exc:
        return [], 0, False, f"invalid {output_format.value} event stream: {exc.msg}"
    if not raw_events:
        return [], 0, not require_structured, (
            "structured event stream is empty" if require_structured else None
        )
    if any(not isinstance(event, dict) for event in raw_events):
        return [], len(raw_events), False, "structured event stream contains a non-object"
    if len(raw_events) > max_events:
        return [], len(raw_events), False, "structured event count exceeds max_events"
    return (
        [_safe_event(index, event) for index, event in enumerate(raw_events)],
        len(raw_events),
        True,
        None,
    )


def _safe_event(index: int, event: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {
        "index": index,
        "event_digest": canonical_digest(event),
    }
    for key in ("type", "kind", "status", "name", "id", "tool", "exit_code"):
        value = event.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            if value is not None:
                safe[key] = value
    return safe


def _snapshot(workspace: Path, contract: CodingAgentContract) -> dict[str, _FileState]:
    result: dict[str, _FileState] = {}
    for root_value, dirs, files in os.walk(workspace, followlinks=False):
        root = Path(root_value)
        kept_dirs: list[str] = []
        for name in dirs:
            path = root / name
            rel = path.relative_to(workspace).as_posix()
            if _matches(rel, contract.ignored_globs):
                continue
            if path.is_symlink():
                result[rel] = _symlink_state(path, workspace)
            else:
                kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in files:
            path = root / name
            rel = path.relative_to(workspace).as_posix()
            if _matches(rel, contract.ignored_globs):
                continue
            if path.is_symlink():
                result[rel] = _symlink_state(path, workspace)
                continue
            if not path.is_file():
                continue
            result[rel] = _file_state(path)
    return result


def _file_state(path: Path) -> _FileState:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return _FileState(kind="file", sha256=digest.hexdigest(), size=size)


def _symlink_state(path: Path, workspace: Path) -> _FileState:
    target = os.readlink(path)
    resolved = (path.parent / target).resolve(strict=False)
    unsafe = resolved != workspace and workspace not in resolved.parents
    encoded = target.encode("utf-8", errors="surrogateescape")
    return _FileState(
        kind="symlink",
        sha256=hashlib.sha256(encoded).hexdigest(),
        size=len(encoded),
        symlink_target=target,
        unsafe_symlink=unsafe,
    )


def _build_workspace_diff(
    before: dict[str, _FileState],
    after: dict[str, _FileState],
    contract: CodingAgentContract,
) -> CodingWorkspaceDiff:
    changes: list[CodingFileChange] = []
    before_paths, after_paths = set(before), set(after)
    for path in sorted(before_paths | after_paths):
        before_state = before.get(path)
        after_state = after.get(path)
        if before_state == after_state:
            continue
        if before_state is None:
            status = "added"
        elif after_state is None:
            status = "removed"
        else:
            status = "modified"
        changes.append(
            CodingFileChange(
                path=path,
                status=status,
                before_kind=before_state.kind if before_state else None,
                after_kind=after_state.kind if after_state else None,
                before_sha256=before_state.sha256 if before_state else None,
                after_sha256=after_state.sha256 if after_state else None,
                before_size=before_state.size if before_state else 0,
                after_size=after_state.size if after_state else 0,
                bytes_changed=max(
                    before_state.size if before_state else 0,
                    after_state.size if after_state else 0,
                ),
                symlink_target=(after_state or before_state).symlink_target,
            )
        )
    disallowed = sorted(
        {
            change.path
            for change in changes
            if not _matches(change.path, contract.allowed_change_globs)
        }
    )
    protected = sorted(
        {
            change.path
            for change in changes
            if _matches(change.path, contract.protected_change_globs)
        }
    )
    unsafe_symlinks = sorted(
        {
            path
            for path, state in after.items()
            if state.kind == "symlink" and state.unsafe_symlink
        }
    )
    payload: dict[str, Any] = {
        "before_digest": _snapshot_digest(before),
        "after_digest": _snapshot_digest(after),
        "changes": changes,
        "changed_files": len(changes),
        "changed_bytes": sum(change.bytes_changed for change in changes),
        "disallowed_paths": disallowed,
        "protected_paths": protected,
        "unsafe_symlinks": unsafe_symlinks,
    }
    normalized = _json_payload(payload)
    return CodingWorkspaceDiff.model_validate(
        {**normalized, "diff_digest": canonical_digest(normalized)}
    )


def _snapshot_digest(snapshot: dict[str, _FileState]) -> str:
    payload = {
        path: {
            "kind": value.kind,
            "sha256": value.sha256,
            "size": value.size,
            "symlink_target": value.symlink_target,
            "unsafe_symlink": value.unsafe_symlink,
        }
        for path, value in sorted(snapshot.items())
    }
    return canonical_digest(payload)


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _json_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_payload(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def main() -> None:
    parser = argparse.ArgumentParser(prog="skill-native-coding-runner")
    parser.add_argument("--config-b64", required=True)
    parser.add_argument("child_argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    child_argv = list(args.child_argv)
    if child_argv and child_argv[0] == "--":
        child_argv = child_argv[1:]
    try:
        config = decode_runner_config(args.config_b64)
        receipt = execute_coding_agent(config, child_argv, sys.stdin.read())
    except Exception as exc:  # noqa: BLE001 - runner must fail closed at its process boundary
        print(
            json.dumps(
                {"error": type(exc).__name__, "message": str(exc)},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    print(receipt.model_dump_json())
    raise SystemExit(0 if receipt.outcome == "pass" else 2)


if __name__ == "__main__":
    main()
