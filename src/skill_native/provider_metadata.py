from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import InferenceReceipt


@dataclass(frozen=True)
class ProviderCapabilities:
    provider: str
    tool_calling: bool | None = None
    structured_output: bool | None = None
    context_window: int | None = None
    privacy_policy_url: str | None = None
    data_use: str = "unknown"


DEFAULT_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "groq": ProviderCapabilities(
        provider="groq",
        tool_calling=True,
        structured_output=True,
        privacy_policy_url="https://groq.com/privacy-policy/",
        data_use="provider-policy",
    ),
    "gemini": ProviderCapabilities(
        provider="gemini",
        tool_calling=True,
        structured_output=True,
        privacy_policy_url="https://ai.google.dev/gemini-api/terms",
        data_use="tier-dependent",
    ),
    "cloudflare": ProviderCapabilities(
        provider="cloudflare",
        tool_calling=None,
        structured_output=None,
        privacy_policy_url="https://www.cloudflare.com/privacypolicy/",
        data_use="provider-policy",
    ),
    "local": ProviderCapabilities(
        provider="local",
        tool_calling=None,
        structured_output=None,
        privacy_policy_url=None,
        data_use="operator-controlled",
    ),
}


@dataclass(frozen=True)
class QuotaView:
    limit_requests: int | None = None
    remaining_requests: int | None = None
    reset_seconds: float | None = None
    remaining_tokens: int | None = None


def _first_int(headers: dict[str, str], names: Iterable[str]) -> int | None:
    for name in names:
        value = headers.get(name.lower())
        if value is None:
            continue
        try:
            return int(float(value))
        except ValueError:
            continue
    return None


def _first_float(headers: dict[str, str], names: Iterable[str]) -> float | None:
    for name in names:
        value = headers.get(name.lower())
        if value is None:
            continue
        try:
            return float(value)
        except ValueError:
            continue
    return None


def normalize_quota(receipt: InferenceReceipt) -> QuotaView:
    headers = {k.lower(): v for k, v in receipt.rate_limit_headers.items()}
    return QuotaView(
        limit_requests=_first_int(headers, ("x-ratelimit-limit-requests", "x-ratelimit-limit", "ratelimit-limit")),
        remaining_requests=_first_int(headers, ("x-ratelimit-remaining-requests", "x-ratelimit-remaining", "ratelimit-remaining")),
        reset_seconds=_first_float(headers, ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset", "ratelimit-reset")),
        remaining_tokens=_first_int(headers, ("x-ratelimit-remaining-tokens", "x-groq-ratelimit-remaining-tokens")),
    )
