import tempfile
import unittest
from pathlib import Path

import httpx

from skill_native.gateway import InferenceGateway
from skill_native.policy import ProviderPolicy, ReceiptLedger
from skill_native.providers import ProviderConfig, ProviderKind, ProviderRouter


class GatewayTests(unittest.TestCase):
    def make_local(self, text="hello"):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": text}}],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                },
            )

        config = ProviderConfig(
            name="local",
            kind=ProviderKind.LOCAL,
            base_url="http://local.test/v1",
            model="local-model",
            quota_class="local",
        )
        client = httpx.Client(transport=httpx.MockTransport(handler))
        return config, client

    def test_chat_completions_returns_openai_shape_and_receipt(self):
        config, client = self.make_local()
        gateway = InferenceGateway(ProviderRouter([config], clients={"local": client}))
        status, body, headers = gateway.chat_completions(
            {"model": "ignored-by-router", "messages": [{"role": "user", "content": "hi"}]}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["object"], "chat.completion")
        self.assertEqual(body["choices"][0]["message"]["content"], "hello")
        self.assertEqual(body["usage"]["total_tokens"], 6)
        self.assertEqual(body["skill_native_receipt"]["provider"], "local")
        self.assertEqual(headers["x-skill-native-provider"], "local")

    def test_local_only_filters_external_provider_and_persists_receipt(self):
        config, client = self.make_local()
        external = ProviderConfig(
            name="external",
            kind=ProviderKind.GROQ,
            base_url="https://external.invalid/openai/v1",
            model="external-model",
            quota_class="free",
            api_key_env="MISSING_TEST_KEY",
        )
        with tempfile.TemporaryDirectory() as td:
            ledger = ReceiptLedger(Path(td) / "receipts.jsonl")
            gateway = InferenceGateway(
                ProviderRouter([external, config], clients={"local": client}),
                policy=ProviderPolicy(local_only=True),
                ledger=ledger,
            )
            status, body, _ = gateway.chat_completions(
                {"messages": [{"role": "user", "content": "hi"}]}
            )
            self.assertEqual(status, 200)
            self.assertEqual(body["skill_native_receipt"]["provider"], "local")
            records = ledger.read()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["provider"], "local")

    def test_budget_exhaustion_stops_before_upstream(self):
        calls = {"count": 0}

        def handler(request):
            calls["count"] += 1
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        config = ProviderConfig(
            name="local",
            kind=ProviderKind.LOCAL,
            base_url="http://local.test/v1",
            model="local-model",
            quota_class="local",
        )
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with tempfile.TemporaryDirectory() as td:
            ledger = ReceiptLedger(Path(td) / "receipts.jsonl")
            gateway = InferenceGateway(
                ProviderRouter([config], clients={"local": client}),
                policy=ProviderPolicy(max_daily_requests=0),
                ledger=ledger,
            )
            status, body, _ = gateway.chat_completions(
                {"messages": [{"role": "user", "content": "hi"}]}
            )
            self.assertEqual(status, 429)
            self.assertEqual(body["error"]["type"], "skill_native_budget_exhausted")
            self.assertEqual(calls["count"], 0)

    def test_invalid_messages_returns_400(self):
        gateway = InferenceGateway(ProviderRouter([]))
        status, body, _ = gateway.chat_completions({"messages": []})
        self.assertEqual(status, 400)
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()
