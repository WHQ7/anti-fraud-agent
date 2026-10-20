"""辨信消息核验工作台：本机、单用户、会话内存记录，不后台监控。"""

import importlib
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guard.config import get_api_key
import ui.common as console_ui

# Refresh a previously running v0.1/v0.2 process once, without restarting the
# server or discarding the user's in-memory reports. Fresh launches skip this.
if getattr(console_ui, "UI_BUILD", None) != "console-20261020-refined-label":
    importlib.reload(console_ui)
from ui.common import init_state

st.set_page_config(page_title="辨信 · 反诈安全管理台", page_icon=":material/chat:", layout="wide", initial_sidebar_state="auto")
init_state()
st.logo(str(ROOT / "assets" / "logo.svg"), size="large", icon_image=str(ROOT / "assets" / "mark.svg"))

page = st.navigation([
    st.Page("app_pages/overview.py", title="安全总览", icon=":material/dashboard:", default=True),
    st.Page("app_pages/detection.py", title="智能检测", icon=":material/search:"),
    st.Page("app_pages/records.py", title="检测记录查询", icon=":material/receipt_long:"),
    st.Page("app_pages/policy.py", title="检测策略调整", icon=":material/tune:"),
    st.Page("app_pages/runtime.py", title="运行状态", icon=":material/desktop_windows:"),
    st.Page("app_pages/statistics.py", title="安全统计报表", icon=":material/monitoring:"),
    st.Page("app_pages/logs.py", title="Agent 执行日志", icon=":material/terminal:"),
    st.Page("app_pages/knowledge.py", title="反诈知识库", icon=":material/menu_book:"),
], position="sidebar", expanded=True)


def revoke_consent():
    st.session_state["consent"] = False


with st.sidebar:
    st.segmented_control("记录数据范围", ["当前会话", "演示样例"], key="data_scope", required=True)
    with st.expander("分析设置与隐私", icon=":material/lock:"):
        st.segmented_control("默认分析方式", ["本地检查", "DeepSeek Agent"], key="mode", required=True, on_change=revoke_consent)
        if st.session_state["mode"] == "DeepSeek Agent":
            available = bool(get_api_key())
            st.badge("apikey 可读取" if available else "未读取到 apikey", color="green" if available else "orange")
            st.caption("可读取不等于接口已验证；仅在智能检测页确认后调用。")
        else:
            st.caption("本地规则模式，不联网，不消耗模型额度。")
        st.text("本次会话最多保留50份已脱敏检测报告，不写入磁盘。演示与真实检测分开。关闭会话后由框架释放内存，不承诺立即擦除。")
    st.caption("本机单用户原型 · 不后台监控")

with st.container(key="console-root"):
    page.run()

st.caption("辨信 · 仅辅助核实，不访问可疑链接，不后台读取消息。")
