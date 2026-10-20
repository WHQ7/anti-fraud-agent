import unittest
from unittest.mock import patch

import httpx

from guard.errors import AgentError
from guard.transport import API_ENDPOINT, DeepSeekTransport


class TransportTests(unittest.TestCase):
    def make_transport(self):
        return DeepSeekTransport("synthetic-test-key-not-real", "deepseek-flash")

    def test_missing_key(self):
        with self.assertRaises(AgentError):
            DeepSeekTransport("", "test").complete([])

    def test_fixed_endpoint_and_no_redirects(self):
        response = httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
        with patch("httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            self.make_transport().complete([])
            self.assertFalse(client.call_args.kwargs["follow_redirects"])
            self.assertEqual(client.return_value.__enter__.return_value.post.call_args.args[0], API_ENDPOINT)

    def test_http_failure_does_not_expose_server_body(self):
        response = httpx.Response(401, text="sensitive-server-body")
        with patch("httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            with self.assertRaises(AgentError) as caught:
                self.make_transport().complete([])
        self.assertNotIn("sensitive-server-body", str(caught.exception))

    def test_timeout(self):
        with patch("httpx.Client") as client:
            client.return_value.__enter__.return_value.post.side_effect = httpx.ReadTimeout("sensitive-request")
            with self.assertRaises(AgentError) as caught:
                self.make_transport().complete([])
        self.assertNotIn("sensitive-request", str(caught.exception))

    def test_budget(self):
        client = self.make_transport()
        client.request_count = 3
        with self.assertRaises(AgentError):
            client.complete([])

    def test_truncation_is_rejected(self):
        response = httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{"}}]})
        with patch("httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            with self.assertRaises(AgentError):
                self.make_transport().complete([])


if __name__ == "__main__":
    unittest.main()
