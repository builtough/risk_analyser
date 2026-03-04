"""
Risk Analysis Tab — AI-powered clause detection with smart filters.
Quick-filter buttons: All · Critical Errors · Misleading Clauses · By Category.
"""
import streamlit as st
from html import escape as html_escape

from modules.llm_backend import LLMBackend
from modules.analyzer import (RISK_CATEGORIES, build_analysis_prompt,
                               parse_llm_risk_response, keyword_scan_chunk, score_findings)
from modules.ui.helpers import clean, badge, metric_card


# ── Category groupings for quick filters ────────────────────────────────────
FILTER_GROUPS = {
    "🔴 Critical Errors": {
        "desc": "HIGH risk findings across all categories",
        "risk_levels": ["HIGH"],
        "categories": list(RISK_CATEGORIES.keys()),
    },
    "⚠️ Misleading Clauses": {
        "desc": "Vague, ambiguous or deceptive language",
        "risk_levels": ["HIGH", "MEDIUM", "LOW"],
        "categories": ["misleading_clauses"],
    },
    "💰 Profit-Shifting": {
        "desc": "Hidden fees and royalty mechanisms",
        "risk_levels": ["HIGH", "MEDIUM", "LOW"],
        "categories": ["profit_shifting"],
    },
    "⚖️ Liability & Indemnity": {
        "desc": "Indemnification and liability exposure",
        "risk_levels": ["HIGH", "MEDIUM", "LOW"],
        "categories": ["indemnity_risks"],
    },
    "🚫 Restrictions": {
        "desc": "Non-compete, exclusivity and market limits",
        "risk_levels": ["HIGH", "MEDIUM", "LOW"],
        "categories": ["competition_restrictions"],
    },
    "🪤 Penalty Traps": {
        "desc": "Auto-renewals and punitive exit clauses",
        "risk_levels": ["HIGH", "MEDIUM", "LOW"],
        "categories": ["penalty_traps", "hidden_obligations"],
    },
}


def render_tab_analysis():
    st.markdown('<div class="da-sec">⚖ Contractual Risk Detection · AI-Powered</div>',
                unsafe_allow_html=True)

    if not st.session_state.get("documents"):
        st.markdown(
            '<div class="empty-state"><div class="es-icon">⚖</div>'
            '<h3>No Documents Loaded</h3>'
            '<p>Upload documents via the sidebar to begin analysis.</p></div>',
            unsafe_allow_html=True)
        return

    # ── Category checkboxes ──────────────────────────────────────────────────
    with st.expander("🎯 Select Risk Categories to Detect", expanded=True):
        cols = st.columns(3)
        selected_cats = []
        for i, (ck, ci) in enumerate(RISK_CATEGORIES.items()):
            with cols[i % 3]:
                if st.checkbox(ci["label"], value=True, key=f"cat_{ck}"):
                    selected_cats.append(ck)

    st.markdown(
        '<div class="info-strip">💡 Documents are <strong>keyword-scanned first</strong> '
        '(no API cost), then only suspicious sections are sent to the LLM for deep analysis.'
        '</div>', unsafe_allow_html=True)

    # ── Run button ───────────────────────────────────────────────────────────
    if st.button("🚀 Run Risk Analysis", type="primary", disabled=not selected_cats):
        _run_analysis(selected_cats)

    # ── Results ──────────────────────────────────────────────────────────────
    if st.session_state.get("analysis_done") and st.session_state.get("score_summary"):
        _render_score_summary()

    if st.session_state.get("findings"):
        st.markdown("---")
        _render_findings_with_filters()


# ── Internal helpers ─────────────────────────────────────────────────────────

def _run_analysis(selected_cats: list):
    if "backend_kwargs" not in st.session_state:
        st.error("Configure AI backend in the sidebar first.")
        return

    backend = LLMBackend(**st.session_state.backend_kwargs)
    pre = [
        (ch, {k: v for k, v in keyword_scan_chunk(ch["text"]).items() if k in selected_cats})
        for ch in st.session_state.chunks
    ]
    pre = [(ch, h) for ch, h in pre if h]

    if not pre:
        st.warning("No chunks matched risk keyword patterns. Try different categories.")
        return

    total = sum(len(h) for _, h in pre)
    st.info(f"Keyword scan done — {total} clause segments to analyse…")
    findings, prog, stat = [], st.progress(0), st.empty()
    n = 0

    for chunk, hit_cats in pre:
        for category in hit_cats:
            stat.caption(
                f"Analysing {chunk['filename']} · "
                f"lines {chunk.get('start_line','?')}–{chunk.get('end_line','?')} · "
                f"{RISK_CATEGORIES[category]['label']}"
            )
            res = backend.query(build_analysis_prompt(chunk["text"], category))
            if res.get("error"):
                st.warning(f"LLM error: {res['error']}")
            elif res.get("response"):
                f = parse_llm_risk_response(res["response"], chunk, category)
                if f:
                    f["start_line"] = chunk.get("start_line", "?")
                    f["end_line"]   = chunk.get("end_line", "?")
                    findings.append(f)
            n += 1
            prog.progress(min(n / max(total, 1), 1.0))

    prog.progress(1.0)
    stat.empty()
    st.session_state.findings      = findings
    st.session_state.score_summary = score_findings(findings)
    st.session_state.analysis_done = True
    st.success(f"✓ Analysis complete — {len(findings)} findings.")


