from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence import canonical_digest

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_ANDROID_PACKAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+$")
_ANDROID_ACTIVITY = re.compile(r"^(?:\.)?[A-Za-z][A-Za-z0-9_.$]*$")
_ANDROID_ABI = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_SERIAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class AndroidContractError(ValueError):
    """Raised when an Android Harness contract fails closed."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartActivityAction(_StrictModel):
    kind: Literal["start_activity"] = "start_activity"
    package: str = Field(min_length=3, max_length=255)
    activity: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def safe_component(self) -> "StartActivityAction":
        if not _ANDROID_PACKAGE.fullmatch(self.package):
            raise ValueError("package must be a canonical Android package name")
        if not _ANDROID_ACTIVITY.fullmatch(self.activity):
            raise ValueError("activity must be a safe Android activity name")
        return self


class KeyEventAction(_StrictModel):
    kind: Literal["keyevent"] = "keyevent"
    keycode: int = Field(ge=0, le=1000)


class TapAction(_StrictModel):
    kind: Literal["tap"] = "tap"
    x: int = Field(ge=0, le=10000)
    y: int = Field(ge=0, le=10000)


class SwipeAction(_StrictModel):
    kind: Literal["swipe"] = "swipe"
    start_x: int = Field(ge=0, le=10000)
    start_y: int = Field(ge=0, le=10000)
    end_x: int = Field(ge=0, le=10000)
    end_y: int = Field(ge=0, le=10000)
    duration_ms: int = Field(default=300, ge=1, le=10000)


class WaitAction(_StrictModel):
    kind: Literal["wait"] = "wait"
    duration_ms: int = Field(ge=1, le=30000)


class WaitForPackageAction(_StrictModel):
    kind: Literal["wait_for_package"] = "wait_for_package"
    package: str = Field(min_length=3, max_length=255)
    timeout_ms: int = Field(default=10000, ge=100, le=120000)

    @model_validator(mode="after")
    def safe_package(self) -> "WaitForPackageAction":
        if not _ANDROID_PACKAGE.fullmatch(self.package):
            raise ValueError("package must be a canonical Android package name")
        return self


class WaitForActivityAction(_StrictModel):
    kind: Literal["wait_for_activity"] = "wait_for_activity"
    package: str = Field(min_length=3, max_length=255)
    activity: str = Field(min_length=1, max_length=255)
    timeout_ms: int = Field(default=10000, ge=100, le=120000)

    @model_validator(mode="after")
    def safe_component(self) -> "WaitForActivityAction":
        if not _ANDROID_PACKAGE.fullmatch(self.package):
            raise ValueError("package must be a canonical Android package name")
        if not _ANDROID_ACTIVITY.fullmatch(self.activity):
            raise ValueError("activity must be a safe Android activity name")
        return self


class WaitForUiTextAction(_StrictModel):
    kind: Literal["wait_for_ui_text"] = "wait_for_ui_text"
    value: str = Field(min_length=1, max_length=512)
    match: Literal["contains", "exact"] = "contains"
    timeout_ms: int = Field(default=10000, ge=100, le=120000)


class CaptureUiHierarchyAction(_StrictModel):
    kind: Literal["capture_ui_hierarchy"] = "capture_ui_hierarchy"
    name: str = Field(default="ui", min_length=1, max_length=128)

    @model_validator(mode="after")
    def safe_name(self) -> "CaptureUiHierarchyAction":
        if not _SAFE_NAME.fullmatch(self.name):
            raise ValueError("UI hierarchy name must be a safe relative file name")
        return self


class CaptureScreenshotAction(_StrictModel):
    kind: Literal["capture_screenshot"] = "capture_screenshot"
    name: str = Field(default="screen", min_length=1, max_length=128)

    @model_validator(mode="after")
    def safe_name(self) -> "CaptureScreenshotAction":
        if not _SAFE_NAME.fullmatch(self.name):
            raise ValueError("screenshot name must be a safe relative file name")
        return self


AndroidAction = Annotated[
    Union[
        StartActivityAction,
        KeyEventAction,
        TapAction,
        SwipeAction,
        WaitAction,
        WaitForPackageAction,
        WaitForActivityAction,
        WaitForUiTextAction,
        CaptureUiHierarchyAction,
        CaptureScreenshotAction,
    ],
    Field(discriminator="kind"),
]


class AndroidDeviceConstraint(_StrictModel):
    serial: str | None = Field(default=None, max_length=128)
    min_api_level: int | None = Field(default=None, ge=21, le=100)
    max_api_level: int | None = Field(default=None, ge=21, le=100)
    allowed_abis: list[str] = Field(default_factory=list, max_length=16)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    product: str | None = Field(default=None, min_length=1, max_length=128)
    build_id: str | None = Field(default=None, min_length=1, max_length=128)
    fingerprint: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_constraint(self) -> "AndroidDeviceConstraint":
        if self.serial is not None and not _SAFE_SERIAL.fullmatch(self.serial):
            raise ValueError("device serial contains unsafe characters")
        if (
            self.min_api_level is not None
            and self.max_api_level is not None
            and self.min_api_level > self.max_api_level
        ):
            raise ValueError("min_api_level must not exceed max_api_level")
        if any(not _ANDROID_ABI.fullmatch(value) for value in self.allowed_abis):
            raise ValueError("allowed_abis contains an unsafe ABI token")
        if self.allowed_abis != sorted(set(self.allowed_abis)):
            raise ValueError("allowed_abis must be sorted and unique")
        return self


class AndroidFinalAssertion(_StrictModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    kind: Literal["package", "activity", "ui_text"]
    value: str = Field(min_length=1, max_length=512)
    match: Literal["contains", "exact"] = "exact"

    @model_validator(mode="after")
    def validate_value(self) -> "AndroidFinalAssertion":
        if self.kind == "package" and not _ANDROID_PACKAGE.fullmatch(self.value):
            raise ValueError("package assertion must use a canonical Android package name")
        return self


class AndroidContract(_StrictModel):
    """Compile-time Android contract. Execution is implemented by a later trusted runner slice."""

    schema_version: Literal["1.0"] = "1.0"
    driver: Literal["adb"] = "adb"
    adb_version: str = Field(min_length=1, max_length=128)
    adb_sha256: str = Field(pattern=_DIGEST_PATTERN)
    device: AndroidDeviceConstraint = Field(default_factory=AndroidDeviceConstraint)
    actions: list[AndroidAction] = Field(min_length=1, max_length=200)
    final_assertions: list[AndroidFinalAssertion] = Field(min_length=1, max_length=64)
    artifact_root: str = ".skill-native/android-artifacts"
    action_timeout_ms: int = Field(default=15000, ge=100, le=180000)
    max_ui_hierarchy_bytes: int = Field(default=2_000_000, ge=1, le=50_000_000)
    max_screenshot_bytes: int = Field(default=20_000_000, ge=1, le=250_000_000)
    max_logcat_bytes: int = Field(default=1_000_000, ge=0, le=50_000_000)
    max_artifact_bytes: int = Field(default=50_000_000, ge=1, le=1_000_000_000)

    @model_validator(mode="after")
    def validate_contract(self) -> "AndroidContract":
        if _unsafe_relative_path(self.artifact_root):
            raise ValueError("artifact_root must be a safe relative path")
        assertion_ids = [assertion.id for assertion in self.final_assertions]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("final assertion ids must be unique")
        ui_names = [
            action.name
            for action in self.actions
            if isinstance(action, CaptureUiHierarchyAction)
        ]
        if len(ui_names) != len(set(ui_names)):
            raise ValueError("UI hierarchy artifact names must be unique")
        screenshot_names = [
            action.name
            for action in self.actions
            if isinstance(action, CaptureScreenshotAction)
        ]
        if len(screenshot_names) != len(set(screenshot_names)):
            raise ValueError("screenshot artifact names must be unique")
        return self


def android_contract_digest(contract: AndroidContract) -> str:
    return canonical_digest(contract.model_dump(mode="json"))


def android_action_plan_digest(actions: list[AndroidAction]) -> str:
    return canonical_digest([action.model_dump(mode="json") for action in actions])


def _unsafe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        not value
        or path.is_absolute()
        or value.startswith("~")
        or any(part in {"", ".", ".."} for part in path.parts)
    )
