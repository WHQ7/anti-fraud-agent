from collections import Counter

import pandas as pd
import streamlit as st

from guard.console import CHANNELS, csv_export, filter_records, stats
from ui.common import current_records, kpis, page_heading

page_heading("安全统计报表", "根据当前范围的实际记录即时汇总 · 不是全天候监测或识别准确率报表", ":material/monitoring:")
period = st.segmented_control("统计范围", ["本次全部", "近7天", "近30天"], default="本次全部", required=True, key="stats-period")
records = filter_records(current_records(), days={"本次全部": None, "近7天": 7, "近30天": 30}[period])
summary = stats(records)
kpis(records)
left, right = st.columns(2, gap="large")
with left.container(border=True, key="panel-stats-channels", height="stretch"):
    st.subheader("来源渠道统计", icon=":material/bar_chart:")
    rows = [{"来源渠道": channel, "检测数": sum(item["channel"] == channel for item in records),
             "高风险线索": sum(item["channel"] == channel and item["risk_level"] == "高风险" for item in records),
             "已人工标记核实": sum(item["channel"] == channel and item["review_state"] == "已核实" for item in records)} for channel in CHANNELS]
    st.dataframe(pd.DataFrame(rows), hide_index=True, height="auto", alt="所选范围各渠道的检测数、高风险数和已人工核实数量")
    st.subheader("风险提示分布")
    distribution = Counter(item["risk_level"] for item in records)
    if records:
        st.bar_chart(pd.DataFrame([{"风险提示": key, "数量": value} for key, value in distribution.items()]),
                     x="风险提示", y="数量", horizontal=True, color="#4055B5", height=190, alt="当前记录的风险提示数量分布，不代表预测概率")
    else:
        st.caption("尚无数据，完成检测后再统计，不生成虚构趋势。")
with right.container(border=True, key="panel-stats-top", height="stretch"):
    st.subheader("优先核实记录", icon=":material/priority_high:")
    high = [item for item in records if item["risk_level"] == "高风险"]
    if high:
        for item in high[:5]:
            st.text(item["title"])
            st.caption(f"{item['time']} · {item['channel']} · {item['review_state']}")
            st.badge(item["action"], color="red")
    else:
        st.info("当前范围没有高风险线索记录。")
    st.text(f"本次范围共 {summary['total']} 条；AI 成功 {summary['agent']} 条；AI 失败回退 {summary['fallback']} 条。")
    st.caption("这些数字只描述本次会话的检测运行结果，不是防护效果、诈骗概率或识别准确率。")
st.download_button("导出本次统计明细 CSV", csv_export(records), "fraud-statistics.csv", "text/csv",
                   icon=":material/download:", key="download-stats")
