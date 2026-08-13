from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .android_contract import (
    AndroidContract,
    android_action_plan_digest,
    android_contract_digest,
)
from .evidence import canonical_digest

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"


class AndroidCompileError(ValueError):
    """Raised when Android compile-time continuity cannot be preserved."""


class AndroidRunnerConfig(BaseModel):
    """Canonical trusted-runner input produced before any ADB process exists."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1, max_length=256)
    contract: AndroidContract
    contract_digest: str = Field(pattern=_DIGEST_PATTERN)
    action_plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    config_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_continuity(self) -> "AndroidRunnerConfig":
        if self.contract_digest != android_contract_digest(self.contract):
            raise ValueError("android contract digest does not match contract payload")
        if self.action_plan_digest != android_action_plan_digest(self.contract.actions):
            raise ValueError("android action-plan digest does not match actions")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"config_digest"})
        )
        if self.config_digest != expected:
            raise ValueError("android runner config digest does not match payload")
        return self


def build_android_runner_config(*, run_id: str, contract: AndroidContract) -> AndroidRunnerConfig:
    payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "contract": contract.model_dump(mode="json"),
        "contract_digest": android_contract_digest(contract),
        "action_plan_digest": android_action_plan_digest(contract.actions),
    }
    return AndroidRunnerConfig.model_validate(
        {**payload, "config_digest": canonical_digest(payload)}
    )


def encode_android_runner_stdin(config: AndroidRunnerConfig) -> str:
    """Return the exact canonical JSON bytes that a trusted runner may consume on stdin."""

    return json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def android_runner_command() -> list[str]:
    """Compile the public argv boundary without exposing contract/action contents."""

    return ["skill-native-android-runner", "--config-stdin"]


def android_runner_stdin_digest(config: AndroidRunnerConfig) -> str:
    return canonical_digest(encode_android_runner_stdin(config))


__all__ = [
    "AndroidCompileError",
    "AndroidRunnerConfig",
    "android_runner_command",
    "android_runner_stdin_digest",
    "build_android_runner_config",
    "encode_android_runner_stdin",
]
