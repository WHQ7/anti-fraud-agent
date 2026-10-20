import streamlit as st

from guard.console import now_label, validate_policy
from ui.common import page_heading

page_heading("检测策略调整", "调整会话内的核实提醒和显示设置 · 不修改操作系统，不下发终端，不自动拦截", ":material/tune:")
policy = st.session_state["policy"]
with st.form("policy-form", border=False):
    left, right = st.columns(2, gap="large")
    with left.container(border=True, key="panel-policy-reminders", height="stretch"):
        st.subheader("分级核实提醒", icon=":material/notifications_active:")
        high = st.checkbox("高风险线索标记为「优先核实」", value=policy["high_priority"], key="policy-high")
        medium = st.checkbox("中风险线索标记为「建议核实」", value=policy["medium_priority"], key="policy-medium")
        context = st.checkbox("信息不足时提示「补充信息」", value=policy["ask_for_context"], key="policy-context")
        st.caption("关闭提醒不会删除规则证据，也不会把风险改成安全。AI 与强规则冲突时始终要求复核。")
    with right.container(border=True, key="panel-policy-boundary", height="stretch"):
        st.subheader("结果展示与安全边界", icon=":material/shield:")
        show_urls = st.checkbox("显示网址静态检查详情", value=policy["display_url_details"], key="policy-url")
        st.checkbox("调用外部 AI 前必须确认发送内容", value=True, disabled=True)
        st.checkbox("禁止访问可疑网址和执行消息中的代码", value=True, disabled=True)
        st.checkbox("禁止在日志中输出密钥和原始消息", value=True, disabled=True)
        st.caption("后三项为固定边界，不提供关闭选项。网址详情隐藏不影响后台的静态检查。")
    with st.container(border=True, key="panel-policy-summary"):
        st.subheader("策略应用范围", icon=":material/info:")
        st.text("提醒设置作用于保存后新生成的记录；旧记录保留检测时策略快照。显示设置作用于当前页面。策略只在当前会话有效，不写入磁盘。")
        st.caption("不显示人为设定的诈骗概率或未经校准的风险分数。风险分级来自规则或 AI 分析，仍需人工核实。")
    saved = st.form_submit_button("保存并应用到本次会话", type="primary", icon=":material/save:", key="save-policy")
    if saved:
        st.session_state["policy"] = validate_policy({"high_priority": high, "medium_priority": medium,
            "ask_for_context": context, "display_url_details": show_urls})
        st.session_state["policy_version"] += 1
        st.session_state["policy_updated"] = now_label()
        st.success("策略已应用到本次会话。未修改系统设置或任何原始分析结论。")
st.caption(f"会话策略版本 {st.session_state['policy_version']} · 最近更新 {st.session_state['policy_updated']}")
