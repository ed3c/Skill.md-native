from __future__ import annotations

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .providers import ProviderError, ProviderRouter


class InferenceGateway:
    """Small OpenAI-compatible broker for sandboxed Agent traffic.

    The gateway owns provider credentials outside the Skill workspace. A caller
    supplies only model/messages and optional routing metadata; raw upstream
    credentials are never returned to the caller.
    """

    def __init__(self, router: ProviderRouter) -> None:
        self.router = router

    def chat_completions(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any], dict[str, str]]:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            return 400, {"error": {"message": "messages must be a non-empty list"}}, {}

        provider = payload.pop("skill_native_provider", None)
        max_tokens = payload.get("max_tokens")
        temperature = payload.get("temperature", 0.0)
        started = time.time()
        try:
            result = self.router.complete(
                messages,
                required_provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except ProviderError as exc:
            code = 429 if exc.receipt.error == "http_429" else 502
            return (
                code,
                {
                    "error": {
                        "message": str(exc),
                        "type": "skill_native_upstream_error",
                        "provider": exc.receipt.provider,
                    },
                    "skill_native_receipt": exc.receipt.model_dump(mode="json"),
                },
                {"x-skill-native-provider": exc.receipt.provider},
            )

        created = int(started)
        body = {
            "id": f"chatcmpl-skill-native-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": created,
            "model": result.receipt.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": result.receipt.input_tokens,
                "completion_tokens": result.receipt.output_tokens,
                "total_tokens": result.receipt.input_tokens + result.receipt.output_tokens,
            },
            "skill_native_receipt": result.receipt.model_dump(mode="json"),
        }
        return 200, body, {"x-skill-native-provider": result.receipt.provider}


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


def serve(router: ProviderRouter, host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(InferenceGateway(router)))
    try:
        server.serve_forever()
    finally:
        server.server_close()
