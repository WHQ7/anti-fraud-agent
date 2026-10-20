import hashlib

import streamlit as st

from guard.agent import MAX_INPUT_CHARS, analyze, validate_input
from guard.config import get_api_key, get_model
from guard.console import CHANNELS
from guard.privacy import redact
from guard.transport import DeepSeekTransport
from ui.common import load_examples, load_knowledge, page_heading, register_report, render_report


def load_example():
    selected = st.session_state["example_choice"]
    if selected != "自己输入":
        st.session_state["message"] = next(item["text"] for item in load_examples() if item["title"] == selected)
    st.session_state["result"] = None
    st.session_state["consent"] = False


def clear_input():
    st.session_state["message"] = ""
    st.session_state["result"] = None
    st.session_state["consent"] = False
    st.session_state["example_choice"] = "自己输入"


def revoke_consent():
    st.session_state["consent"] = False


page_heading("智能检测", "粘贴可疑信息，查看风险依据和核实建议。", ":material/search:")
input_col, output_col = st.columns([1, 1.1], gap="medium")
mode = "agent" if st.session_state["mode"] == "DeepSeek Agent" else "local"
with input_col.container(border=True, key="panel-input"):
    st.subheader("输入信息")
    source, example = st.columns([1, 1.6], gap="small")
    source.selectbox("信息来源", CHANNELS, key="input_channel", persist_state="session")
    example.selectbox("试一个虚构案例", ["自己输入", *[item["title"] for item in load_examples()]],
                      key="example_choice", on_change=load_example, persist_state="session")
    st.text_area("待分析内容", height=220, max_chars=MAX_INPUT_CHARS, key="message",
                 placeholder="粘贴收到的信息。不要填写真实验证码、密码、密钥或其他私密资料。",
                 on_change=revoke_consent, persist_state="session")
    preview, count = redact(st.session_state["message"])
    if mode == "agent":
        with st.expander("检查脱敏后的分析内容", expanded=True, icon=":material/visibility:"):
            st.code(preview or "尚未输入内容", language=None, wrap_lines=True)
            st.caption(f"已尽力替换 {count} 处，仍可能漏检。请自行检查后再发送。")
        st.caption(f"模型：{get_model()} · 最多3次请求 · apikey {'可读取' if get_api_key() else '未读取到'}")
        st.checkbox("我已检查预览，同意将内容与工具结果发送到 DeepSeek，并承担 API 调用费用。", key="consent")
    with st.container(horizontal=True):
        submitted = st.button("开始分析", type="primary", icon=":material/search:", key="analyze")
        st.button("清空输入", on_click=clear_input, key="clear", icon=":material/backspace:")
    st.caption("本地检查，不联网。可在侧栏「分析设置与隐私」切换 AI。" if mode == "local" else "AI 模式：仅在你确认后发送到 DeepSeek。")
    with st.expander("记录选项与隐私"):
        st.toggle("在本次会话保留已脱敏报告（最多50份）", key="recording", persist_state="session")
        st.caption("新检测仅加入当前会话，不混入演示样例。关闭开关后不加入记录列表。")
        if mode == "local":
            st.code(preview or "尚未输入内容", language=None, wrap_lines=True)
            st.caption(f"这是本地分析使用的脱敏内容，已尽力替换 {count} 处，仍可能遗漏。")

with output_col.container(border=True, key="panel-output"):
    st.subheader("检测结果")
    if submitted:
        st.session_state["result"] = None
        error = ""
        try:
            validate_input(st.session_state["message"])
            if mode == "agent" and not st.session_state["consent"]:
                error = "请先检查脱敏预览，再勾选外部 API 使用同意项。"
            elif mode == "agent" and not get_api_key():
                error = "未读取到 apikey。可以先使用本地检查，或设置环境变量后重启应用。"
        except ValueError as exc:
            error = str(exc)
        if error:
            st.error(error)
        else:
            with st.status("正在检查线索…", expanded=True) as progress:
                def update_progress(event):
                    st.text(f"{event['step']}. {event['tool']}：{event['detail']}")

                try:
                    transport = DeepSeekTransport(get_api_key(), get_model()) if mode == "agent" else None
                    report = analyze(st.session_state["message"], mode=mode, transport=transport,
                                     consent=st.session_state["consent"], knowledge=load_knowledge(), on_event=update_progress)
                    st.session_state["result"] = report
                    st.session_state["result_fingerprint"] = hashlib.sha256(st.session_state["message"].encode()).hexdigest()
                    register_report(report, st.session_state["input_channel"])
                    progress.update(label="AI 未完成，仅保留本地结果" if report["mode"] == "fallback" else "检测完成，请独立核实",
                                    state="error" if report["mode"] == "fallback" else "complete", expanded=False)
                except Exception:
                    progress.update(label="检测未完成", state="error")
                    st.error("遇到内部错误，未生成报告。请先使用本地检查；不要公开密钥或私人输入。")
    report = st.session_state["result"]
    if report:
        fingerprint = hashlib.sha256(st.session_state["message"].encode()).hexdigest()
        if fingerprint != st.session_state["result_fingerprint"]:
            st.warning("输入已修改，下方仍是上一次报告；请重新分析。")
        render_report(report)
    elif not submitted:
        st.text("尚未检测")
        st.caption("输入内容后点击「开始分析」，这里显示结论、原文依据和核实建议。")
