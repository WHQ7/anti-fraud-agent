"""Explicit opt-in live test. Sends only one built-in fictional sample."""

import argparse
import json
from pathlib import Path

from guard.agent import analyze
from guard.config import get_api_key, get_model
from guard.transport import DeepSeekTransport


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="仅发送虚构招聘样例；最多3次付费模型请求。")
    parser.add_argument("--confirm-api-cost", action="store_true", help="确认外部模型调用和额度消耗")
    args = parser.parse_args()
    if not args.confirm_api_cost:
        parser.error("请阅读脚本说明，并显式传入 --confirm-api-cost 才能执行。")
    if not get_api_key():
        raise SystemExit("未读取到 apikey。")
    sample = json.loads((Path(__file__).parent / "data" / "examples.json").read_text(encoding="utf-8"))[0]
    report = analyze(sample["text"], mode="agent", consent=True,
                     transport=DeepSeekTransport(get_api_key(), get_model()))
    # Do not print credentials, HTTP headers, original input or raw model payloads.
    print(json.dumps({key: report[key] for key in (
        "mode", "risk_level", "request_count", "model_tool_calls", "citation_ids", "token_usage")}, ensure_ascii=False))
    print(json.dumps({"events": [{"tool": item["tool"], "status": item["status"]} for item in report["trace"]]}, ensure_ascii=False))
    if report["mode"] == "fallback":
        print(report["warnings"][0])
    raise SystemExit(0 if report["mode"] == "agent" else 1)
