import copy
import json
import socket
import unittest
from unittest.mock import patch

from guard.agent import AnalysisSession, analyze, validate_input
from guard.errors import AgentError
from guard.knowledge import KnowledgeBase
from guard.privacy import redact
from guard.reports import report_text, validate_report
from guard.rules import check_text_rules
from guard.urls import extract_urls, inspect_url_features


def valid_json(text="请先缴纳入职保证金。", citations=None):
    return json.dumps({"risk_level": "高风险", "summary": "存在前置交费线索，需要独立核实。",
                       "evidence": [{"quote": text, "reason": "前置交费需要重点核实。"}],
                       "recommendations": ["通过独立可信渠道核实。"],
                       "uncertainties": ["尚未验证对方身份。"],
                       "citation_ids": citations if citations is not None else ["K02"]}, ensure_ascii=False)


class ScriptedTransport:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.request_count = 0
        self.token_usage = {"prompt_tokens": 1, "completion_tokens": 1}
        self.messages = []

    def complete(self, messages, tools=None):
        self.request_count += 1
        self.messages.append(copy.deepcopy(messages))
        response = next(self.replies)
        if isinstance(response, Exception):
            raise response
        return response


def tool_call(name="search_safety_knowledge", args=None, identifier="call_1"):
    return {"id": identifier, "type": "function", "function": {
        "name": name, "arguments": json.dumps(args if args is not None else {"query": "招聘 保证金"})}}


