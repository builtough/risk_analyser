"""
Document Viewer Tab
- Always renders the complete document with line numbers
- Risk findings highlighted inline after analysis (color-coded by level)
- Side panel lists all findings for the selected document
- Optional search-within-document highlight
- Page/Section secondary view for multi-page PDFs
"""
import streamlit as st
from html import escape as html_escape

from modules.ui.helpers import clean, clean_finding, highlight, metric_card, build_finding_line_map


def render_tab_viewer():
    st.markdown('<div class="da-sec">📄 Document Viewer · Full Text with Risk Highlights</div>',
                unsafe_allow_html=True)

    docs = [d for d in st.session_state.get("documents", []) if not d.get("error")]
    if not docs:
        st.markdown(
            '<div class="empty-state"><div class="es-icon">📄</div>'
            '<h3>No Documents Loaded</h3>'
            '<p>Upload documents via the sidebar to view their contents here.</p></div>',
            unsafe_allow_html=True)
        return

    # ── Document selector ────────────────────────────────────────────────────
    doc_names    = [d["filename"] for d in docs]
    selected_doc = st.selectbox("Select document", doc_names, label_visibility="visible")
    doc = next((d for d in docs if d["filename"] == selected_doc), None)
    if not doc:
        return

    raw   = doc.get("raw_text", "")
    pages = doc.get("pages", [])
    lines = raw.split("\n")

    # ── Stats strip ──────────────────────────────────────────────────────────
    vs1, vs2, vs3, vs4 = st.columns(4)
    for col, val, lbl in [
        (vs1, doc.get("type", "").upper(), "Format"),
        (vs2, f"{len(raw.split()):,}",     "Words"),
        (vs3, f"{len(raw):,}",             "Characters"),
        (vs4, f"{len(lines):,}",           "Lines"),
    ]:
        with col:
            st.markdown(metric_card(val, lbl), unsafe_allow_html=True)
    st.markdown("")

    # ── Findings for this document ───────────────────────────────────────────
    doc_findings = [
        f for f in st.session_state.get("findings", [])
        if f.get("filename") == selected_doc
    ]
    line_map     = build_finding_line_map(doc_findings)
    has_findings = bool(line_map)

    if has_findings:
        h  = sum(1 for v in line_map.values() if v["level"] == "HIGH")
        m  = sum(1 for v in line_map.values() if v["level"] == "MEDIUM")
        lo = sum(1 for v in line_map.values() if v["level"] == "LOW")
        st.markdown(
            f'🔍 **{len(doc_findings)} finding(s)** flagged in this document — '
            f'<span class="badge badge-HIGH">{h} HIGH lines</span> '
            f'<span class="badge badge-MEDIUM">{m} MED lines</span> '
            f'<span class="badge badge-LOW">{lo} LOW lines</span>',
            unsafe_allow_html=True,
        )

    # ── Controls ─────────────────────────────────────────────────────────────
    ctrl1, ctrl2 = st.columns([3, 1])
    with ctrl1:
        sv_kw = st.text_input("🔍 Highlight within document",
                               placeholder="e.g. indemnify, renewal…",
                               label_visibility="collapsed")
    with ctrl2:
        if has_findings and doc_findings:
            first_line = min(
                (f.get("start_line") for f in doc_findings
                 if isinstance(f.get("start_line"), int)),
                default=1,
            )
            if st.button("⚑ Jump to first finding", use_container_width=True):
                st.session_state["viewer_anchor"] = f"line-{first_line}"
                st.rerun()

    st.markdown("---")

    # ── Main viewer / findings panel layout ──────────────────────────────────
    if has_findings:
        main_col, side_col = st.columns([3, 1])
    else:
        main_col = st.container()
        side_col = None

    with main_col:
        _render_full_document(lines, sv_kw, line_map)

    if side_col:
        with side_col:
            _render_findings_panel(doc_findings)

    # ── Secondary: Page/Section view for PDFs ────────────────────────────────
    if pages and len(pages) > 1:
        with st.expander(f"📑 Page / Section View ({len(pages)} sections)"):
            for pg in pages:
                num  = pg.get("page_number", "?")
                text = pg.get("text", "").strip()
                if not text:
                    continue
                body  = highlight(text, [sv_kw.strip()]) if sv_kw.strip() else html_escape(text)
                label = f"{'Page' if isinstance(num, int) else 'Sheet'} {num} — {len(text.split())} words"
                with st.expander(label):
                    st.markdown(f'<div class="doc-viewer">{body}</div>',
                                unsafe_allow_html=True)

    # ── Download ─────────────────────────────────────────────────────────────
    st.download_button(
        f"⬇ Download extracted text — {selected_doc}",
        data=raw,
        file_name=f"{selected_doc}_extracted.txt",
        mime="text/plain",
    )