def _render_score_summary():
    s  = st.session_state.score_summary
    ov = s.get("overall_risk", "LOW")
    m1, m2, m3, m4, m5 = st.columns(5)
    for col, val, lbl, cls in [
        (m1, ov,                "Overall Risk",  f"mc-{ov}"),
        (m2, s.get("total", 0), "Total",         "mc-blue"),
        (m3, s.get("high",  0), "High Risk",     "mc-HIGH"),
        (m4, s.get("medium",0), "Medium Risk",   "mc-MEDIUM"),
        (m5, s.get("low",   0), "Low Risk",      "mc-LOW"),
    ]:
        with col:
            st.markdown(metric_card(val, lbl, cls), unsafe_allow_html=True)
    st.markdown("")


def _render_findings_with_filters():
    findings = st.session_state.findings

    # ── Quick-filter buttons (stateful via session_state) ────────────────────
    if "analysis_quick_filter" not in st.session_state:
        st.session_state.analysis_quick_filter = "All Findings"

    st.markdown("**Quick Filters:**")
    filter_options = ["All Findings"] + list(FILTER_GROUPS.keys())
    btn_cols = st.columns(len(filter_options))
    for i, opt in enumerate(filter_options):
        with btn_cols[i]:
            is_active = st.session_state.analysis_quick_filter == opt
            label = opt
            if st.button(label, key=f"qf_{i}",
                         type="primary" if is_active else "secondary",
                         use_container_width=True):
                st.session_state.analysis_quick_filter = opt
                st.rerun()

    # Show description for active filter
    active = st.session_state.analysis_quick_filter
    if active != "All Findings":
        st.caption(f"ℹ {FILTER_GROUPS[active]['desc']}")

    st.markdown("")

    # ── Advanced filters (collapsed) ─────────────────────────────────────────
    with st.expander("🔧 Advanced Filters"):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            f_risk = st.multiselect("Risk Level", ["HIGH", "MEDIUM", "LOW"],
                                     default=["HIGH", "MEDIUM", "LOW"])
        with fc2:
            f_cat = st.multiselect(
                "Category", list(RISK_CATEGORIES.keys()),
                format_func=lambda k: RISK_CATEGORIES[k]["label"],
                default=list(RISK_CATEGORIES.keys()),
            )
        with fc3:
            all_docs = list({f["filename"] for f in findings})
            f_doc = st.multiselect("Document", all_docs, default=all_docs)

    # Apply quick filter first, then advanced filters on top
    if active == "All Findings":
        qf_risk = ["HIGH", "MEDIUM", "LOW"]
        qf_cats = list(RISK_CATEGORIES.keys())
    else:
        g = FILTER_GROUPS[active]
        qf_risk = g["risk_levels"]
        qf_cats = g["categories"]

    # Intersection with advanced filters
    final_risk = [r for r in f_risk if r in qf_risk]
    final_cats = [c for c in f_cat if c in qf_cats]

    filtered = [
        f for f in findings
        if f.get("risk_level") in final_risk
        and f.get("category")  in final_cats
        and f.get("filename")  in f_doc
    ]

    # Count badges
    high_n   = sum(1 for f in filtered if f.get("risk_level") == "HIGH")
    medium_n = sum(1 for f in filtered if f.get("risk_level") == "MEDIUM")
    low_n    = sum(1 for f in filtered if f.get("risk_level") == "LOW")

    st.markdown(
        f'Showing **{len(filtered)}** of {len(findings)} findings &nbsp; '
        f'<span class="badge badge-HIGH">{high_n} HIGH</span> &nbsp;'
        f'<span class="badge badge-MEDIUM">{medium_n} MEDIUM</span> &nbsp;'
        f'<span class="badge badge-LOW">{low_n} LOW</span>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    if not filtered:
        st.info("No findings match the current filters.")
        return

    # ── Render finding cards ─────────────────────────────────────────────────
    for finding in filtered:
        _render_finding_card(finding)


def _render_finding_card(finding: dict):
    risk   = finding.get("risk_level", "LOW")
    cat    = clean(finding.get("category_label", ""))
    fname  = html_escape(finding.get("filename", ""))
    sl, el = finding.get("start_line", "?"), finding.get("end_line", "?")
    txt    = clean(finding.get("finding", ""))
    prob   = clean(finding.get("problematic_language", ""))
    interp = clean(finding.get("interpretation", ""))
    qs     = [clean(q) for q in finding.get("follow_up_questions", []) if q]

    quote_html = (
        f'<div class="fc-quote">{html_escape(prob)}</div>'
        if prob and prob.upper() not in ("N/A", "") else ""
    )
    qs_html = ""
    if qs:
        items  = "".join(f'<div class="fc-qi">{html_escape(q)}</div>' for q in qs)
        qs_html = f'<div class="fc-qlbl">Legal Team Follow-up Questions</div>{items}'

    st.markdown(f"""
    <div class="fc fc-{risk}">
      <div class="fc-hdr">
        {badge(risk)}
        <span class="fc-cat">{html_escape(cat)}</span>
        <span class="fc-src">{fname}</span>
        <span class="fc-ln">Lines {sl}–{el}</span>
      </div>
      <div class="fc-find">{html_escape(txt)}</div>
      {quote_html}
      <div class="fc-interp">{html_escape(interp)}</div>
      {qs_html}
    </div>""", unsafe_allow_html=True)