class InputAndPrivacyTests(unittest.TestCase):
    def test_empty_input(self):
        for value in ("", "  ", None, 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_input(value)

    def test_length_and_controls(self):
        for value in ("字" * 6001, "abc\x00"):
            with self.assertRaises(ValueError):
                validate_input(value)

    def test_redacts_contact_and_otp(self):
        text, count = redact("电话13800138000 邮箱student@example.com 验证码是123456")
        self.assertGreaterEqual(count, 3)
        for secret in ("13800138000", "student@example.com", "123456"):
            self.assertNotIn(secret, text)

    def test_redacts_keys(self):
        text, count = redact("apikey=demo_secret_value_123456 Bearer abcdefghijklmnop")
        self.assertGreaterEqual(count, 2)
        self.assertNotIn("demo_secret_value", text)
        self.assertNotIn("abcdefghijklmnop", text)

    def test_report_does_not_keep_raw_contact(self):
        report = analyze("客服让我把验证码123456发给他，电话13800138000。")
        exported = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("13800138000", exported)
        self.assertNotIn("123456", exported)

    def test_url_userinfo_and_query_are_redacted_without_losing_host(self):
        safe, count = redact("https://realuser:realpassword@notice.example/a?token=private-session")
        self.assertNotIn("realpassword", safe)
        self.assertNotIn("private-session", safe)
        self.assertEqual(inspect_url_features(safe)["urls"][0]["hostname"], "notice.example")
        self.assertGreaterEqual(count, 2)


class URLTests(unittest.TestCase):
    def test_userinfo(self):
        value = inspect_url_features("https://bank.example@evil.example/login")['urls'][0]
        self.assertEqual(value["hostname"], "evil.example")
        self.assertTrue(any("@" in item for item in value["features"]))
        self.assertFalse(value["visited"])

    def test_never_resolves_or_connects(self):
        with patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")), \
             patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
            for url in ("http://127.0.0.1:8080/admin", "http://169.254.169.254/latest/", "https://[::1]/"):
                result = inspect_url_features(url)
                self.assertFalse(result["network_access"])
                self.assertFalse(result["urls"][0]["visited"])

    def test_malformed_port_and_ipv6(self):
        for url in ("http://example.com:wrong/", "https://[invalid]/"):
            result = inspect_url_features(url)["urls"][0]
            self.assertTrue(any("无法可靠解析" in item for item in result["features"]))

    def test_supported_deobfuscation_and_punctuation(self):
        result = inspect_url_features("网址 hxxps://notice.example/x。")['urls'][0]
        self.assertEqual(result["hostname"], "notice.example")
        self.assertEqual(extract_urls("https://x.example/a。"), ["https://x.example/a"])

    def test_limit(self):
        self.assertEqual(len(extract_urls(" ".join(f"https://a{i}.example/" for i in range(20)))), 8)

    def test_https_is_not_a_safety_verdict(self):
        report = analyze("https://example.com")
        self.assertEqual(report["risk_level"], "信息不足")
        self.assertIn("未被访问", report["warnings"][0])


class RulesTests(unittest.TestCase):
    def test_no_exam_does_not_negate_later_fee(self):
        report = analyze("你已通过面试，无需笔试。请先缴纳299元入职保证金，10分钟内完成。")
        self.assertEqual(report["risk_level"], "高风险")

    def test_education_is_not_automatically_fraud(self):
        report = analyze("反诈提醒：不要把验证码告诉陌生人，切勿向安全账户转账。")
        self.assertEqual(report["risk_level"], "暂未发现明显风险")

    def test_education_prefix_does_not_hide_direct_request(self):
        report = analyze("反诈提醒：请把验证码告诉客服，再转账到安全账户。")
        self.assertEqual(report["risk_level"], "高风险")

    def test_normal_interview(self):
        report = analyze("邀请你周三下午参加开发实习面试。面试不收取费用，不需要提供验证码。")
        self.assertEqual(report["risk_level"], "暂未发现明显风险")

    def test_mixed_warning_does_not_hide_request(self):
        self.assertEqual(analyze("请把验证码告诉客服。不要向陌生人转账。")['risk_level'], "高风险")

    def test_evidence_offsets(self):
        text = "请先支付入职保证金，然后马上转账。"
        for item in check_text_rules(text)["findings"]:
            self.assertEqual(text[item["start"]:item["end"]], item["quote"])


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()

    def test_job_retrieval(self):
        self.assertEqual(self.kb.search("招聘 入职 培训费 保证金")[0]["id"], "K02")

    def test_no_match(self):
        self.assertEqual(self.kb.search("qwertyasdfghzzzzz"), [])

    def test_refund_retrieval(self):
        self.assertEqual(self.kb.search("退款 追款 手续费 赔付")[0]["id"], "K03")

    def test_sources_are_curated(self):
        for doc in self.kb.documents:
            self.assertTrue(doc["source_url"].startswith("https://"))
            self.assertIn("reviewed_at", doc)
            self.assertIn("source_scope", doc)


class ValidationTests(unittest.TestCase):
    def test_valid_report(self):
        report = validate_report(valid_json(), "请先缴纳入职保证金。", {"K02"})
        self.assertEqual(report["evidence"][0]["start"], 0)

    def test_fabricated_evidence(self):
        with self.assertRaises(ValueError):
            validate_report(valid_json("不存在的原文"), "正常消息", {"K02"})

    def test_unretrieved_citation(self):
        with self.assertRaises(ValueError):
            validate_report(valid_json(citations=["K99"]), "请先缴纳入职保证金。", {"K02"})

    def test_probability_and_wrong_keys(self):
        original = json.loads(valid_json())
        for modification in ({"summary": "诈骗概率99%，所以是诈骗。"}, {"extra": "unknown"}, {"risk_level": "绝对安全"}):
            data = {**original, **modification}
            with self.assertRaises(ValueError):
                validate_report(json.dumps(data), "请先缴纳入职保证金。", {"K02"})

    def test_percentage_in_original_quote_is_not_invented_probability(self):
        text = "承诺收益100%，请先缴纳保证金。"
        report = validate_report(valid_json(text), text, {"K02"})
        self.assertEqual(report["evidence"][0]["quote"], text)


class AgentTests(unittest.TestCase):
    text = "请先缴纳入职保证金。"

    def test_consent_before_any_call(self):
        fake = ScriptedTransport([])
        with self.assertRaises(ValueError):
            analyze(self.text, mode="agent", transport=fake)
        self.assertEqual(fake.request_count, 0)

    def test_real_tool_loop_with_mock_model(self):
        fake = ScriptedTransport([
            {"tool_calls": [tool_call()]}, {"content": "准备完成"}, {"content": valid_json()}])
        result = analyze(self.text, mode="agent", transport=fake, consent=True)
        self.assertEqual(result["mode"], "agent")
        self.assertEqual(result["model_tool_calls"], 1)
        self.assertEqual(fake.request_count, 3)
        self.assertTrue(any(event["actor"] == "agent" and event["tool"] == "search_safety_knowledge" for event in result["trace"]))
        self.assertTrue(any(item["role"] == "tool" for item in fake.messages[-1]))

    def test_no_tool_call_is_not_faked(self):
        fake = ScriptedTransport([{"content": "无需工具"}, {"content": valid_json()}])
        result = analyze(self.text, mode="agent", transport=fake, consent=True)
        self.assertEqual(result["model_tool_calls"], 0)
        self.assertFalse(any(event["actor"] == "agent" for event in result["trace"]))

    def test_network_failure_has_explicit_fallback(self):
        fake = ScriptedTransport([AgentError("timeout", "模型请求超时")])
        result = analyze(self.text, mode="agent", transport=fake, consent=True)
        self.assertEqual(result["mode"], "fallback")
        self.assertIn("不是 AI 结论", result["warnings"][0])

    def test_invalid_model_report_falls_back(self):
        fake = ScriptedTransport([{"content": "done"}, {"content": valid_json("伪造的证据")}])
        result = analyze(self.text, mode="agent", transport=fake, consent=True)
        self.assertEqual(result["mode"], "fallback")

    def test_tool_limit(self):
        fake = ScriptedTransport([{"tool_calls": [tool_call(identifier=f"c{i}") for i in range(7)]}])
        result = analyze(self.text, mode="agent", transport=fake, consent=True)
        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result["model_tool_calls"], 0)

    def test_unknown_tool_cannot_read_or_execute(self):
        fake = ScriptedTransport([
            {"tool_calls": [tool_call("read_environment", {"name": "apikey"})]},
            {"content": "done"}, {"content": valid_json()}])
        report = analyze(self.text, mode="agent", transport=fake, consent=True)
        self.assertTrue(any(event["status"] == "rejected" for event in report["trace"]))
        self.assertEqual(report["mode"], "agent")

    def test_invalid_tool_arguments(self):
        session = AnalysisSession(self.text, KnowledgeBase(), None)
        for name, args in (("inspect_url_features", {"url": "http://127.0.0.1"}),
                           ("search_safety_knowledge", {"query": "字" * 241}),
                           ("search_safety_knowledge", {"query": ["x"]}), ("exec", {})):
            with self.assertRaises(ValueError):
                session.tool(name, args)

    def test_duplicate_call_ids_rejected(self):
        fake = ScriptedTransport([{"tool_calls": [tool_call(), tool_call()]}])
        self.assertEqual(analyze(self.text, mode="agent", transport=fake, consent=True)["mode"], "fallback")

    def test_safe_text_is_all_that_reaches_model(self):
        text = "apikey=not_a_real_secret_123456 电话13800138000 请先缴纳入职保证金。"
        fake = ScriptedTransport([AgentError("test", "模拟停止")])
        analyze(text, mode="agent", transport=fake, consent=True)
        payload = json.dumps(fake.messages)
        self.assertNotIn("not_a_real_secret_123456", payload)
        self.assertNotIn("13800138000", payload)

    def test_export_is_plain_text(self):
        report = analyze(self.text)
        output = report_text(report)
        self.assertIn("未调用 AI", output)
        self.assertIn("原文依据", output)
        self.assertIn("https://consumer.ftc.gov/", output)

    def test_conflict_requires_visible_review_flag(self):
        payload = json.loads(valid_json())
        payload["risk_level"] = "暂未发现明显风险"
        fake = ScriptedTransport([{"content": "done"}, {"content": json.dumps(payload)}])
        report = analyze(self.text, mode="agent", transport=fake, consent=True)
        self.assertTrue(report["needs_review"])


if __name__ == "__main__":
    unittest.main()
