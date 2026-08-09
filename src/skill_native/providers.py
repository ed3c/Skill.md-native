from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ProviderKind(str, Enum):
    GROQ = "groq"
    GEMINI = "gemini"
    CLOUDFLARE = "cloudflare"
    LOCAL = "local"


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: ProviderKind
    base_url: str
    model: str
    quota_class: str = "free"
    api_key_env: str | None = None
    enabled: bool = True


class QuotaSnapshot(Protocol):
    remaining_requests: int | None
    remaining_tokens: int | None


class ProviderRouter:
    """Policy router for legitimate free-tier/local inference.

    Provider credentials are supplied by the operator and never discovered,
    scraped, rotated, or shared by this project.
    """

    def __init__(self, providers: list[ProviderConfig]) -> None:
        self.providers = [p for p in providers if p.enabled]

    def candidates(self, required_provider: str | None = None) -> list[ProviderConfig]:
        result = self.providers
        if required_provider:
            result = [p for p in result if p.name == required_provider]
        return sorted(
            result,
            key=lambda p: (
                0 if p.quota_class == "local" else 1 if p.quota_class == "free" else 2,
                p.name,
            ),
        )

    def choose(self, required_provider: str | None = None) -> ProviderConfig:
        candidates = self.candidates(required_provider)
        if not candidates:
            raise RuntimeError("no eligible inference provider")
        return candidates[0]
