from __future__ import annotations

import base64
import json
import re
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Union
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence import canonical_digest

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class BrowserContractError(ValueError):
    """Raised when a Browser Harness contract or receipt fails closed."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GotoAction(_StrictModel):
    kind: Literal["goto"] = "goto"
    url: str = Field(min_length=1)
    wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = (
        "domcontentloaded"
    )


class ClickAction(_StrictModel):
    kind: Literal["click"] = "click"
    selector: str = Field(min_length=1)
    expect_popup: bool = False
    download_name: str | None = None
    dialog_action: Literal["accept", "dismiss"] | None = None

    @model_validator(mode="after")
    def one_expected_side_effect(self) -> "ClickAction":
        count = int(self.expect_popup) + int(self.download_name is not None) + int(
            self.dialog_action is not None
        )
        if count > 1:
            raise ValueError("click action may expect at most one popup/download/dialog")
        if self.download_name is not None and not _SAFE_NAME.fullmatch(
            self.download_name
        ):
            raise ValueError("download_name must be a safe relative file name")
        return self


class FillAction(_StrictModel):
    kind: Literal["fill"] = "fill"
    selector: str = Field(min_length=1)
    value: str


class SelectAction(_StrictModel):
    kind: Literal["select"] = "select"
    selector: str = Field(min_length=1)
    value: str


class PressAction(_StrictModel):
    kind: Literal["press"] = "press"
    selector: str = Field(min_length=1)
    key: str = Field(min_length=1, max_length=64)


class WaitForAction(_StrictModel):
    kind: Literal["wait_for"] = "wait_for"
    selector: str = Field(min_length=1)
    state: Literal["attached", "detached", "visible", "hidden"] = "visible"


class ScreenshotAction(_StrictModel):
    kind: Literal["screenshot"] = "screenshot"
    name: str = Field(min_length=1)
    full_page: bool = True

    @model_validator(mode="after")
    def safe_name(self) -> "ScreenshotAction":
        if not _SAFE_NAME.fullmatch(self.name):
            raise ValueError("screenshot name must be a safe relative file name")
        return self


class AssertTextAction(_StrictModel):
    kind: Literal["assert_text"] = "assert_text"
    selector: str = Field(min_length=1)
    value: str
    match: Literal["contains", "exact"] = "contains"


class AssertURLAction(_StrictModel):
    kind: Literal["assert_url"] = "assert_url"
    value: str = Field(min_length=1)


class AssertTitleAction(_StrictModel):
    kind: Literal["assert_title"] = "assert_title"
    value: str
    match: Literal["contains", "exact"] = "exact"


BrowserAction = Annotated[
    Union[
        GotoAction,
        ClickAction,
        FillAction,
        SelectAction,
        PressAction,
        WaitForAction,
        ScreenshotAction,
        AssertTextAction,
        AssertURLAction,
        AssertTitleAction,
    ],
    Field(discriminator="kind"),
]


class BrowserContract(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    driver: Literal["playwright-python"] = "playwright-python"
    driver_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    browser: Literal["chromium", "firefox", "webkit"] = "chromium"
    headless: bool = True
    allowed_origins: list[str] = Field(min_length=1)
    actions: list[BrowserAction] = Field(min_length=1, max_length=200)
    artifact_root: str = ".skill-native/browser-artifacts"
    viewport_width: int = Field(default=1280, ge=320, le=7680)
    viewport_height: int = Field(default=720, ge=240, le=4320)
    locale: str = Field(default="en-US", min_length=2, max_length=32)
    action_timeout_ms: int = Field(default=10_000, ge=100, le=120_000)
    navigation_timeout_ms: int = Field(default=20_000, ge=100, le=180_000)
    max_pages: int = Field(default=2, ge=1, le=20)
    max_events: int = Field(default=2_000, ge=1, le=100_000)
    max_network_events: int = Field(default=1_000, ge=1, le=100_000)
    max_console_bytes: int = Field(default=64_000, ge=0, le=10_000_000)
    max_dom_bytes: int = Field(default=1_000_000, ge=1, le=50_000_000)
    max_aria_bytes: int = Field(default=1_000_000, ge=1, le=50_000_000)
    max_artifact_bytes: int = Field(default=20_000_000, ge=1, le=1_000_000_000)
    max_download_bytes: int = Field(default=10_000_000, ge=0, le=1_000_000_000)
    capture_dom: bool = True
    capture_aria: bool = True
    final_screenshot: bool = True

    @model_validator(mode="after")
    def validate_contract(self) -> "BrowserContract":
        normalized = [_normalize_origin(value) for value in self.allowed_origins]
        if self.allowed_origins != normalized:
            raise ValueError("allowed_origins must use canonical origin spelling")
        if normalized != sorted(set(normalized)):
            raise ValueError("allowed_origins must be normalized, sorted, and unique")
        if _unsafe_relative_path(self.artifact_root):
            raise ValueError("artifact_root must be a safe relative path")
        screenshot_names = [
            action.name
            for action in self.actions
            if isinstance(action, ScreenshotAction)
        ]
        if len(screenshot_names) != len(set(screenshot_names)):
            raise ValueError("screenshot names must be unique")
        allowed = set(normalized)
        for action in self.actions:
            if isinstance(action, GotoAction):
                if _normalize_origin(action.url) not in allowed:
                    raise ValueError("goto action URL is outside allowed_origins")
            if isinstance(action, AssertURLAction):
                if _normalize_origin(action.value) not in allowed:
                    raise ValueError("assert_url value is outside allowed_origins")
        return self


class BrowserRunnerConfig(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    contract: BrowserContract
    contract_digest: str = Field(pattern=_DIGEST_PATTERN)
    action_plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    config_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_digests(self) -> "BrowserRunnerConfig":
        if self.contract_digest != browser_contract_digest(self.contract):
            raise ValueError("browser contract digest does not match contract payload")
        if self.action_plan_digest != browser_action_plan_digest(self.contract.actions):
            raise ValueError("browser action-plan digest does not match actions")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"config_digest"})
        )
        if self.config_digest != expected:
            raise ValueError("browser runner config digest does not match payload")
        return self


class BrowserEvent(_StrictModel):
    sequence: int = Field(ge=0)
    kind: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class BrowserArtifact(_StrictModel):
    kind: Literal["dom", "aria", "screenshot", "download"]
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=_DIGEST_PATTERN)
    bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1)
    sensitivity: Literal["public", "internal", "sensitive"] = "internal"

    @model_validator(mode="after")
    def safe_relative_path(self) -> "BrowserArtifact":
        if _unsafe_relative_path(self.path):
            raise ValueError("artifact path must be safe and relative")
        return self


class BrowserReceipt(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    runner_version: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    config_digest: str = Field(pattern=_DIGEST_PATTERN)
    contract_digest: str = Field(pattern=_DIGEST_PATTERN)
    action_plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    driver: Literal["playwright-python"] = "playwright-python"
    driver_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    browser: Literal["chromium", "firefox", "webkit"]
    browser_version: str = Field(min_length=1)
    headless: bool
    outcome: Literal["pass", "fail"]
    final_url: str
    title: str
    page_count: int = Field(ge=0)
    events: list[BrowserEvent]
    network_events: list[dict[str, Any]]
    console_events: list[dict[str, Any]]
    page_errors: list[str]
    artifacts: list[BrowserArtifact]
    assertions: dict[str, bool]
    policy_checks: dict[str, bool]
    violations: list[str]
    error: str | None = None
    receipt_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_receipt(self) -> "BrowserReceipt":
        if self.outcome == "pass":
            if self.error is not None:
                raise ValueError("passing browser receipt must not contain an error")
            if not all(self.assertions.values()):
                raise ValueError("passing browser receipt contains a failed assertion")
            if not all(self.policy_checks.values()):
                raise ValueError("passing browser receipt contains a failed policy check")
            if self.violations:
                raise ValueError("passing browser receipt contains policy violations")
        paths = [artifact.path for artifact in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("browser receipt contains duplicate artifact paths")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"receipt_digest"})
        )
        if self.receipt_digest != expected:
            raise ValueError("browser receipt digest does not match payload")
        return self


def browser_contract_digest(contract: BrowserContract) -> str:
    return canonical_digest(contract.model_dump(mode="json"))


def browser_action_plan_digest(actions: list[BrowserAction]) -> str:
    return canonical_digest(
        [action.model_dump(mode="json") for action in actions]
    )


def build_browser_runner_config(
    *,
    run_id: str,
    contract: BrowserContract,
) -> BrowserRunnerConfig:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "run_id": run_id,
        "contract": contract,
        "contract_digest": browser_contract_digest(contract),
        "action_plan_digest": browser_action_plan_digest(contract.actions),
    }
    normalized = _json_payload(payload)
    return BrowserRunnerConfig.model_validate(
        {**normalized, "config_digest": canonical_digest(normalized)}
    )


def encode_browser_runner_config(config: BrowserRunnerConfig) -> str:
    payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decode_browser_runner_config(value: str) -> BrowserRunnerConfig:
    try:
        raw = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise BrowserContractError("browser runner config is not valid canonical base64 JSON") from exc
    config = BrowserRunnerConfig.model_validate(parsed)
    canonical = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise BrowserContractError("browser runner config must use canonical JSON")
    return config


def parse_browser_receipt(stdout: str) -> BrowserReceipt:
    raw = stdout[:-1] if stdout.endswith("\n") else stdout
    if not raw or "\n" in raw:
        raise BrowserContractError("browser runner must emit exactly one JSON line")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BrowserContractError("browser runner output is not JSON") from exc
    receipt = BrowserReceipt.model_validate(parsed)
    canonical = json.dumps(
        receipt.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    if raw != canonical:
        raise BrowserContractError("browser receipt must use canonical JSON")
    return receipt


def _normalize_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("browser origins and URLs must use http or https")
    port = parsed.port
    default = (parsed.scheme == "http" and port in {None, 80}) or (
        parsed.scheme == "https" and port in {None, 443}
    )
    authority = parsed.hostname.lower() if default else f"{parsed.hostname.lower()}:{port}"
    return f"{parsed.scheme.lower()}://{authority}"


def _unsafe_relative_path(value: str) -> bool:
    path = PurePosixPath(value.replace("\\", "/"))
    return (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    )


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_payload(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_payload(child) for child in value]
    return value


__all__ = [
    "AssertTextAction",
    "AssertTitleAction",
    "AssertURLAction",
    "BrowserAction",
    "BrowserArtifact",
    "BrowserContract",
    "BrowserContractError",
    "BrowserEvent",
    "BrowserReceipt",
    "BrowserRunnerConfig",
    "ClickAction",
    "FillAction",
    "GotoAction",
    "PressAction",
    "ScreenshotAction",
    "SelectAction",
    "WaitForAction",
    "browser_action_plan_digest",
    "browser_contract_digest",
    "build_browser_runner_config",
    "decode_browser_runner_config",
    "encode_browser_runner_config",
    "parse_browser_receipt",
]
