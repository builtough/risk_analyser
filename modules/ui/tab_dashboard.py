"""Analytics Tab — charts and statistics."""
import streamlit as st
import pandas as pd

from modules.visualizer import (plot_keyword_frequency, plot_risk_distribution,
                                 plot_category_breakdown, plot_keyword_heatmap,
                                 plot_document_stats)
from modules.ui.helpers import clean, metric_card


def render_tab_dashboard():
    st.markdown('<div class="da-sec">📊 Analytics · Visualizations & Statistics</div>',
                unsafe_allow_html=True)

    has_analysis = bool(st.session_state.get("score_summary"))
    has_search   = bool(st.session_state.get("freq_data"))
    has_docs     = bool(st.session_state.get("documents"))

    if not has_analysis and not has_search:
        st.markdown(
            '<div class="empty-state"><div class="es-icon">📊</div>'
            '<h3>No Data Yet</h3>'
            '<p>Run a Risk Analysis or Keyword Search first.</p></div>',
            unsafe_allow_html=True)
        return

    # ── Corpus stats ─────────────────────────────────────────────────────────
    if has_docs:
        docs    = [d for d in st.session_state.documents if not d.get("error")]
        total_w = sum(len(d.get("raw_text","").split()) for d in docs)
        total_c = sum(len(d.get("raw_text",""))         for d in docs)

        st.markdown("#### Corpus Statistics")
        ts1, ts2, ts3, ts4 = st.columns(4)
        for col, val, lbl in [
            (ts1, len(docs),                              "Documents"),
            (ts2, f"{total_w:,}",                         "Words"),
            (ts3, f"{total_c:,}",                         "Characters"),
            (ts4, len(st.session_state.get("chunks",[])), "Chunks"),
        ]:
            with col:
                st.markdown(metric_card(val, lbl), unsafe_allow_html=True)
        st.markdown("")

        with st.expander("📋 Per-Document Breakdown"):
            rows = [{"Document": d["filename"], "Type": d.get("type","").upper(),
                     "Words": len(d.get("raw_text","").split()),
                     "Chars": len(d.get("raw_text","")),
                     "Sections": len(d.get("pages",[]))}
                    for d in docs]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.plotly_chart(plot_document_stats(docs), use_container_width=True)

    # ── Risk analysis charts ──────────────────────────────────────────────────
    if has_analysis:
        st.markdown("#### Risk Analysis")
        rc1, rc2 = st.columns(2)
        with rc1:
            st.plotly_chart(plot_risk_distribution(st.session_state.score_summary),
                            use_container_width=True)
        with rc2:
            st.plotly_chart(plot_category_breakdown(st.session_state.score_summary),
                            use_container_width=True)

        if st.session_state.get("findings"):
            st.markdown("#### All Findings Table")
            df = pd.DataFrame([{
                "Risk":             f.get("risk_level",""),
                "Category":         clean(f.get("category_label","")),
                "Document":         f.get("filename",""),
                "Lines":            f"{f.get('start_line','?')}–{f.get('end_line','?')}",
                "Finding":          clean(f.get("finding",""))[:120],
                "Flagged Language": clean(f.get("problematic_language",""))[:100],
                "Interpretation":   clean(f.get("interpretation",""))[:150],
            } for f in st.session_state.findings])
            st.dataframe(df, use_container_width=True, hide_index=True,
                         height=min(700, (len(df)+1)*38+50))

    # ── Keyword charts ────────────────────────────────────────────────────────
    if has_search:
        st.markdown("#### Keyword Analytics")
        st.plotly_chart(plot_keyword_frequency(st.session_state.freq_data),
                        use_container_width=True)
        st.plotly_chart(plot_keyword_heatmap(st.session_state.freq_data),
                        use_container_width=True)
