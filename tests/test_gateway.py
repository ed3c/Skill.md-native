import unittest

import httpx

from skill_native.gateway import InferenceGateway
from skill_native.providers import ProviderConfig, ProviderKind, ProviderRouter


class GatewayTests(unittest.TestCase):
    def test_chat_completions_returns_openai_shape_and_receipt(self):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello"}}],
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

    def test_invalid_messages_returns_400(self):
        gateway = InferenceGateway(ProviderRouter([]))
        status, body, _ = gateway.chat_completions({"messages": []})
        self.assertEqual(status, 400)
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()
