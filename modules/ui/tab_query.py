"""LLM Query Tab — RAG-powered natural language Q&A over contracts."""
import streamlit as st
from html import escape as html_escape
from datetime import datetime

from modules.llm_backend import LLMBackend
from modules.search import build_query_prompt, simple_relevance_search

EXAMPLES = [
    "What are the termination rights of each party?",
    "Are there any automatic renewal or evergreen clauses?",
    "What royalty or fee structures are defined?",
    "What indemnification obligations does the buyer carry?",
    "What are the governing law and dispute resolution provisions?",
    "Are there non-compete or exclusivity restrictions?",
]


def render_tab_query():
    st.markdown('<div class="da-sec">💬 Natural Language Query · RAG-Powered</div>',
                unsafe_allow_html=True)

    if not st.session_state.get("chunks"):
        st.markdown(
            '<div class="empty-state"><div class="es-icon">💬</div>'
            '<h3>No Documents Loaded</h3>'
            '<p>Upload and load documents via the sidebar first.</p></div>',
            unsafe_allow_html=True)
        return

    with st.expander("💡 Example questions — click to populate"):
        ec = st.columns(2)
        for i, eq in enumerate(EXAMPLES):
            with ec[i % 2]:
                if st.button(eq, key=f"eq_{i}", use_container_width=True):
                    st.session_state.active_query = eq
                    st.rerun()

    user_q = st.text_area(
        "Your question",
        value=st.session_state.get("active_query", ""),
        placeholder="Type or click an example above…",
        height=90, label_visibility="collapsed",
    )
    st.session_state.active_query = user_q

    qc1, qc2 = st.columns([1, 5])
    with qc1:
        top_k = st.selectbox("Context chunks", [3, 5, 6, 8, 10], index=1)
    with qc2:
        st.markdown("<div style='padding-top:22px'></div>", unsafe_allow_html=True)
        submit_q = st.button("💬 Ask Question", type="primary")

    if submit_q:
        question = st.session_state.active_query.strip()
        if not question:
            st.warning("Please type or select a question first.")
        elif "backend_kwargs" not in st.session_state:
            st.error("Configure the AI backend in the sidebar.")
        else:
            with st.spinner("Retrieving context and generating answer…"):
                relevant = simple_relevance_search(st.session_state.chunks, question, top_k)
                prompt   = build_query_prompt(question, relevant)
                result   = LLMBackend(**st.session_state.backend_kwargs).query(prompt)
            if result.get("error"):
                st.error(f"LLM Error: {result['error']}")
            else:
                st.session_state.query_history = st.session_state.get("query_history", [])
                st.session_state.query_history.append({
                    "question": question,
                    "response": result.get("response", ""),
                    "chunks":   len(relevant),
                    "ts":       datetime.now().strftime("%H:%M"),
                })
                st.session_state.active_query = ""
                st.rerun()

    history = st.session_state.get("query_history", [])
    if history:
        st.markdown("---")
        for item in reversed(history):
            st.markdown(
                f'<div class="q-bub">Q: {html_escape(item["question"])}</div>',
                unsafe_allow_html=True)
            resp = html_escape(item["response"]).replace("\n", "<br>")
            st.markdown(
                f'<div class="a-bub">'
                f'<div class="a-lbl">⚖ AI Analysis · {item["ts"]} · {item["chunks"]} sections</div>'
                f'{resp}</div>',
                unsafe_allow_html=True)
            st.markdown("")
        if st.button("🗑 Clear History"):
            st.session_state.query_history = []
            st.rerun()
