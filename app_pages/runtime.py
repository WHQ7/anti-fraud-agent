import platform

import pandas as pd
import streamlit as st

from guard.config import get_api_key, get_model
from guard.console import now_label, stats
from ui.common import current_records, load_knowledge, page_heading

page_heading("运行状态", f"展示当前应用的真实配置与能力 · 页面时间 {now_label()} · 不扫描你的其他终端", ":material/desktop_windows:")
has_key = bool(get_api_key())
summary = stats(current_records())
with st.container(border=True, key="panel-runtime"):
    st.subheader("当前应用实例", icon=":material/desktop_windows:")
    st.table(pd.DataFrame([{
        "实例": "本机反诈控制台", "访问范围": "127.0.0.1:8503", "页面": "当前可运行",
        "Python": platform.python_version(), "Streamlit": st.__version__,
        "知识资料": f"{len(load_knowledge().documents)} 条", "当前范围记录": f"{summary['total']} 条",
    }]), hide_index=True, alt="本机应用实例及版本信息")
    st.caption("页面可运行不代表 DeepSeek 接口已经验证。密钥仅检查可读取状态，不回显其值。")

with st.container(border=True, key="panel-capabilities"):
    st.subheader("应用防护能力", icon=":material/verified_user:")
    abilities = [
        {"能力": "文本规则与否定语境", "说明": "处理当前手动提交的文本，可能误报或漏报", "状态": "已实现"},
        {"能力": "网址静态结构分析", "说明": "仅解析字符串，不访问网页，不查询证书或黑名单", "状态": "已实现"},
        {"能力": "本地知识检索", "说明": "关键词 + BM25 风格排序，尚未使用向量数据库", "状态": "已实现"},
        {"能力": "DeepSeek Agent", "说明": f"配置模型 {get_model()}；确认发送后才调用", "状态": "密钥可读取 / 接口未主动探测" if has_key else "未读取到密钥"},
        {"能力": "当前范围的 AI 成功报告", "说明": "来自所选范围已完成的检测，不是实时连通性认证", "状态": str(summary["agent"]) + " 份"},
        {"能力": "后台消息监控 / 自动拦截", "说明": "不读取微信、邮件、剪贴板，不安装终端代理", "状态": "未实现 / 未启用"},
    ]
    st.dataframe(pd.DataFrame(abilities), hide_index=True, height="auto", row_height=62, alt="应用能力及实际实现状态")
st.info("这是本机单用户学习原型，尚无公网登录、租户隔离和请求限额。不要直接开放到公网。")
