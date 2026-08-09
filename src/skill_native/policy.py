from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterable

from .models import InferenceReceipt
from .providers import ProviderConfig


@dataclass(frozen=True)
class ProviderPolicy:
    local_only: bool = False
    max_daily_requests: int | None = None
    max_daily_tokens: int | None = None
    max_daily_cost_usd: float | None = None

    def filter(self, providers: Iterable[ProviderConfig]) -> list[ProviderConfig]:
        result = list(providers)
        if self.local_only:
            result = [p for p in result if p.quota_class == "local"]
        return result


class ReceiptLedger:
    """Append-only JSONL inference ledger with local budget accounting."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append(self, receipt: InferenceReceipt, *, run_id: str | None = None) -> None:
        record = receipt.model_dump(mode="json")
        if run_id is not None:
            record["run_id"] = run_id
        record["recorded_at"] = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")

    def read(self, *, run_id: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        records: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if run_id is None or record.get("run_id") == run_id:
                    records.append(record)
        return records

    def today_usage(self) -> dict[str, float | int]:
        today = datetime.now(timezone.utc).date().isoformat()
        records = [r for r in self.read() if str(r.get("recorded_at", "")).startswith(today)]
        return {
            "requests": len(records),
            "tokens": sum(int(r.get("input_tokens", 0)) + int(r.get("output_tokens", 0)) for r in records),
            "cost_usd": sum(float(r.get("price_usd", 0.0)) for r in records),
        }

    def assert_budget(self, policy: ProviderPolicy) -> None:
        usage = self.today_usage()
        if policy.max_daily_requests is not None and usage["requests"] >= policy.max_daily_requests:
            raise RuntimeError("daily inference request budget exhausted")
        if policy.max_daily_tokens is not None and usage["tokens"] >= policy.max_daily_tokens:
            raise RuntimeError("daily inference token budget exhausted")
        if policy.max_daily_cost_usd is not None and usage["cost_usd"] >= policy.max_daily_cost_usd:
            raise RuntimeError("daily inference cost budget exhausted")
