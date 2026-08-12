from __future__ import annotations

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .policy import ProviderPolicy, ReceiptLedger
from .providers import ProviderError, ProviderRouter


class InferenceGateway:
    """OpenAI-compatible broker for sandboxed Agent traffic."""

    def __init__(
        self,
        router: ProviderRouter,
        *,
        policy: ProviderPolicy | None = None,
        ledger: ReceiptLedger | None = None,
    ) -> None:
        self.router = router
        self.policy = policy or ProviderPolicy()
        self.ledger = ledger

    def _eligible_router(self) -> ProviderRouter:
        providers = self.policy.filter(self.router.providers)
        if not providers:
            raise RuntimeError("provider policy leaves no eligible inference provider")
        clients = {
            name: adapter.client
            for name, adapter in self.router.adapters.items()
            if name in {p.name for p in providers}
        }
        return ProviderRouter(providers, clients=clients)

    def _persist_new_receipts(
        self,
        router: ProviderRouter,
        start_index: int,
        *,
        run_id: str | None,
    ) -> None:
        if self.ledger is None:
            return
        for receipt in router.attempt_receipts[start_index:]:
            self.ledger.append(receipt, run_id=run_id)

    def chat_completions(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any], dict[str, str]]:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            return 400, {"error": {"message": "messages must be a non-empty list"}}, {}

        if self.ledger is not None:
            try:
                self.ledger.assert_budget(self.policy)
            except RuntimeError as exc:
                return 429, {"error": {"message": str(exc), "type": "skill_native_budget_exhausted"}}, {}

        provider = payload.get("skill_native_provider")
        run_id = payload.get("skill_native_run_id")
        if run_id is not None and not isinstance(run_id, str):
            return 400, {"error": {"message": "skill_native_run_id must be a string"}}, {}
        max_tokens = payload.get("max_tokens")
        temperature = payload.get("temperature", 0.0)
        started = time.time()
        try:
            active_router = self._eligible_router()
        except RuntimeError as exc:
            return 503, {"error": {"message": str(exc), "type": "skill_native_policy_error"}}, {}

        receipt_start = len(active_router.attempt_receipts)
        try:
            result = active_router.complete(
                messages,
                required_provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except ProviderError as exc:
            self._persist_new_receipts(active_router, receipt_start, run_id=run_id)
            code = 429 if exc.receipt.error == "http_429" else 502
            receipt = exc.receipt.model_copy(update={"run_id": run_id})
            return (
                code,
                {
                    "error": {
                        "message": str(exc),
                        "type": "skill_native_upstream_error",
                        "provider": receipt.provider,
                    },
                    "skill_native_receipt": receipt.model_dump(mode="json"),
                },
                {"x-skill-native-provider": receipt.provider},
            )
        except RuntimeError as exc:
            self._persist_new_receipts(active_router, receipt_start, run_id=run_id)
            return 503, {"error": {"message": str(exc), "type": "skill_native_policy_error"}}, {}

        self._persist_new_receipts(active_router, receipt_start, run_id=run_id)
        receipt = result.receipt.model_copy(update={"run_id": run_id})
        created = int(started)
        body = {
            "id": f"chatcmpl-skill-native-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": created,
            "model": receipt.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": receipt.input_tokens,
                "completion_tokens": receipt.output_tokens,
                "total_tokens": receipt.input_tokens + receipt.output_tokens,
            },
            "skill_native_receipt": receipt.model_dump(mode="json"),
        }
        return 200, body, {"x-skill-native-provider": receipt.provider}


def make_handler(gateway: InferenceGateway):
    class Handler(BaseHTTPRequestHandler):
        server_version = "skill-native-gateway/0.1"

        def do_GET(self):
            if self.path == "/healthz":
                self._json(200, {"status": "ok"})
                return
            self._json(404, {"error": {"message": "not found"}})

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self._json(404, {"error": {"message": "not found"}})
                return
            try:
                length = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._json(400, {"error": {"message": "invalid JSON"}})
                return
            status, body, headers = gateway.chat_completions(payload)
            self._json(status, body, headers)

        def log_message(self, format, *args):
            return

        def _json(self, status: int, body: dict[str, Any], headers: dict[str, str] | None = None):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(
    router: ProviderRouter,
    host: str = "127.0.0.1",
    port: int = 8787,
    *,
    policy: ProviderPolicy | None = None,
    ledger: ReceiptLedger | None = None,
) -> None:
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(InferenceGateway(router, policy=policy, ledger=ledger)),
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