# ── Internal renderers ────────────────────────────────────────────────────────

def _render_full_document(lines: list, sv_kw: str, line_map: dict):
    """Render every line of the document with line numbers and risk highlights."""
    kws = [sv_kw.strip()] if sv_kw.strip() else []
    rendered_lines = []

    for i, line in enumerate(lines, start=1):
        safe_text = highlight(line, kws) if kws else html_escape(line)

        line_info = line_map.get(i)
        if line_info:
            level      = line_info["level"]
            cat_labels = html_escape(", ".join(line_info["labels"]))
            row_class  = f"dv-line dv-hl-{level}"
            title_attr = f' title="{cat_labels}"'
        else:
            row_class  = "dv-line"
            title_attr = ""

        ln_html = f'<span class="dv-ln">{i}</span>'
        rendered_lines.append(
            f'<span class="{row_class}"{title_attr}>{ln_html}{safe_text}</span>'
        )

    body = "\n".join(rendered_lines)
    st.caption(f"{len(lines):,} lines total"
               + (f" · 🔦 {len(line_map)} flagged line(s)" if line_map else ""))
    st.markdown(f'<div class="doc-viewer">{body}</div>', unsafe_allow_html=True)

    if line_map:
        st.markdown(
            '**Legend:** '
            '<span style="background:rgba(239,68,68,.2);padding:1px 8px;border-radius:3px;'
            'border-left:3px solid #EF4444;font-size:12px">HIGH</span> &nbsp;'
            '<span style="background:rgba(245,158,11,.2);padding:1px 8px;border-radius:3px;'
            'border-left:3px solid #F59E0B;font-size:12px">MEDIUM</span> &nbsp;'
            '<span style="background:rgba(34,197,94,.15);padding:1px 8px;border-radius:3px;'
            'border-left:3px solid #22C55E;font-size:12px">LOW</span>',
            unsafe_allow_html=True,
        )


def _render_findings_panel(doc_findings: list):
    """Side panel listing all findings for this document."""
    st.markdown("**Findings**")
    if not doc_findings:
        st.caption("No findings for this document.")
        return

    # Sort by start line
    sorted_findings = sorted(
        doc_findings,
        key=lambda f: f.get("start_line") if isinstance(f.get("start_line"), int) else 9999,
    )

    for f in sorted_findings:
        risk   = f.get("risk_level", "LOW")
        cat    = clean(f.get("category_label", ""))
        sl, el = f.get("start_line", "?"), f.get("end_line", "?")
        txt    = clean_finding(f.get("finding", ""))
        short  = txt[:110] + ("…" if len(txt) > 110 else "")
        color  = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#22C55E"}.get(risk, "#94A3B8")

        st.markdown(
            f'<div style="border-left:3px solid {color};padding:8px 10px;'
            f'margin-bottom:8px;border-radius:0 6px 6px 0;background:rgba(0,0,0,.03);">'
            f'<div style="font-weight:600;color:{color};font-size:11px;margin-bottom:2px;">'
            f'{risk} · Lines {sl}–{el}</div>'
            f'<div style="font-size:11px;opacity:.65;margin-bottom:3px;">' + cat + '</div>'
            f'<div style="font-size:12px;line-height:1.5;">' + short + '</div>'
            f'</div>',
            unsafe_allow_html=True,
        )