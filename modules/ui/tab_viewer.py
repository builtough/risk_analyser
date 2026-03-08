"""
Document Viewer Tab — Smart multi-format viewer.

Features:
  • PDF       — page-by-page navigation with per-page text + inline tables
  • DOCX      — section-by-section with inline table grids
  • Excel/CSV — interactive sheet tabs with full grid + search
  • Plain text — full line-numbered view with risk highlights
  • ALL formats: keyword highlight, risk findings sidebar, download
"""
import io
import streamlit as st
import pandas as pd
from html import escape as html_escape

from modules.ui.helpers import (clean, clean_finding, highlight,
                                 metric_card, build_finding_line_map)
from modules.table_extractor import table_to_text


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def render_tab_viewer():
    st.markdown(
        '<div class="da-sec">📄 Document Viewer · Smart Multi-Format Display</div>',
        unsafe_allow_html=True,
    )

    docs = [d for d in st.session_state.get("documents", []) if not d.get("error")]
    if not docs:
        st.markdown(
            '<div class="empty-state"><div class="es-icon">📄</div>'
            '<h3>No Documents Loaded</h3>'
            '<p>Upload documents via the sidebar to view their contents here.</p></div>',
            unsafe_allow_html=True,
        )
        return

    # ── Document selector ─────────────────────────────────────────────────────
    doc_names    = [d["filename"] for d in docs]
    selected_doc = st.selectbox("Select document", doc_names, label_visibility="collapsed")
    doc = next((d for d in docs if d["filename"] == selected_doc), None)
    if not doc:
        return

    file_ext    = doc.get("type", "").lower()
    raw         = doc.get("raw_text", "")
    rich_blocks = doc.get("rich_blocks", [])
    pages       = doc.get("pages", [])

    # ── Stats strip ───────────────────────────────────────────────────────────
    n_tables = sum(1 for b in rich_blocks if b.get("type") == "table")
    n_pages  = len(pages) if pages else (len(raw.split("\n")) // 50 + 1)
    vs1, vs2, vs3, vs4 = st.columns(4)
    for col, val, lbl in [
        (vs1, file_ext.upper() or "TXT",  "Format"),
        (vs2, f"{len(raw.split()):,}",    "Words"),
        (vs3, str(n_pages),               "Pages / Sections"),
        (vs4, str(n_tables) or "—",       "Tables"),
    ]:
        with col:
            st.markdown(metric_card(val, lbl), unsafe_allow_html=True)
    st.markdown("")

    # ── Findings for this document ────────────────────────────────────────────
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
            f'🔍 **{len(doc_findings)} finding(s)** — '
            f'<span class="badge badge-HIGH">{h} HIGH</span> '
            f'<span class="badge badge-MEDIUM">{m} MED</span> '
            f'<span class="badge badge-LOW">{lo} LOW</span>',
            unsafe_allow_html=True,
        )

    # ── Global keyword search bar ─────────────────────────────────────────────
    sv_kw = st.text_input(
        "🔍 Highlight within document",
        placeholder="Search within document…",
        label_visibility="collapsed",
        key="viewer_search_global",
    )

    st.markdown("---")

    # ── Route to format-specific renderer ────────────────────────────────────
    if file_ext in ("xlsx", "xls", "csv"):
        _render_excel_viewer(rich_blocks, selected_doc, sv_kw)

    elif file_ext == "pdf":
        _render_pdf_viewer(doc, sv_kw, line_map, doc_findings, has_findings)

    elif file_ext in ("docx", "doc"):
        _render_docx_viewer(doc, sv_kw, line_map, doc_findings, has_findings)

    else:
        # Plain text / unknown format
        _render_plain_viewer(raw, sv_kw, line_map, doc_findings, has_findings)

    # ── Download extracted text ───────────────────────────────────────────────
    st.markdown("---")
    st.download_button(
        f"⬇ Download extracted text — {selected_doc}",
        data=raw,
        file_name=f"{selected_doc}_extracted.txt",
        mime="text/plain",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Excel / CSV viewer — interactive sheet tabs
# ═══════════════════════════════════════════════════════════════════════════════

def _render_excel_viewer(rich_blocks: list, filename: str, sv_kw: str = ""):
    """Show each sheet as a tab with full interactive grid."""
    if not rich_blocks:
        st.info("No sheets found in this file.")
        return

    if len(rich_blocks) == 1:
        block = rich_blocks[0]
        label = block.get("sheet", block.get("label", "Sheet 1"))
        st.markdown(f"**📊 {html_escape(label)}**")
        _render_df_grid(block["content"], f"{filename}_0", sv_kw)
    else:
        tab_labels = [b.get("sheet", b.get("label", f"Sheet {i+1}"))
                      for i, b in enumerate(rich_blocks)]
        tabs = st.tabs(tab_labels)
        for i, (tab, block) in enumerate(zip(tabs, rich_blocks)):
            with tab:
                _render_df_grid(block["content"], f"{filename}_{i}", sv_kw)


def _render_df_grid(df: pd.DataFrame, key_prefix: str, filter_str: str = ""):
    """Interactive dataframe grid with search and CSV download."""
    c1, c2 = st.columns([4, 1])
    with c1:
        search = st.text_input(
            "Filter rows", placeholder="Filter rows…",
            label_visibility="collapsed",
            key=f"{key_prefix}_search",
            value=filter_str,
        )
    with c2:
        buf = io.BytesIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇ CSV", data=buf.getvalue(),
            file_name=f"{key_prefix}.csv", mime="text/csv",
            key=f"{key_prefix}_dl", use_container_width=True,
        )

    display_df = df.copy()
    if search.strip():
        mask = display_df.astype(str).apply(
            lambda col: col.str.contains(search, case=False, na=False)
        ).any(axis=1)
        display_df = display_df[mask]
        st.caption(f"{len(display_df)} of {len(df)} rows match")

    st.dataframe(
        display_df, use_container_width=True, hide_index=True,
        height=min(800, max(200, (len(display_df) + 1) * 35 + 40)),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PDF viewer — all pages shown, page selector + navigation
# ═══════════════════════════════════════════════════════════════════════════════

def _render_pdf_viewer(doc: dict, sv_kw: str, line_map: dict,
                        doc_findings: list, has_findings: bool):
    """
    Show ALL pages of a PDF. Each page has its own expandable section.
    Pages that contain flagged findings are highlighted in the page list.
    """
    pages       = doc.get("pages", [])
    rich_blocks = doc.get("rich_blocks", [])

    # Build set of flagged page numbers from findings
    flagged_pages = set()
    if doc_findings:
        # Findings use line numbers; estimate page from line position
        lines_all = doc.get("raw_text", "").split("\n")
        total_lines = len(lines_all)
        for f in doc_findings:
            sl = f.get("start_line", 0)
            if isinstance(sl, int) and total_lines > 0:
                # Estimate page proportionally (rough heuristic)
                pct     = sl / max(total_lines, 1)
                est_pg  = max(1, int(pct * len(pages)) + 1)
                flagged_pages.add(est_pg)

    if not pages:
        st.warning("No page data available — showing raw text view.")
        _render_plain_viewer(doc.get("raw_text", ""), sv_kw, line_map, doc_findings, has_findings)
        return

    kws = [sv_kw.strip()] if sv_kw.strip() else []

    # ── View mode selection ────────────────────────────────────────────────
    view_mode_options = ["📑 All Pages", "🔢 Single Page", "📋 Full Text View"]
    # view_mode_default = 1   # default to single-page mode
    view_mode = st.radio("View mode", view_mode_options, horizontal=True,
                          label_visibility="collapsed", key="pdf_view_mode")

    if view_mode == "📑 All Pages":
        _render_pdf_all_pages(pages, rich_blocks, kws, line_map, flagged_pages, has_findings, doc_findings)

    elif view_mode == "🔢 Single Page":
        _render_pdf_single_page(pages, rich_blocks, kws, line_map, flagged_pages, has_findings, doc_findings)

    else:
        # Full concatenated text view
        all_lines = doc.get("raw_text", "").split("\n")
        if has_findings:
            mc, sc = st.columns([3, 1])
            with mc:
                _render_full_document(all_lines, sv_kw, line_map)
            with sc:
                _render_findings_panel(doc_findings)
        else:
            _render_full_document(all_lines, sv_kw, line_map)


def _render_pdf_all_pages(pages, rich_blocks, kws, line_map, flagged_pages,
                           has_findings, doc_findings):
    """Render all PDF pages as expandable sections."""
    st.caption(f"Showing all {len(pages)} page(s). Pages with findings are marked ⚠.")

    # Separate tables by page for inline display
    tables_by_page = {}
    for b in rich_blocks:
        if b.get("type") == "table":
            pno = b.get("page", 0)
            tables_by_page.setdefault(pno, []).append(b)

    for pg in pages:
        pno  = pg.get("page_number", "?")
        text = pg.get("text", "").strip()
        n_words = len(text.split())
        flag = " ⚠" if pno in flagged_pages else ""
        label = f"Page {pno}{flag}  ·  {n_words} words"

        # Auto-expand flagged pages
        expanded = pno in flagged_pages or len(pages) <= 3
        with st.expander(label, expanded=expanded):
            if not text:
                st.caption("(empty page)")
            else:
                body = highlight(text, kws) if kws else html_escape(text)
                st.markdown(
                    f'<div class="doc-viewer" style="max-height:40vh">{body}</div>',
                    unsafe_allow_html=True,
                )
            # Inline tables for this page
            for tbl in tables_by_page.get(pno, []):
                df = tbl.get("content")
                if df is not None and not df.empty:
                    st.markdown(
                        f'<div class="tbl-marker-start">📋 TABLE · {html_escape(tbl.get("label",""))}</div>',
                        unsafe_allow_html=True,
                    )
                    _render_df_grid(df, f"pdf_pg{pno}_{tbl.get('label','')}")
                    st.markdown('<div class="tbl-marker-end">━━ TABLE END ━━</div>',
                                unsafe_allow_html=True)

    # Findings panel below all pages
    if has_findings:
        st.markdown("---")
        with st.expander("📌 Findings for this document", expanded=True):
            _render_findings_panel(doc_findings)


def _render_pdf_single_page(pages, rich_blocks, kws, line_map, flagged_pages,
                              has_findings, doc_findings):
    """Render one page at a time with prev/next navigation."""
    if not pages:
        return

    page_nums = [pg.get("page_number", i+1) for i, pg in enumerate(pages)]

    # Use a separate state key for the index so Prev/Next can mutate it
    # without conflicting with the selectbox widget key.
    if "pdf_page_idx" not in st.session_state:
        st.session_state.pdf_page_idx = 0
    # Clamp in case document changed
    st.session_state.pdf_page_idx = max(0, min(st.session_state.pdf_page_idx, len(pages) - 1))

    # Prev / Next buttons — update the index state BEFORE the selectbox renders
    nav1, nav2, nav3 = st.columns([1, 6, 1])
    with nav1:
        if st.button("◀ Prev", disabled=st.session_state.pdf_page_idx == 0):
            st.session_state.pdf_page_idx -= 1
            st.rerun()
    with nav3:
        if st.button("Next ▶", disabled=st.session_state.pdf_page_idx >= len(pages) - 1):
            st.session_state.pdf_page_idx += 1
            st.rerun()

    # Selectbox syncs FROM the index state via index= parameter (not key mutation)
    selected_idx = st.selectbox(
        "Go to page",
        range(len(pages)),
        index=st.session_state.pdf_page_idx,
        format_func=lambda i: f"Page {page_nums[i]}"
                              + (" ⚠" if page_nums[i] in flagged_pages else ""),
        key="pdf_page_sel",
    )
    # If user picked a page via the dropdown, sync state
    if selected_idx != st.session_state.pdf_page_idx:
        st.session_state.pdf_page_idx = selected_idx
        st.rerun()

    pg   = pages[selected_idx]
    pno  = pg.get("page_number", selected_idx + 1)
    text = pg.get("text", "").strip()

    # Tables for this page
    tables_for_page = [b for b in rich_blocks
                       if b.get("type") == "table" and b.get("page") == pno]

    if has_findings:
        mc, sc = st.columns([3, 1])
    else:
        mc = st.container()
        sc = None

    with mc:
        if text:
            body = highlight(text, kws) if kws else html_escape(text)
            st.markdown(f'<div class="doc-viewer">{body}</div>', unsafe_allow_html=True)
        else:
            st.caption("(empty page)")

        for tbl in tables_for_page:
            df = tbl.get("content")
            if df is not None and not df.empty:
                st.markdown(
                    f'<div class="tbl-marker-start">📋 TABLE · {html_escape(tbl.get("label",""))}</div>',
                    unsafe_allow_html=True,
                )
                _render_df_grid(df, f"pdf_sp_{pno}_{tbl.get('label','')}")

    if sc:
        with sc:
            _render_findings_panel(doc_findings)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCX viewer — section/paragraph blocks with inline table grids
# ═══════════════════════════════════════════════════════════════════════════════

def _render_docx_viewer(doc: dict, sv_kw: str, line_map: dict,
                         doc_findings: list, has_findings: bool):
    """
    DOCX: Walk rich_blocks in document order.
    Text blocks → line-numbered viewer with risk highlights.
    Table blocks → interactive grid with start/end markers.
    """
    rich_blocks = doc.get("rich_blocks", [])
    if not rich_blocks:
        _render_plain_viewer(doc.get("raw_text", ""), sv_kw, line_map, doc_findings, has_findings)
        return

    kws    = [sv_kw.strip()] if sv_kw.strip() else []
    n_text = sum(1 for b in rich_blocks if b.get("type") == "text")
    n_tbl  = sum(1 for b in rich_blocks if b.get("type") == "table")
    st.caption(f"{n_text} text section(s) · {n_tbl} table(s) — shown in document order")

    # View mode
    view_mode = st.radio(
        "View mode",
        ["📄 Document Order (Inline Tables)", "📑 Text Only", "📋 Tables Only"],
        horizontal=True, label_visibility="collapsed", key="docx_view_mode",
    )

    if view_mode == "📑 Text Only":
        all_lines = doc.get("raw_text", "").split("\n")
        if has_findings:
            mc, sc = st.columns([3, 1])
            with mc:
                _render_full_document(all_lines, sv_kw, line_map)
            with sc:
                _render_findings_panel(doc_findings)
        else:
            _render_full_document(all_lines, sv_kw, line_map)
        return

    if view_mode == "📋 Tables Only":
        tbl_blocks = [b for b in rich_blocks if b.get("type") == "table"]
        if not tbl_blocks:
            st.info("No tables found in this document.")
        for i, b in enumerate(tbl_blocks):
            label = b.get("label", f"Table {i+1}")
            with st.expander(f"📋 {label}", expanded=True):
                _render_df_grid(b["content"], f"docx_tbl_{i}", sv_kw)
        return

    # ── Document Order — inline tables ──────────────────────────────────────
    line_cursor = 1
    if has_findings:
        mc, sc = st.columns([3, 1])
    else:
        mc = st.container()
        sc = None

    with mc:
        for block in rich_blocks:
            btype = block.get("type")
            if btype == "text":
                text  = block.get("content", "").strip()
                if not text:
                    continue
                lines = text.split("\n")

                rendered = []
                for line in lines:
                    safe   = highlight(line, kws) if kws else html_escape(line)
                    info   = line_map.get(line_cursor)
                    if info:
                        level     = info["level"]
                        cats      = html_escape(", ".join(info["labels"]))
                        row_class = f"dv-line dv-hl-{level}"
                        title     = f' title="{cats}"'
                    else:
                        row_class = "dv-line"
                        title     = ""
                    ln_html = f'<span class="dv-ln">{line_cursor}</span>'
                    rendered.append(f'<span class="{row_class}"{title}>{ln_html}{safe}</span>')
                    line_cursor += 1

                st.markdown(
                    f'<div class="doc-viewer" style="max-height:50vh">{"".join(rendered)}</div>',
                    unsafe_allow_html=True,
                )

            elif btype == "table":
                df    = block.get("content")
                label = block.get("label", "Table")
                if df is not None and not df.empty:
                    st.markdown(
                        f'<div class="tbl-marker-start">📋 {html_escape(label)}</div>',
                        unsafe_allow_html=True,
                    )
                    _render_df_grid(df, f"docx_inline_{line_cursor}", sv_kw)
                    st.markdown('<div class="tbl-marker-end">━━ TABLE END ━━</div>',
                                unsafe_allow_html=True)
                    line_cursor += 1

    if sc:
        with sc:
            _render_findings_panel(doc_findings)

    _render_risk_legend(line_map)


# ═══════════════════════════════════════════════════════════════════════════════
# Plain text viewer
# ═══════════════════════════════════════════════════════════════════════════════

def _render_plain_viewer(raw: str, sv_kw: str, line_map: dict,
                          doc_findings: list, has_findings: bool):
    """Full line-numbered text viewer with risk highlights and findings panel."""
    all_lines = raw.split("\n")

    if has_findings:
        mc, sc = st.columns([3, 1])
        with mc:
            _render_full_document(all_lines, sv_kw, line_map)
        with sc:
            _render_findings_panel(doc_findings)
    else:
        _render_full_document(all_lines, sv_kw, line_map)


# ═══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _render_full_document(lines: list, sv_kw: str, line_map: dict):
    """Render all lines with line numbers and optional risk highlights."""
    kws           = [sv_kw.strip()] if sv_kw.strip() else []
    rendered_lines = []

    for i, line in enumerate(lines, start=1):
        safe      = highlight(line, kws) if kws else html_escape(line)
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
            f'<span class="{row_class}"{title_attr}>{ln_html}{safe}</span>'
        )

    st.caption(
        f"{len(lines):,} lines"
        + (f" · 🔦 {len(line_map)} flagged" if line_map else "")
    )
    st.markdown(
        f'<div class="doc-viewer">{"".join(rendered_lines)}</div>',
        unsafe_allow_html=True,
    )
    _render_risk_legend(line_map)


