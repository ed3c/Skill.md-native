from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from .models import InferenceReceipt, QuotaClass


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
    timeout_seconds: float = 60.0
    extra_headers: dict[str, str] = field(default_factory=dict)

    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


@dataclass(frozen=True)
class InferenceResult:
    text: str
    receipt: InferenceReceipt
    raw_response: dict[str, Any]


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, receipt: InferenceReceipt, retryable: bool) -> None:
        super().__init__(message)
        self.receipt = receipt
        self.retryable = retryable


class OpenAICompatibleProvider:
    """Minimal HTTP adapter for OpenAI-compatible chat-completions APIs.

    This deliberately uses HTTP rather than provider SDKs so the benchmark has
    one request path and one evidence contract across Groq, Gemini, Cloudflare,
    and local endpoints.
    """

    RATE_LIMIT_PREFIXES = (
        "retry-after",
        "x-ratelimit-",
        "ratelimit-",
        "x-groq-",
    )

    def __init__(self, config: ProviderConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self.client = client or httpx.Client(timeout=config.timeout_seconds)

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = 0.0,
    ) -> InferenceResult:
        payload: dict[str, Any] = {"model": self.config.model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        request_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        headers = {"content-type": "application/json", **self.config.extra_headers}
        api_key = os.getenv(self.config.api_key_env) if self.config.api_key_env else None
        if self.config.api_key_env and not api_key:
            receipt = self._receipt(request_hash=request_hash, error="credential_missing")
            raise ProviderError(
                f"missing credential environment variable {self.config.api_key_env}",
                receipt=receipt,
                retryable=False,
            )
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"

        started = time.perf_counter()
        try:
            response = self.client.post(self.config.chat_completions_url(), headers=headers, json=payload)
        except httpx.HTTPError as exc:
            elapsed = (time.perf_counter() - started) * 1000
            receipt = self._receipt(
                request_hash=request_hash,
                latency_ms=elapsed,
                error=f"transport:{type(exc).__name__}",
            )
            raise ProviderError(str(exc), receipt=receipt, retryable=True) from exc

        elapsed = (time.perf_counter() - started) * 1000
        rate_headers = self._rate_limit_headers(response.headers)
        try:
            body = response.json()
        except ValueError:
            body = {}

        usage = body.get("usage") if isinstance(body, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
        output_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)

        if response.status_code >= 400:
            error = f"http_{response.status_code}"
            receipt = self._receipt(
                request_hash=request_hash,
                latency_ms=elapsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                rate_limit_headers=rate_headers,
                error=error,
            )
            retryable = response.status_code == 429 or response.status_code >= 500
            raise ProviderError(error, receipt=receipt, retryable=retryable)

        text = self._extract_text(body)
        receipt = self._receipt(
            request_hash=request_hash,
            latency_ms=elapsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            rate_limit_headers=rate_headers,
        )
        return InferenceResult(text=text, receipt=receipt, raw_response=body)

    def _receipt(
        self,
        *,
        request_hash: str,
        latency_ms: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        rate_limit_headers: dict[str, str] | None = None,
        error: str | None = None,
    ) -> InferenceReceipt:
        return InferenceReceipt(
            provider=self.config.name,
            model=self.config.model,
            request_hash=request_hash,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            price_usd=0.0 if self.config.quota_class in {"free", "local"} else 0.0,
            quota_class=QuotaClass(self.config.quota_class),
            rate_limit_headers=rate_limit_headers or {},
            error=error,
        )

    def _rate_limit_headers(self, headers: httpx.Headers) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, value in headers.items():
            lower = key.lower()
            if any(lower.startswith(prefix) for prefix in self.RATE_LIMIT_PREFIXES):
                result[lower] = value
        return result

    @staticmethod
    def _extract_text(body: dict[str, Any]) -> str:
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("provider response missing choices[0].message.content") from exc
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            return "".join(parts)
        raise ValueError("unsupported provider content shape")


class ProviderRouter:
    """Policy router for legitimate free-tier/local inference.

    Provider credentials are supplied by the operator and never discovered,
    scraped, rotated, shared, or used to bypass a provider quota.
    """

    def __init__(
        self,
        providers: list[ProviderConfig],
        *,
        clients: dict[str, httpx.Client] | None = None,
    ) -> None:
        self.providers = [p for p in providers if p.enabled]
        clients = clients or {}
        self.adapters = {
            p.name: OpenAICompatibleProvider(p, client=clients.get(p.name)) for p in self.providers
        }
        self.attempt_receipts: list[InferenceReceipt] = []

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

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        required_provider: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = 0.0,
    ) -> InferenceResult:
        candidates = self.candidates(required_provider)
        if not candidates:
            raise RuntimeError("no eligible inference provider")

        last_error: ProviderError | None = None
        for config in candidates:
            try:
                result = self.adapters[config.name].complete(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self.attempt_receipts.append(result.receipt)
                return result
            except ProviderError as exc:
                self.attempt_receipts.append(exc.receipt)
                last_error = exc
                # Provider pinning is deterministic: never fail over when explicitly requested.
                if required_provider or not exc.retryable:
                    raise
        assert last_error is not None
        raise last_error
