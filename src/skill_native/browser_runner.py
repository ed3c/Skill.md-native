from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import mimetypes
import os
import stat
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .browser_contract import (
    AssertTextAction,
    AssertTitleAction,
    AssertURLAction,
    BrowserArtifact,
    BrowserContract,
    BrowserEvent,
    BrowserReceipt,
    BrowserRunnerConfig,
    ClickAction,
    FillAction,
    GotoAction,
    PressAction,
    ScreenshotAction,
    SelectAction,
    WaitForAction,
    decode_browser_runner_config,
)
from .evidence import canonical_digest

_RUNNER_VERSION = "0.1.0"


class BrowserRunnerError(RuntimeError):
    pass


class _ArtifactStore:
    def __init__(self, workspace: Path, config: BrowserRunnerConfig) -> None:
        workspace = workspace.resolve()
        root = (workspace / config.contract.artifact_root / config.run_id).resolve()
        try:
            root.relative_to(workspace)
        except ValueError as exc:
            raise BrowserRunnerError("artifact root escapes the browser workspace") from exc
        if root.exists():
            raise BrowserRunnerError("browser artifact root already exists")
        root.mkdir(parents=True, mode=0o700)
        if root.is_symlink():
            raise BrowserRunnerError("browser artifact root must not be a symlink")
        self.root = root
        self.max_bytes = config.contract.max_artifact_bytes
        self.max_download_bytes = config.contract.max_download_bytes
        self.total_bytes = 0
        self.artifacts: list[BrowserArtifact] = []

    def write_text(
        self,
        kind: str,
        relative_path: str,
        value: str,
        *,
        max_bytes: int,
        media_type: str,
        sensitivity: str = "internal",
    ) -> BrowserArtifact:
        payload = value.encode("utf-8")
        if len(payload) > max_bytes:
            raise BrowserRunnerError(
                f"{kind} artifact exceeds its byte budget: {len(payload)}>{max_bytes}"
            )
        path = self._path(relative_path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self._register(
            kind,
            relative_path,
            path,
            media_type=media_type,
            sensitivity=sensitivity,
        )

    def screenshot(
        self,
        page: Any,
        relative_path: str,
        *,
        full_page: bool,
    ) -> BrowserArtifact:
        path = self._path(relative_path)
        if path.exists():
            raise BrowserRunnerError("screenshot target already exists")
        page.screenshot(path=str(path), full_page=full_page)
        return self._register(
            "screenshot",
            relative_path,
            path,
            media_type="image/png",
            sensitivity="sensitive",
        )

    def download(self, download: Any, relative_path: str) -> BrowserArtifact:
        path = self._path(relative_path)
        if path.exists():
            raise BrowserRunnerError("download target already exists")
        download.save_as(str(path))
        artifact = self._register(
            "download",
            relative_path,
            path,
            media_type=mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
            sensitivity="sensitive",
        )
        if artifact.bytes > self.max_download_bytes:
            raise BrowserRunnerError(
                "download exceeds browser max_download_bytes: "
                f"{artifact.bytes}>{self.max_download_bytes}"
            )
        return artifact

    def _path(self, relative_path: str) -> Path:
        normalized = relative_path.replace("\\", "/")
        parts = Path(normalized).parts
        if not normalized or Path(normalized).is_absolute() or any(
            part in {"", ".", ".."} for part in parts
        ):
            raise BrowserRunnerError("browser artifact path is unsafe")
        path = (self.root / normalized).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise BrowserRunnerError("browser artifact path escapes artifact root") from exc
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink():
            raise BrowserRunnerError("browser artifact parent must not be a symlink")
        return path

    def _register(
        self,
        kind: str,
        relative_path: str,
        path: Path,
        *,
        media_type: str,
        sensitivity: str,
    ) -> BrowserArtifact:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise BrowserRunnerError("browser artifact must be a regular file")
        size = info.st_size
        if self.total_bytes + size > self.max_bytes:
            raise BrowserRunnerError(
                "browser artifacts exceed max_artifact_bytes: "
                f"{self.total_bytes + size}>{self.max_bytes}"
            )
        digest = _file_digest(path)
        artifact = BrowserArtifact(
            kind=kind,
            path=relative_path.replace("\\", "/"),
            sha256=digest,
            bytes=size,
            media_type=media_type,
            sensitivity=sensitivity,
        )
        self.total_bytes += size
        self.artifacts.append(artifact)
        return artifact


class _ExecutionState:
    def __init__(self, contract: BrowserContract) -> None:
        self.contract = contract
        self.events: list[BrowserEvent] = []
        self.network_events: list[dict[str, Any]] = []
        self.console_events: list[dict[str, Any]] = []
        self.page_errors: list[str] = []
        self.assertions: dict[str, bool] = {}
        self.violations: list[str] = []
        self.console_bytes = 0
        self.seen_pages = 0
        self.event_overflow = False
        self.network_overflow = False
        self.console_overflow = False
        self.expected_popup = False
        self.expected_download: str | None = None
        self.expected_dialog: str | None = None
        self.dialog_seen = False

    def event(self, kind: str, **details: Any) -> None:
        if len(self.events) >= self.contract.max_events:
            if not self.event_overflow:
                self.violations.append("event budget exceeded")
                self.event_overflow = True
            return
        self.events.append(
            BrowserEvent(
                sequence=len(self.events),
                kind=kind,
                details=_json_safe(details),
            )
        )

    def network(self, value: dict[str, Any]) -> None:
        if len(self.network_events) >= self.contract.max_network_events:
            if not self.network_overflow:
                self.violations.append("network event budget exceeded")
                self.network_overflow = True
            return
        self.network_events.append(_json_safe(value))

    def console(self, kind: str, text: str) -> None:
        payload = text.encode("utf-8", errors="replace")
        if self.console_bytes + len(payload) > self.contract.max_console_bytes:
            if not self.console_overflow:
                self.violations.append("console byte budget exceeded")
                self.console_overflow = True
            return
        self.console_bytes += len(payload)
        self.console_events.append({"type": kind, "text": text})

    def violation(self, value: str) -> None:
        if value not in self.violations:
            self.violations.append(value)
        self.event("policy_violation", value=value)


def execute_browser(config: BrowserRunnerConfig, *, workspace: Path | None = None) -> BrowserReceipt:
    workspace = (workspace or Path.cwd()).resolve()
    contract = config.contract
    state = _ExecutionState(contract)
    artifacts: list[BrowserArtifact] = []
    final_url = ""
    title = ""
    browser_version = "unavailable"
    observed_driver_version = contract.driver_version
    error: str | None = None
    page_count = 0

    try:
        observed_driver_version = importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        error = "playwright package is not installed"

    driver_version_matches = observed_driver_version == contract.driver_version
    if not driver_version_matches:
        error = (
            "playwright version mismatch: "
            f"declared={contract.driver_version} observed={observed_driver_version}"
        )

    artifact_store: _ArtifactStore | None = None
    browser: Any = None
    context: Any = None
    page: Any = None
    try:
        artifact_store = _ArtifactStore(workspace, config)
        if error is not None:
            raise BrowserRunnerError(error)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserRunnerError("playwright package is not importable") from exc

        allowed_origins = set(contract.allowed_origins)
        with sync_playwright() as playwright:
            browser_type = getattr(playwright, contract.browser)
            browser = browser_type.launch(headless=contract.headless)
            browser_version = browser.version
            context = browser.new_context(
                accept_downloads=True,
                viewport={
                    "width": contract.viewport_width,
                    "height": contract.viewport_height,
                },
                locale=contract.locale,
                service_workers="block",
            )
            context.set_default_timeout(contract.action_timeout_ms)
            context.set_default_navigation_timeout(contract.navigation_timeout_ms)

            def route_handler(route: Any, request: Any) -> None:
                url = request.url
                origin = _origin(url)
                allowed = origin is None or origin in allowed_origins
                state.network(
                    {
                        "phase": "request",
                        "method": request.method,
                        "url": _redacted_url(url),
                        "origin": origin,
                        "resource_type": request.resource_type,
                        "action": "Allowed" if allowed else "Denied",
                    }
                )
                if allowed:
                    route.continue_()
                else:
                    state.violation(f"unexpected origin: {origin}")
                    route.abort("blockedbyclient")

            context.route("**/*", route_handler)
            context.on(
                "response",
                lambda response: state.network(
                    {
                        "phase": "response",
                        "url": _redacted_url(response.url),
                        "origin": _origin(response.url),
                        "status": response.status,
                        "action": "Observed",
                    }
                ),
            )
            context.on(
                "requestfailed",
                lambda request: state.network(
                    {
                        "phase": "request_failed",
                        "url": _redacted_url(request.url),
                        "origin": _origin(request.url),
                        "failure": request.failure,
                        "action": "Observed",
                    }
                ),
            )

            def attach_page(observed_page: Any) -> None:
                state.seen_pages += 1
                state.event("page_opened", page_index=state.seen_pages - 1)
                observed_page.on(
                    "console",
                    lambda message: state.console(message.type, message.text),
                )
                observed_page.on(
                    "pageerror",
                    lambda page_error: state.page_errors.append(str(page_error)),
                )

                def on_dialog(dialog: Any) -> None:
                    expected = state.expected_dialog
                    state.event(
                        "dialog",
                        dialog_type=dialog.type,
                        message=dialog.message,
                        expected=expected is not None,
                    )
                    if expected is None:
                        state.violation("unexpected dialog")
                        dialog.dismiss()
                        return
                    state.dialog_seen = True
                    if expected == "accept":
                        dialog.accept()
                    else:
                        dialog.dismiss()

                def on_download(download: Any) -> None:
                    state.event(
                        "download",
                        suggested_filename=download.suggested_filename,
                        expected=state.expected_download is not None,
                    )
                    if state.expected_download is None:
                        state.violation("unexpected download")
                        try:
                            download.cancel()
                        except Exception:
                            pass

                observed_page.on("dialog", on_dialog)
                observed_page.on("download", on_download)

            page = context.new_page()
            attach_page(page)

            def on_new_page(new_page: Any) -> None:
                attach_page(new_page)
                if not state.expected_popup:
                    state.violation("unexpected popup")

            context.on("page", on_new_page)

            for index, action in enumerate(contract.actions):
                action_id = f"action:{index}:{action.kind}"
                try:
                    _execute_action(
                        action,
                        page,
                        state,
                        artifact_store,
                        allowed_origins,
                    )
                    state.assertions[action_id] = True
                    state.event("action", index=index, action=action.kind, passed=True)
                except Exception as exc:
                    state.assertions[action_id] = False
                    state.event(
                        "action",
                        index=index,
                        action=action.kind,
                        passed=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    raise BrowserRunnerError(
                        f"browser action {index} ({action.kind}) failed: {exc}"
                    ) from exc

            final_url = page.url
            title = page.title()
            if _origin(final_url) not in allowed_origins:
                state.violation(f"final URL origin is not allowed: {_origin(final_url)}")

            if contract.capture_dom:
                artifact_store.write_text(
                    "dom",
                    "final/dom.html",
                    page.content(),
                    max_bytes=contract.max_dom_bytes,
                    media_type="text/html",
                    sensitivity="sensitive",
                )
            if contract.capture_aria:
                aria = page.locator("body").aria_snapshot()
                artifact_store.write_text(
                    "aria",
                    "final/accessibility.yaml",
                    aria,
                    max_bytes=contract.max_aria_bytes,
                    media_type="application/yaml",
                    sensitivity="sensitive",
                )
            if contract.final_screenshot:
                artifact_store.screenshot(
                    page,
                    "final/final.png",
                    full_page=True,
                )
            page_count = state.seen_pages
            artifacts = list(artifact_store.artifacts)
    except Exception as exc:
        if error is None:
            error = f"{type(exc).__name__}: {exc}"
        if artifact_store is not None:
            artifacts = list(artifact_store.artifacts)
        if page is not None:
            try:
                final_url = page.url
                title = page.title()
            except Exception:
                pass
        page_count = state.seen_pages
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass

    policy_checks = {
        "driver_version": driver_version_matches,
        "allowed_origins": not any(
            violation.startswith("unexpected origin")
            or violation.startswith("final URL origin")
            for violation in state.violations
        ),
        "page_budget": state.seen_pages <= contract.max_pages,
        "event_budget": not state.event_overflow,
        "network_budget": not state.network_overflow,
        "console_budget": not state.console_overflow,
        "artifact_budget": (
            artifact_store is not None
            and artifact_store.total_bytes <= contract.max_artifact_bytes
        ),
        "side_effects": not any(
            value in {"unexpected popup", "unexpected dialog", "unexpected download"}
            for value in state.violations
        ),
        "assertions": bool(state.assertions) and all(state.assertions.values()),
    }
    if state.seen_pages > contract.max_pages:
        state.violation("page budget exceeded")
    passed = error is None and not state.violations and all(policy_checks.values())
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "runner_version": _RUNNER_VERSION,
        "run_id": config.run_id,
        "config_digest": config.config_digest,
        "contract_digest": config.contract_digest,
        "action_plan_digest": config.action_plan_digest,
        "driver": contract.driver,
        "driver_version": observed_driver_version,
        "browser": contract.browser,
        "browser_version": browser_version,
        "headless": contract.headless,
        "outcome": "pass" if passed else "fail",
        "final_url": final_url,
        "title": title,
        "page_count": page_count,
        "events": state.events,
        "network_events": state.network_events,
        "console_events": state.console_events,
        "page_errors": state.page_errors,
        "artifacts": artifacts,
        "assertions": state.assertions,
        "policy_checks": policy_checks,
        "violations": state.violations,
        "error": None if passed else (error or "browser policy or assertion failed"),
    }
    normalized = _json_safe(payload)
    return BrowserReceipt.model_validate(
        {**normalized, "receipt_digest": canonical_digest(normalized)}
    )


def _execute_action(
    action: Any,
    page: Any,
    state: _ExecutionState,
    artifacts: _ArtifactStore,
    allowed_origins: set[str],
) -> None:
    timeout = state.contract.action_timeout_ms
    if isinstance(action, GotoAction):
        page.goto(action.url, wait_until=action.wait_until, timeout=state.contract.navigation_timeout_ms)
        return
    if isinstance(action, FillAction):
        page.locator(action.selector).fill(action.value, timeout=timeout)
        return
    if isinstance(action, SelectAction):
        page.locator(action.selector).select_option(action.value, timeout=timeout)
        return
    if isinstance(action, PressAction):
        page.locator(action.selector).press(action.key, timeout=timeout)
        return
    if isinstance(action, WaitForAction):
        page.locator(action.selector).wait_for(state=action.state, timeout=timeout)
        return
    if isinstance(action, ScreenshotAction):
        name = action.name if action.name.endswith(".png") else f"{action.name}.png"
        artifacts.screenshot(
            page,
            f"screenshots/{name}",
            full_page=action.full_page,
        )
        return
    if isinstance(action, AssertTextAction):
        observed = page.locator(action.selector).text_content(timeout=timeout) or ""
        passed = observed == action.value if action.match == "exact" else action.value in observed
        if not passed:
            raise BrowserRunnerError(
                f"text assertion failed for {action.selector!r}: {observed!r}"
            )
        return
    if isinstance(action, AssertURLAction):
        if page.url != action.value:
            raise BrowserRunnerError(
                f"URL assertion failed: observed={page.url!r} expected={action.value!r}"
            )
        return
    if isinstance(action, AssertTitleAction):
        observed = page.title()
        passed = observed == action.value if action.match == "exact" else action.value in observed
        if not passed:
            raise BrowserRunnerError(
                f"title assertion failed: observed={observed!r} expected={action.value!r}"
            )
        return
    if isinstance(action, ClickAction):
        locator = page.locator(action.selector)
        if action.expect_popup:
            state.expected_popup = True
            try:
                with page.expect_popup(timeout=timeout) as popup_info:
                    locator.click(timeout=timeout)
                popup = popup_info.value
                popup.wait_for_load_state("domcontentloaded", timeout=state.contract.navigation_timeout_ms)
                origin = _origin(popup.url)
                if origin not in allowed_origins:
                    state.violation(f"unexpected origin: {origin}")
                popup.close()
            finally:
                state.expected_popup = False
            return
        if action.download_name is not None:
            state.expected_download = action.download_name
            try:
                with page.expect_download(timeout=timeout) as download_info:
                    locator.click(timeout=timeout)
                download = download_info.value
                artifacts.download(
                    download,
                    f"downloads/{action.download_name}",
                )
            finally:
                state.expected_download = None
            return
        if action.dialog_action is not None:
            state.expected_dialog = action.dialog_action
            state.dialog_seen = False
            try:
                locator.click(timeout=timeout)
                if not state.dialog_seen:
                    raise BrowserRunnerError("expected dialog was not observed")
            finally:
                state.expected_dialog = None
            return
        locator.click(timeout=timeout)
        return
    raise BrowserRunnerError(f"unsupported browser action: {type(action).__name__}")


def _origin(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme in {"about", "data", "blob"}:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "invalid"
    port = parsed.port
    default = (parsed.scheme == "http" and port in {None, 80}) or (
        parsed.scheme == "https" and port in {None, 443}
    )
    authority = parsed.hostname.lower() if default else f"{parsed.hostname.lower()}:{port}"
    return f"{parsed.scheme.lower()}://{authority}"


def _redacted_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(child) for child in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(prog="skill-native-browser-runner")
    parser.add_argument("--config-b64", required=True)
    args = parser.parse_args()
    try:
        config = decode_browser_runner_config(args.config_b64)
        receipt = execute_browser(config)
    except Exception as exc:
        parser.exit(2, f"skill-native-browser-runner: {type(exc).__name__}: {exc}\n")
    print(
        json.dumps(
            receipt.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    raise SystemExit(0 if receipt.outcome == "pass" else 1)


if __name__ == "__main__":
    main()
