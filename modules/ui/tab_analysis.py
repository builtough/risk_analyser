"""
Risk Analysis Tab
- Built-in category checkboxes
- Custom clause builder: add/edit/delete categories at runtime
- Quick-filter buttons post-analysis
"""
import streamlit as st
from html import escape as html_escape

from modules.llm_backend import LLMBackend
from modules.analyzer import (
    RISK_CATEGORIES,
    build_analysis_prompt, parse_llm_risk_response,
    keyword_scan_chunk, score_findings,
    merge_categories, make_custom_category, custom_category_key,
)
from modules.ui.helpers import clean, clean_finding, badge, metric_card

# ── Quick-filter group definitions ──────────────────────────────────────────
_BUILTIN_GROUPS = {
    "🔴 Critical Errors": {
        "desc": "HIGH risk findings across all categories",
        "risk_levels": ["HIGH"],
        "match": "all",
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


def _get_custom_categories() -> dict:
    return st.session_state.get("custom_categories", {})


def _all_categories() -> dict:
    return merge_categories(_get_custom_categories())


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

    # ── Two-column layout: categories left, custom builder right ─────────────
    left_col, right_col = st.columns([3, 2])

    with left_col:
        _render_category_selector()

    with right_col:
        _render_custom_clause_builder()

    st.markdown(
        '<div class="info-strip">💡 Documents are <strong>keyword-scanned first</strong> '
        '(no API cost), then only suspicious sections are sent to the LLM for deep analysis.'
        '</div>', unsafe_allow_html=True)

    # ── Run button ───────────────────────────────────────────────────────────
    selected_cats = st.session_state.get("_selected_cats", [])
    if st.button("🚀 Run Risk Analysis", type="primary", disabled=not selected_cats):
        _run_analysis(selected_cats)

    # ── Results ──────────────────────────────────────────────────────────────
    if st.session_state.get("analysis_done") and st.session_state.get("score_summary"):
        _render_score_summary()

    if st.session_state.get("findings"):
        st.markdown("---")
        _render_findings_with_filters()


# ── Category selector ────────────────────────────────────────────────────────

def _render_category_selector():
    all_cats = _all_categories()
    custom   = _get_custom_categories()

    with st.expander("🎯 Select Risk Categories to Detect", expanded=True):
        selected = []

        # Built-in categories
        st.markdown("**Built-in Categories**")
        builtin_cols = st.columns(2)
        for i, (ck, ci) in enumerate(RISK_CATEGORIES.items()):
            with builtin_cols[i % 2]:
                if st.checkbox(ci["label"], value=True, key=f"cat_{ck}"):
                    selected.append(ck)

        # Custom categories (if any)
        if custom:
            st.markdown("**Custom Categories**")
            custom_cols = st.columns(2)
            for i, (ck, ci) in enumerate(custom.items()):
                with custom_cols[i % 2]:
                    if st.checkbox(ci["label"], value=True, key=f"cat_{ck}"):
                        selected.append(ck)

        st.session_state["_selected_cats"] = selected


# ── Custom clause builder ─────────────────────────────────────────────────────

def _render_custom_clause_builder():
    custom = _get_custom_categories()

    with st.expander(
        f"✏️ Custom Clause Categories  {'· ' + str(len(custom)) + ' added' if custom else ''}",
        expanded=bool(custom),
    ):
        st.markdown(
            "<small>Define your own risk categories with trigger keywords. "
            "They are treated identically to built-in categories during analysis.</small>",
            unsafe_allow_html=True,
        )
        st.markdown("")

        # ── Existing custom categories ────────────────────────────────────
        if custom:
            st.markdown("**Your custom categories:**")
            to_delete = []
            for ck, ci in list(custom.items()):
                c1, c2 = st.columns([5, 1])
                with c1:
                    kw_list = ", ".join(ci["keywords"])
                    st.markdown(
                        f'<div style="padding:8px 12px;border-radius:6px;'
                        f'border-left:4px solid {ci["color"]};background:rgba(0,0,0,.03);'
                        f'margin-bottom:6px;font-size:13px;">'
                        f'<strong>{html_escape(ci["label"])}</strong><br>'
                        f'<span style="font-size:11px;opacity:.7;">'
                        f'{html_escape(ci["description"])}</span><br>'
                        f'<span style="font-size:11px;color:#3B82F6;">'
                        f'Keywords: {html_escape(kw_list)}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    st.markdown("<div style='padding-top:10px'></div>",
                                unsafe_allow_html=True)
                    if st.button("🗑", key=f"del_{ck}",
                                 help=f"Remove {ci['label']}"):
                        to_delete.append(ck)

            for ck in to_delete:
                del st.session_state["custom_categories"][ck]
            if to_delete:
                st.rerun()

            st.markdown("---")

        # ── Add new category form ─────────────────────────────────────────
        st.markdown("**Add a new category:**")

        new_label = st.text_input(
            "Category name",
            placeholder="e.g. Data Privacy Risks",
            key="new_cat_label",
        )
        new_desc = st.text_input(
            "Description",
            placeholder="e.g. Clauses that expose personal data to third parties",
            key="new_cat_desc",
        )
        new_kws = st.text_area(
            "Trigger keywords (comma-separated)",
            placeholder="e.g. personal data, data sharing, third-party access, GDPR, transfer of data",
            height=80,
            key="new_cat_kws",
            help="The document will be keyword-scanned for these terms before LLM analysis.",
        )

        if st.button("➕ Add Category", type="secondary", use_container_width=True):
            label = new_label.strip()
            desc  = new_desc.strip()
            kws   = [k.strip() for k in new_kws.split(",") if k.strip()]

            if not label:
                st.error("Category name is required.")
            elif not kws:
                st.error("At least one keyword is required.")
            else:
                if "custom_categories" not in st.session_state:
                    st.session_state["custom_categories"] = {}

                key   = custom_category_key(label)
                index = len(st.session_state["custom_categories"])
                st.session_state["custom_categories"][key] = make_custom_category(
                    label=f"🔖 {label}",
                    description=desc or f"Custom category: {label}",
                    keywords=kws,
                    index=index,
                )
                st.success(f"✓ Added «{label}» with {len(kws)} keyword(s).")
                st.rerun()

        # ── Quick-add presets ─────────────────────────────────────────────
        with st.expander("💡 Quick-add presets"):
            presets = [
                ("Data Privacy", "Clauses exposing personal or sensitive data",
                 "personal data, data sharing, GDPR, data transfer, third-party access, consent"),
                ("IP Ownership", "Clauses affecting intellectual property rights",
                 "intellectual property, work for hire, assignment of rights, patent, copyright, trade secret"),
                ("Force Majeure", "Broad or one-sided force majeure provisions",
                 "force majeure, act of god, unforeseen circumstances, beyond reasonable control, epidemic"),
                ("Governing Law", "Unfavourable jurisdiction or arbitration clauses",
                 "governing law, jurisdiction, arbitration, dispute resolution, venue, applicable law"),
                ("Change of Control", "Triggers on ownership or corporate restructuring",
                 "change of control, merger, acquisition, assignment, successor, takeover"),
            ]
            for name, desc, kws in presets:
                if st.button(f"+ {name}", key=f"preset_{name}", use_container_width=True):
                    if "custom_categories" not in st.session_state:
                        st.session_state["custom_categories"] = {}
                    key   = custom_category_key(name)
                    index = len(st.session_state["custom_categories"])
                    st.session_state["custom_categories"][key] = make_custom_category(
                        label=f"🔖 {name}",
                        description=desc,
                        keywords=[k.strip() for k in kws.split(",")],
                        index=index,
                    )
                    st.success(f"✓ Added preset «{name}».")
                    st.rerun()


# ── Analysis runner ──────────────────────────────────────────────────────────

def _run_analysis(selected_cats: list):
    if "backend_kwargs" not in st.session_state:
        st.error("Configure AI backend in the sidebar first.")
        return

    custom   = _get_custom_categories()
    all_cats = merge_categories(custom)
    backend  = LLMBackend(**st.session_state.backend_kwargs)

    pre = [
        (ch, {k: v for k, v in keyword_scan_chunk(ch["text"], custom).items()
               if k in selected_cats})
        for ch in st.session_state.chunks
        if not ch.get("is_table")
    ]
    pre = [(ch, h) for ch, h in pre if h]

    if not pre:
        st.warning("No chunks matched keyword patterns. Try adding more keywords or different categories.")
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
                f"{all_cats[category]['label']}"
            )
            model_nm = getattr(backend, "active_model_name", "")
            res = backend.query(build_analysis_prompt(chunk["text"], category, custom, model_nm))
            if res.get("error"):
                st.warning(f"LLM error: {res['error']}")
            elif res.get("response"):
                f = parse_llm_risk_response(res["response"], chunk, category, custom)
                if f:
                    f["start_line"] = chunk.get("start_line", "?")
                    f["end_line"]   = chunk.get("end_line",   "?")
                    findings.append(f)
            n += 1
            prog.progress(min(n / max(total, 1), 1.0))

    prog.progress(1.0)
    stat.empty()
    st.session_state.findings      = findings
    st.session_state.score_summary = score_findings(findings, custom)
    st.session_state.analysis_done = True
    st.success(f"✓ Analysis complete — {len(findings)} findings.")


# ── Score summary strip ───────────────────────────────────────────────────────

def _render_score_summary():
    s  = st.session_state.score_summary
    ov = s.get("overall_risk", "LOW")
    m1, m2, m3, m4, m5 = st.columns(5)
    for col, val, lbl, cls in [
        (m1, ov,                 "Overall Risk", f"mc-{ov}"),
        (m2, s.get("total",  0), "Total",        "mc-blue"),
        (m3, s.get("high",   0), "High Risk",    "mc-HIGH"),
        (m4, s.get("medium", 0), "Medium Risk",  "mc-MEDIUM"),
        (m5, s.get("low",    0), "Low Risk",      "mc-LOW"),
    ]:
        with col:
            st.markdown(metric_card(val, lbl, cls), unsafe_allow_html=True)
    st.markdown("")


# ── Findings + filters ────────────────────────────────────────────────────────

def _render_findings_with_filters():
    findings  = st.session_state.findings
    custom    = _get_custom_categories()
    all_cats  = merge_categories(custom)

    # Build quick-filter groups dynamically (custom cats get their own "Custom" group)
    filter_groups = dict(_BUILTIN_GROUPS)
    if custom:
        filter_groups["🔖 Custom Categories"] = {
            "desc": "Findings from your custom-defined categories",
            "risk_levels": ["HIGH", "MEDIUM", "LOW"],
            "categories": list(custom.keys()),
        }

    if "analysis_quick_filter" not in st.session_state:
        st.session_state.analysis_quick_filter = "All Findings"

    # Quick-filter buttons
    st.markdown("**Quick Filters:**")
    options   = ["All Findings"] + list(filter_groups.keys())
    btn_cols  = st.columns(len(options))
    for i, opt in enumerate(options):
        with btn_cols[i]:
            is_active = st.session_state.analysis_quick_filter == opt
            if st.button(opt, key=f"qf_{i}",
                         type="primary" if is_active else "secondary",
                         use_container_width=True):
                st.session_state.analysis_quick_filter = opt
                st.rerun()

    active = st.session_state.analysis_quick_filter
    if active != "All Findings" and active in filter_groups:
        st.caption(f"ℹ {filter_groups[active]['desc']}")
    st.markdown("")

    # Advanced filters
    with st.expander("🔧 Advanced Filters"):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            f_risk = st.multiselect("Risk Level", ["HIGH", "MEDIUM", "LOW"],
                                     default=["HIGH", "MEDIUM", "LOW"])
        with fc2:
            f_cat = st.multiselect(
                "Category", list(all_cats.keys()),
                format_func=lambda k: all_cats[k]["label"],
                default=list(all_cats.keys()),
            )
        with fc3:
            all_docs = list({f["filename"] for f in findings})
            f_doc = st.multiselect("Document", all_docs, default=all_docs)

    # Apply quick filter
    if active == "All Findings":
        qf_risk = ["HIGH", "MEDIUM", "LOW"]
        qf_cats = list(all_cats.keys())
    else:
        g = filter_groups.get(active, {})
        qf_risk = g.get("risk_levels", ["HIGH", "MEDIUM", "LOW"])
        qf_cats = g.get("categories", list(all_cats.keys())) \
                  if g.get("match") != "all" else list(all_cats.keys())

    final_risk = [r for r in f_risk if r in qf_risk]
    final_cats = [c for c in f_cat if c in qf_cats]

    filtered = [
        f for f in findings
        if f.get("risk_level") in final_risk
        and f.get("category")  in final_cats
        and f.get("filename")  in f_doc
    ]

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

    for finding in filtered:
        _render_finding_card(finding)


# ── Finding card ─────────────────────────────────────────────────────────────



def _render_finding_card(finding: dict):
    risk   = finding.get("risk_level", "LOW")
    cat    = clean_finding(finding.get("category_label", ""))
    fname  = finding.get("filename", "")
    sl, el = finding.get("start_line", "?"), finding.get("end_line", "?")
    txt    = clean_finding(finding.get("finding", ""))
    prob   = clean_finding(finding.get("problematic_language", ""))
    interp = clean_finding(finding.get("interpretation", ""))
    qs     = [clean_finding(q) for q in finding.get("follow_up_questions", []) if q]
    is_custom = finding.get("is_custom", False)

    color = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#22C55E"}.get(risk, "#94A3B8")

    # ── Card container ───────────────────────────────────────────────────────
    with st.container():
        st.markdown(
            f'<div style="border-left:4px solid {color};padding:14px 16px;'
            f'margin-bottom:12px;border-radius:0 8px 8px 0;'
            f'background:rgba(0,0,0,.02);">',
            unsafe_allow_html=True,
        )

        # Header row — pure Streamlit widgets, no custom class spans
        h1, h2, h3, h4 = st.columns([1.2, 2.5, 2, 1])
        with h1:
            label = {"HIGH": "🔴 HIGH", "MEDIUM": "🟡 MEDIUM", "LOW": "🟢 LOW"}.get(risk, risk)
            st.markdown(f"**{label}**")
        with h2:
            st.markdown(f"**{cat}**" + (" `CUSTOM`" if is_custom else ""))
        with h3:
            st.caption(f"📄 {fname}")
        with h4:
            st.caption(f"Lines {sl}–{el}")

        st.divider()

        # Finding text
        if txt:
            st.markdown(txt)

        # Flagged language in a code block — no HTML, can never echo back
        if prob and prob.upper() not in ("N/A", ""):
            st.markdown("**Flagged language:**")
            st.code(prob, language=None)

        # Interpretation
        if interp:
            st.markdown(f"*{interp}*")

        # Follow-up questions
        if qs:
            st.markdown("**Legal Team Follow-up Questions:**")
            for q in qs:
                st.markdown(f"- {q}")

        st.markdown('</div>', unsafe_allow_html=True)