import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


class UITests(unittest.TestCase):
    def app(self, detection=True):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        if detection:
            app.switch_page("app_pages/detection.py").run()
        else:
            app.switch_page("app_pages/overview.py").run()
        return app

    def test_initial_screen(self):
        app = self.app(detection=False)
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["mode"], "本地检查")
        self.assertIsNone(app.session_state["result"])
        self.assertEqual(len(app.metric), 6)
        self.assertTrue(all(metric.value == "0" for metric in app.metric))

    def test_empty_message(self):
        app = self.app()
        app.button(key="analyze").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertIsNone(app.session_state["result"])

    def test_default_screen_restores_original_console_structure(self):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        self.assertEqual(app.title[0].value, "安全总览")
        self.assertTrue(app.button(key="go-detect"))
        self.assertTrue(app.get_by_key("panel-high"))
        self.assertTrue(app.get_by_key("panel-channels"))
        self.assertTrue(app.get_by_key("panel-recent"))
        self.assertEqual(len(app.get("html")), 0)
        self.assertEqual(len(app.get("imgs")), 0)
        self.assertEqual(len(app.metric), 6)
        self.assertFalse(app.exception)

    def test_workbench_primary_action_opens_detection(self):
        app = self.app(detection=False)
        app.button(key="go-detect").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "智能检测")
        self.assertTrue(app.text_area(key="message"))

    def test_agent_preview_is_visible_and_record_options_are_optional(self):
        app = self.app()
        app.get_by_key("mode").set_value("DeepSeek Agent").run()
        preview = next(element for element in app.expander if element.label == "检查脱敏后的分析内容")
        self.assertTrue(preview.proto.expanded)
        self.assertFalse(app.checkbox(key="consent").value)
        self.assertTrue(app.get_by_key("recording").value)

    def test_sample_and_local_report(self):
        app = self.app()
        app.selectbox(key="example_choice").select("虚假招聘收费").run()
        app.button(key="analyze").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["result"]["risk_level"], "高风险")
        self.assertEqual(app.session_state["result"]["request_count"], 0)
        self.assertEqual(len(app.get("download_button")), 2)

    def test_clear(self):
        app = self.app()
        app.selectbox(key="example_choice").select("正常面试安排").run()
        app.button(key="analyze").click().run()
        app.button(key="clear").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["message"], "")
        self.assertIsNone(app.session_state["result"])

    def test_agent_requires_consent(self):
        app = self.app()
        app.get_by_key("mode").set_value("DeepSeek Agent").run()
        app.selectbox(key="example_choice").select("虚假招聘收费").run()
        with patch("guard.transport.DeepSeekTransport.complete", side_effect=AssertionError("no API permitted")):
            app.button(key="analyze").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertIsNone(app.session_state["result"])

    def test_editing_revokes_consent(self):
        app = self.app()
        app.get_by_key("mode").set_value("DeepSeek Agent").run()
        app.checkbox(key="consent").check().run()
        app.text_area(key="message").set_value("请先缴纳入职保证金。").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state["consent"])

    def test_knowledge_and_about(self):
        app = self.app()
        app.switch_page("app_pages/knowledge.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("link_button")), 6)
        app.switch_page("app_pages/runtime.py").run()
        self.assertFalse(app.exception)

    def test_input_change_marks_report_stale(self):
        app = self.app()
        app.selectbox(key="example_choice").select("虚假招聘收费").run()
        app.button(key="analyze").click().run()
        app.text_area(key="message").set_value("修改后的消息，请核实。").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("输入已修改" in warning.value for warning in app.warning))

    def test_input_survives_viewing_sources(self):
        app = self.app()
        app.text_area(key="message").set_value("我的面试安排，周三下午参加。").run()
        app.switch_page("app_pages/knowledge.py").run()
        app.switch_page("app_pages/detection.py").run()
        self.assertEqual(app.text_area(key="message").value, "我的面试安排，周三下午参加。")
        self.assertFalse(app.exception)

    def test_every_console_page(self):
        app = self.app(detection=False)
        for name in ("overview", "detection", "records", "policy", "runtime", "statistics", "logs", "knowledge"):
            with self.subTest(page=name):
                app.switch_page(f"app_pages/{name}.py").run()
                self.assertFalse(app.exception)

    def test_demo_is_explicit_and_separate(self):
        app = self.app(detection=False)
        with patch("guard.transport.DeepSeekTransport.complete", side_effect=AssertionError("No demo API")):
            app.button(key="load-demo").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["data_scope"], "演示样例")
        self.assertEqual(len(app.session_state["demo_records"]), 7)
        self.assertEqual(len(app.session_state["records"]), 0)
        self.assertTrue(all(item["demo"] and item["mode"] == "local" for item in app.session_state["demo_records"]))
        self.assertFalse(any("当前为虚构演示数据" in warning.value for warning in app.warning))
        self.assertTrue(any("演示数据" in element.value for element in app.markdown))

    def test_detection_registers_and_policy_applies(self):
        app = self.app()
        app.selectbox(key="example_choice").select("虚假招聘收费").run()
        app.button(key="analyze").click().run()
        self.assertEqual(len(app.session_state["records"]), 1)
        self.assertEqual(app.session_state["records"][0]["action"], "优先核实")
        app.switch_page("app_pages/policy.py").run()
        app.checkbox(key="policy-high").uncheck()
        app.button(key="save-policy").click().run()
        self.assertFalse(app.session_state["policy"]["high_priority"])
        app.switch_page("app_pages/detection.py").run()
        app.button(key="analyze").click().run()
        self.assertEqual(len(app.session_state["records"]), 2)
        self.assertEqual(app.session_state["records"][-1]["action"], "留意来源")
        self.assertEqual(app.session_state["records"][0]["action"], "优先核实")
        app.switch_page("app_pages/records.py").run()
        self.assertFalse(app.exception)

    def test_recording_can_be_disabled(self):
        app = self.app()
        app.selectbox(key="example_choice").select("虚假招聘收费").run()
        app.get_by_key("recording").set_value(False).run()
        app.button(key="analyze").click().run()
        self.assertFalse(app.exception)
        self.assertIsNotNone(app.session_state["result"])
        self.assertEqual(app.session_state["records"], [])

    def test_manual_review_updates_overview(self):
        app = self.app()
        app.selectbox(key="example_choice").select("虚假招聘收费").run()
        app.button(key="analyze").click().run()
        record_id = app.session_state["records"][0]["id"]
        app.switch_page("app_pages/records.py").run()
        app.selectbox(key=f"review-{record_id}").select("已核实")
        app.button(key="save-review").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["records"][0]["review_state"], "已核实")
        app.switch_page("app_pages/overview.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[-1].value, "0")

    def test_record_deletion_requires_confirmation(self):
        app = self.app()
        app.selectbox(key="example_choice").select("虚假招聘收费").run()
        app.button(key="analyze").click().run()
        app.switch_page("app_pages/records.py").run()
        self.assertTrue(app.button(key="clear-records").disabled)
        app.checkbox(key="confirm-clear-records").check().run()
        app.button(key="clear-records").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["records"], [])


if __name__ == "__main__":
    unittest.main()
