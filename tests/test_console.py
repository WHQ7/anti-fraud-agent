import unittest

from guard.agent import analyze
from guard.console import DEFAULT_POLICY, append_record, csv_export, filter_records, make_record, safe_log, stats, validate_policy


class ConsoleTests(unittest.TestCase):
    def record(self, text="请先支付入职保证金。", **kwargs):
        return make_record(analyze(text), "聊天消息", DEFAULT_POLICY, **kwargs)

    def test_policy_validation(self):
        for value in ({}, {**DEFAULT_POLICY, "high_priority": 1}, {**DEFAULT_POLICY, "shell": "x"}):
            with self.assertRaises(ValueError):
                validate_policy(value)

    def test_policy_changes_reminder_not_risk(self):
        report = analyze("请先缴纳入职保证金。")
        a = make_record(report, "邮件", DEFAULT_POLICY)
        b = make_record(report, "邮件", {**DEFAULT_POLICY, "high_priority": False})
        self.assertEqual(a["risk_level"], b["risk_level"])
        self.assertNotEqual(a["action"], b["action"])
        self.assertTrue(a["policy_snapshot"]["high_priority"])

    def test_conflict_cannot_disable_review(self):
        report = analyze("请先缴纳入职保证金。")
        report["needs_review"] = True
        record = make_record(report, "短信", {key: False for key in DEFAULT_POLICY})
        self.assertEqual(record["action"], "冲突复核")

    def test_bounded_records(self):
        record = self.record()
        records = []
        for _ in range(70):
            records = append_record(records, record)
        self.assertEqual(len(records), 50)

    def test_channel_and_status_filter(self):
        record = self.record()
        self.assertEqual(len(filter_records([record], channel="聊天消息", review="待复核")), 1)
        self.assertEqual(filter_records([record], channel="短信"), [])
        self.assertEqual(filter_records([record], keyword="notmatching"), [])

    def test_stats_are_based_on_records(self):
        self.assertEqual(stats([])["total"], 0)
        record = self.record()
        result = stats([record])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["high"], 1)
        self.assertEqual(result["agent"], 0)
        self.assertEqual(result["channels"]["聊天消息"], 1)

    def test_export_formula_injection(self):
        record = self.record(title="  =HYPERLINK(unsafe)")
        output = csv_export([record]).decode("utf-8-sig")
        self.assertIn("'  =HYPERLINK", output)

    def test_safe_log_has_no_message_or_credentials(self):
        record = self.record("我的私密原文代号ABC123，先缴纳保证金。")
        log = safe_log([record])
        self.assertNotIn("ABC123", log)
        self.assertNotIn("Authorization", log)
        self.assertIn("check_text_rules", log)

    def test_records_do_not_alias_reports(self):
        report = analyze("请先缴纳入职保证金。")
        record = make_record(report, "邮件", DEFAULT_POLICY)
        report["summary"] = "changed"
        self.assertNotEqual(record["report"]["summary"], "changed")

    def test_unknown_channel_rejected(self):
        with self.assertRaises(ValueError):
            make_record(analyze("需要补充背景。"), "任意脚本", DEFAULT_POLICY)


if __name__ == "__main__":
    unittest.main()
