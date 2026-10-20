import pandas as pd
import streamlit as st

from guard.console import stats
from ui.common import channel_bars, current_records, generate_demo, kpis, page_heading, records_table

records = current_records()
summary = stats(records)
page_heading("安全总览", "反诈检测、风险线索与人工核实进度。数据仅限当前所选范围。", ":material/dashboard:")
kpis(records)
with st.container(horizontal=True):
    if st.button("新建检测", type="primary", key="go-detect", icon=":material/add:"):
        st.switch_page("app_pages/detection.py")
    st.button("加载演示记录", on_click=generate_demo, key="load-demo",
              help="运行7条虚构案例的本地检查，不调用模型，与当前会话分开保留。")
left, right = st.columns([1.15, 1], gap="medium")
with left.container(border=True, key="panel-high", height="stretch"):
    st.subheader("优先核实事项", icon=":material/report:")
    st.caption("高风险且待复核的信息，最多显示3条；这里只提醒，不执行拦截。")
    high = [item for item in reversed(records) if item["risk_level"] == "高风险" and item["review_state"] == "待复核"]
    if high:
        st.dataframe(pd.DataFrame([{"时间": item["time"][11:], "来源": item["channel"],
                                   "内容摘要": item["title"]} for item in high[:3]]),
                     hide_index=True, height="auto", row_height=64,
                     column_config={"内容摘要": st.column_config.TextColumn(width="large")},
                     alt="最多三条高风险待复核信息，未执行自动拦截或管理员通知")
        st.page_link("app_pages/records.py", label="查看记录与核实详情", icon=":material/receipt_long:")
    else:
        st.text("暂无高风险待复核事项")
        st.caption("没有记录不代表已经完成安全检查。")
with right.container(border=True, key="panel-channels", height="stretch"):
    st.subheader("信息来源分布", icon=":material/bar_chart:")
    channel_bars(records)

with st.container(border=True, key="panel-recent"):
    st.subheader("最新检测记录", icon=":material/history:")
    records_table(list(reversed(records)), key="recent-records", limit=8)
    st.caption(f"当前共 {summary['total']} 条，最多保留50条。仅存本次会话内存，需要留存请主动导出。")
