import streamlit as st

from guard.console import safe_log
from ui.common import current_records, page_heading

page_heading("Agent 执行日志", "实际执行的规则检查、工具调用、检索和报告校验 · 不展示模型隐藏思维链", ":material/terminal:")
records = current_records()
text = safe_log(records)
with st.container(border=True, key="panel-log"):
    st.code(text, language="text", wrap_lines=True)
st.download_button("下载执行日志", text, "fraud-execution-log.txt", "text/plain", icon=":material/download:")
st.caption("日志只汇总会话内已保留报告的实际事件，不包含你的 API 密钥、请求头或原始消息。没有发出管理员通知、自动举报或系统拦截。")