def _render_risk_legend(line_map: dict):
    if not line_map:
        return
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
    """Compact findings list for the side panel."""
    st.markdown("**Findings**")
    if not doc_findings:
        st.caption("No findings for this document.")
        return

    sorted_findings = sorted(
        doc_findings,
        key=lambda f: f.get("start_line") if isinstance(f.get("start_line"), int) else 9999,
    )
    for f in sorted_findings:
        risk     = f.get("risk_level", "LOW")
        cat      = clean(f.get("category_label", ""))
        sl, el   = f.get("start_line", "?"), f.get("end_line", "?")
        txt      = clean_finding(f.get("finding", ""))
        short    = txt[:110] + ("…" if len(txt) > 110 else "")
        color    = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#22C55E"}.get(risk, "#94A3B8")
        st.markdown(
            f'<div style="border-left:3px solid {color};padding:8px 10px;'
            f'margin-bottom:8px;border-radius:0 6px 6px 0;background:rgba(0,0,0,.03);">'
            f'<div style="font-weight:600;color:{color};font-size:11px;margin-bottom:2px;">'
            f'{risk} · Lines {sl}–{el}</div>'
            f'<div style="font-size:11px;opacity:.65;margin-bottom:3px;">{cat}</div>'
            f'<div style="font-size:12px;line-height:1.5;">{short}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )