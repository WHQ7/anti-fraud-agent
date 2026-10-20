import json
from pathlib import Path

import pandas as pd
import streamlit as st

from guard.agent import analyze
from guard.console import CHANNELS, DEFAULT_POLICY, append_record, make_record, stats
from guard.knowledge import KnowledgeBase
from guard.reports import DISCLAIMER, LEVELS, report_text

ROOT = Path(__file__).resolve().parents[1]
UI_BUILD = "console-20261020-refined-label"
RISK_COLORS = ["red", "orange", "green", "gray"]


def init_state():
    defaults = {
        "message": "", "result": None, "result_fingerprint": "", "consent": False,
        "records": [], "demo_records": [], "policy": DEFAULT_POLICY.copy(),
        "policy_version": 1, "policy_updated": "尚未修改", "data_scope": "当前会话",
        "recording": True, "mode": "本地检查",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


@st.cache_data(ttl=3600, max_entries=1)
def load_examples():
    return json.loads((ROOT / "data" / "examples.json").read_text(encoding="utf-8"))


@st.cache_resource(ttl=3600, max_entries=1)
def load_knowledge():
    return KnowledgeBase()


def current_records():
    return st.session_state["demo_records"] if st.session_state["data_scope"] == "演示样例" else st.session_state["records"]


def generate_demo():
    # Explicit user action. No API, no fabricated AI activity or network events.
    if not st.session_state["demo_records"]:
        channels = ["聊天消息", "短信", "聊天消息", "邮件", "短信", "网址", "其他"]
        st.session_state["demo_records"] = [
            make_record(analyze(item["text"], knowledge=load_knowledge()), channel,
                        st.session_state["policy"], demo=True, title=item["title"])
            for item, channel in zip(load_examples(), channels)
        ]
    st.session_state["data_scope"] = "演示样例"


def register_report(report, channel):
    if not st.session_state["recording"]:
        return
    record = make_record(report, channel, st.session_state["policy"])
    st.session_state["records"] = append_record(st.session_state["records"], record)


def scope_notice():
    if st.session_state["data_scope"] == "演示样例":
        st.badge("演示数据", color="gray", icon=":material/science:")


def page_heading(title, subtitle, icon):
    st.title(title, icon=icon)
    st.caption(subtitle)
    scope_notice()


def kpis(records):
    values = stats(records)
    cards = [("total", "检测信息", values["total"]), ("high", "高风险线索", values["high"]),
             ("medium", "中风险线索", values["medium"]), ("insufficient", "信息不足", values["insufficient"]),
             ("no-signal", "暂未发现明显风险", values["no_signal"]), ("pending", "待人工复核", values["pending"])]
    # Restore the original six-card console row. Native columns stack on mobile.
    for column, (name, label, value) in zip(st.columns(6, gap="small"), cards):
        with column.container(key=f"kpi-{name}"):
            st.metric(label, value, border=True, height="stretch")


def records_table(records, *, key, limit=50):
    rows = [{"检测时间": item["time"], "来源渠道": item["channel"], "内容摘要": item["title"],
             "风险提示": [item["risk_level"]], "分析方式": "AI 失败 / 本地结果" if item["mode"] == "fallback" else ("DeepSeek Agent" if item["mode"] == "agent" else "本地规则"),
             "核实建议": item["action"], "人工状态": [item["review_state"]]}
            for item in records[:limit]]
    columns = ["检测时间", "来源渠道", "内容摘要", "风险提示", "分析方式", "核实建议", "人工状态"]
    st.dataframe(pd.DataFrame(rows, columns=columns), hide_index=True,
                 column_config={
                     "风险提示": st.column_config.MultiselectColumn(options=list(LEVELS), color=RISK_COLORS),
                     "人工状态": st.column_config.MultiselectColumn(options=["待复核", "已核实", "误报标记"], color=["orange", "green", "violet"]),
                     "内容摘要": st.column_config.TextColumn(width="large"),
                 }, height="auto", row_height=58, key=key, alt="检测记录，包含时间、来源、风险提示及人工状态")
    if not rows:
        st.caption("暂无记录。先在「智能检测」分析一条信息，或在「安全总览」加载虚构演示记录。")


def channel_bars(records):
    values = stats(records)
    maximum = max(values["channels"].values(), default=0) or 1
    for channel in CHANNELS:
        count = values["channels"][channel]
        st.progress(count / maximum, text=f"{channel}　{count} 条")
    st.caption("长度按各渠道记录数相对展示，不是风险概率。来源由用户选择，非后台监控采集。")


def render_report(report, *, prefix="report"):
    st.caption(report["mode_label"])
    if report["mode"] == "fallback":
        st.error(report["warnings"][0])
    alert = {"高风险": st.error, "中风险": st.warning, "信息不足": st.info, "暂未发现明显风险": st.info}[report["risk_level"]]
    # st.text for model content: prevent external Markdown links/images in alerts.
    alert("请结合以下原文线索和未核实事项判断。", title=report["risk_level"])
    st.text(report["summary"])
    if report["needs_review"]:
        st.warning("本地强规则与 AI 判断冲突，需要人工复核。不要据较低风险提示继续敏感操作。")
    st.caption(DISCLAIMER)
    st.subheader("判断依据", icon=":material/fact_check:")
    if not report["evidence"]:
        st.text("没有可展示的直接风险原文依据，请补充来源和业务背景。")
    for item in report["evidence"]:
        st.code(item["quote"], language=None, wrap_lines=True)
        st.text(item["reason"])
    st.subheader("建议核实步骤", icon=":material/checklist:")
    for index, action in enumerate(report["recommendations"], 1):
        st.text(f"{index}. {action}")
    with st.expander("仍需核实的事项"):
        for item in report["uncertainties"]:
            st.text(item)
    if st.session_state["policy"]["display_url_details"]:
        with st.expander(f"网址静态检查 · {len(report['url_results'])} 个"):
            for item in report["url_results"]:
                st.code(item["url"], language=None, wrap_lines=True)
                st.text(f"实际主机名：{item['hostname'] or '无法解析'}")
                for feature in item["features"]:
                    st.text(feature)
                st.caption(item["note"])
            if not report["url_results"]:
                st.text("未提取到支持格式的网址；这不能保证没有变形链接。")
    with st.expander(f"参考资料 · {len(report['citation_ids'])} 条引用"):
        for doc in report["sources"]:
            st.text(f"[{doc['id']}] {doc['title']} · {'报告引用' if doc['id'] in report['citation_ids'] else '仅检索到'}")
            st.text(doc["content"])
            st.link_button("查看公开来源", doc["source_url"], key=f"{prefix}-source-{doc['id']}")
            st.caption(doc["source_scope"])
        st.caption(report["retrieval_method"])
    with st.expander("实际工具执行记录"):
        for event in report["trace"]:
            st.text(f"{event['step']}. [{event['actor']}/{event['status']}] {event['tool']} — {event['detail']}")
        st.caption(f"模型请求 {report['request_count']} 次；模型请求执行工具 {report['model_tool_calls']} 次。")
        if report["token_usage"]:
            st.json(report["token_usage"])
    with st.container(horizontal=True):
        st.download_button("下载文本报告", report_text(report), "fraud-analysis.txt", "text/plain",
                           icon=":material/download:", key=f"{prefix}-txt")
        st.download_button("下载 JSON", json.dumps(report, ensure_ascii=False, indent=2),
                           "fraud-analysis.json", "application/json", key=f"{prefix}-json")
    with st.expander("隐私和判断边界"):
        for warning in report["warnings"]:
            st.text(warning)
