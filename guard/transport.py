"""The only network boundary. Fixed official HTTPS host, no redirects/retries."""

import time

from guard.errors import AgentError

API_ENDPOINT = "https://api.deepseek.com/chat/completions"


class DeepSeekTransport:
    def __init__(self, api_key: str, model: str, deadline_seconds: float = 90):
        self._api_key = api_key
        self.model = model
        self.deadline_seconds = deadline_seconds
        self.started_at = None
        self.request_count = 0
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        import httpx

        if not self._api_key:
            raise AgentError("missing_key", "未读取到 apikey，请设置环境变量或重启应用。")
        if self.started_at is None:
            self.started_at = time.monotonic()
        remaining = self.deadline_seconds - (time.monotonic() - self.started_at)
        if self.request_count >= 3 or remaining < 1:
            raise AgentError("budget", "已达到请求次数或总等待时间上限，停止调用。")
        self.request_count += 1
        payload = {
            "model": self.model, "messages": messages,
            "stream": False, "max_tokens": 2300,
            "thinking": {"type": "disabled"},
        }
        if tools:
            payload.update(tools=tools, tool_choice="auto")
        else:
            payload["response_format"] = {"type": "json_object"}
        try:
            # Never take the endpoint from user content or model tool arguments.
            with httpx.Client(timeout=httpx.Timeout(min(remaining, 40), connect=8),
                              follow_redirects=False) as client:
                response = client.post(API_ENDPOINT, json=payload,
                                       headers={"Authorization": f"Bearer {self._api_key}"})
            if response.status_code != 200:
                messages_by_status = {
                    401: "DeepSeek 认证失败，请检查 apikey。",
                    402: "DeepSeek 账户额度不足。",
                    429: "DeepSeek 请求受限，请稍后手动重试。",
                }
                raise AgentError("http_error", messages_by_status.get(response.status_code,
                                 f"DeepSeek 返回 HTTP {response.status_code}，未自动重试。"))
            body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") in {"length", "content_filter"}:
                raise AgentError("incomplete", "模型输出被截断或过滤，不能作为完整分析报告。")
            message = choice["message"]
            if not isinstance(message, dict):
                raise ValueError("invalid message")
            usage = body.get("usage", {})
            for field in self.token_usage:
                value = usage.get(field, 0)
                if isinstance(value, int) and value >= 0:
                    self.token_usage[field] += value
            return message
        except AgentError:
            raise
        except httpx.TimeoutException:
            raise AgentError("timeout", "模型请求超时，未自动重试；保留本地检查结果。") from None
        except httpx.HTTPError:
            raise AgentError("network", "无法连接 DeepSeek，请检查网络或代理；未自动重试。") from None
        except (ValueError, TypeError, KeyError, IndexError):
            raise AgentError("response", "模型接口响应格式异常，未采纳该响应。") from None
