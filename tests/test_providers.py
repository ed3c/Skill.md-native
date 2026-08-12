import os
import unittest

import httpx

from skill_native.providers import ProviderConfig, ProviderError, ProviderKind, ProviderRouter


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


class ProviderRouterTests(unittest.TestCase):
    def test_success_records_usage_and_rate_limit_headers(self):
        def handler(request):
            self.assertEqual(request.url.path, "/openai/v1/chat/completions")
            return httpx.Response(
                200,
                headers={"x-ratelimit-remaining-requests": "29"},
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 3},
                },
            )

        config = ProviderConfig(
            name="groq-free",
            kind=ProviderKind.GROQ,
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-20b",
            quota_class="free",
        )
        router = ProviderRouter([config], clients={"groq-free": client_for(handler)})
        result = router.complete([{"role": "user", "content": "ping"}])
        self.assertEqual(result.text, "ok")
        self.assertEqual(result.receipt.input_tokens, 12)
        self.assertEqual(result.receipt.output_tokens, 3)
        self.assertEqual(result.receipt.rate_limit_headers["x-ratelimit-remaining-requests"], "29")
        self.assertEqual(len(router.attempt_receipts), 1)

    def test_retryable_429_falls_back_when_provider_is_not_pinned(self):
        local = ProviderConfig(
            name="local",
            kind=ProviderKind.LOCAL,
            base_url="http://local.test/v1",
            model="local-model",
            quota_class="local",
        )
        free = ProviderConfig(
            name="free",
            kind=ProviderKind.GROQ,
            base_url="https://free.test/v1",
            model="free-model",
            quota_class="free",
        )

        def local_handler(request):
            return httpx.Response(429, headers={"retry-after": "10"}, json={"error": {"message": "busy"}})

        def free_handler(request):
            return httpx.Response(200, json={"choices": [{"message": {"content": "fallback"}}], "usage": {}})

        router = ProviderRouter(
            [free, local],
            clients={"local": client_for(local_handler), "free": client_for(free_handler)},
        )
        result = router.complete([{"role": "user", "content": "ping"}])
        self.assertEqual(result.text, "fallback")
        self.assertEqual([r.error for r in router.attempt_receipts], ["http_429", None])

    def test_provider_pinning_does_not_fail_over(self):
        pinned = ProviderConfig(
            name="pinned",
            kind=ProviderKind.GROQ,
            base_url="https://pinned.test/v1",
            model="model",
            quota_class="free",
        )
        backup = ProviderConfig(
            name="backup",
            kind=ProviderKind.LOCAL,
            base_url="http://backup.test/v1",
            model="model",
            quota_class="local",
        )
        router = ProviderRouter(
            [pinned, backup],
            clients={
                "pinned": client_for(lambda request: httpx.Response(429, json={})),
                "backup": client_for(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "wrong"}}]})),
            },
        )
        with self.assertRaises(ProviderError):
            router.complete([{"role": "user", "content": "ping"}], required_provider="pinned")
        self.assertEqual(len(router.attempt_receipts), 1)

    def test_missing_operator_credential_fails_without_network_call(self):
        config = ProviderConfig(
            name="gemini-free",
            kind=ProviderKind.GEMINI,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model="gemini-test",
            quota_class="free",
            api_key_env="SKILL_NATIVE_TEST_MISSING_KEY",
        )
        os.environ.pop("SKILL_NATIVE_TEST_MISSING_KEY", None)
        router = ProviderRouter([config])
        with self.assertRaises(ProviderError) as ctx:
            router.complete([{"role": "user", "content": "ping"}], required_provider="gemini-free")
        self.assertEqual(ctx.exception.receipt.error, "credential_missing")


if __name__ == "__main__":
    unittest.main()
