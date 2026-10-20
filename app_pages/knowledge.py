import streamlit as st

from ui.common import load_knowledge, page_heading

page_heading("反诈知识库", "人工整理、带来源的中文学习摘要 · 本地词法检索，不是实时威胁情报", ":material/menu_book:")
query = st.text_input("检索资料", placeholder="例如：招聘、保证金、账户异常、退款", key="knowledge-query", max_chars=240)
documents = load_knowledge().search(query, limit=4) if query.strip() else load_knowledge().documents
if not documents:
    st.info("没有检索到相关资料；不会让模型编造来源。")
for doc in documents:
    with st.container(border=True, key=f"panel-knowledge-{doc['id']}"):
        st.subheader(doc["title"])
        st.badge(f"{doc['id']} · {doc['category']}", color="blue")
        st.text(doc["content"])
        st.caption(doc["source_scope"])
        st.link_button(doc["source_title"], doc["source_url"], icon=":material/open_in_new:")
        st.caption(f"资料收录核对：{doc['reviewed_at']}；{doc['kind']}")
with st.expander("项目能力与安全边界"):
    st.text("本地规则与 AI 都可能误报或漏报，输出结构有效不代表语义正确。只做辅助核实，不认定诈骗事实。")
    st.text("当前未实现截图 OCR、恶意软件检测、网站信誉查询、自动拦截、后台消息监控、向量检索或跨会话历史数据库。")
