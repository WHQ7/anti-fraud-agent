import streamlit as st

from guard.console import CHANNELS, REVIEW_STATES, csv_export, filter_records
from guard.reports import LEVELS
from ui.common import current_records, page_heading, records_table, render_report

page_heading("检测记录查询", "筛选短信、邮件、聊天和网址检测 · 记录仅保留在本次会话 · 人工标记不等于系统已验证身份", ":material/receipt_long:")
records = current_records()
with st.container(border=True, key="panel-query"):
    with st.form("record-filters", border=False):
        first, second, third = st.columns(3)
        channel = first.selectbox("来源渠道", ["全部渠道", *CHANNELS], key="filter-channel")
        risk = second.selectbox("风险提示", ["全部风险", *LEVELS], key="filter-risk")
        review = third.selectbox("人工状态", ["全部状态", *REVIEW_STATES], key="filter-review")
        keyword = st.text_input("搜索摘要或结论", key="filter-keyword", max_chars=100)
        st.form_submit_button("查询记录", type="primary", icon=":material/search:")
    filtered = filter_records(records, channel=channel, risk=risk, review=review, keyword=keyword)
    st.caption(f"当前范围共 {len(records)} 条，筛选后 {len(filtered)} 条。")
    records_table(filtered, key="query-records")
    st.download_button("导出筛选记录 CSV", csv_export(filtered), "fraud-records.csv", "text/csv",
                       icon=":material/download:", key="export-records")

if filtered:
    with st.container(border=True, key="panel-record-detail"):
        st.subheader("记录详情与人工复核", icon=":material/fact_check:")
        selected = st.selectbox("选择记录", [item["id"] for item in filtered],
                                format_func=lambda value: next(f"{item['time']} · {item['title']}" for item in filtered if item["id"] == value), key="selected-record")
        record = next(item for item in filtered if item["id"] == selected)
        with st.form("review-form", border=False):
            state = st.selectbox("人工复核标记", REVIEW_STATES, index=REVIEW_STATES.index(record["review_state"]), key=f"review-{selected}")
            if st.form_submit_button("保存人工标记", icon=":material/save:", key="save-review"):
                record["review_state"] = state
                st.rerun()
        st.caption(f"检测时提醒策略：{record['action']}。保留检测时策略快照，修改策略不会重写旧结论。")
        render_report(record["report"], prefix=f"detail-{selected}")

with st.expander("清空当前范围的会话记录"):
    st.caption("只清空内存中的当前范围，不删除你的项目文件或知识库。")
    confirmed = st.checkbox("确认清空当前范围的全部记录", key="confirm-clear-records")
    if st.button("清空记录", disabled=not confirmed, key="clear-records"):
        key = "demo_records" if st.session_state["data_scope"] == "演示样例" else "records"
        st.session_state[key] = []
        st.rerun()
