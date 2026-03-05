"""
Document Viewer Tab
- Full document with line numbers and risk highlights for text-based files
- Excel: each sheet rendered as an interactive grid with table markers
- DOCX/PPTX/PDF: tables rendered as inline grids exactly where they appear in the document,
  with clear start/end markers
"""
import io
import streamlit as st
import pandas as pd
from html import escape as html_escape

from modules.ui.helpers import clean, clean_finding, highlight, metric_card, build_finding_line_map


def render_tab_viewer():
    st.markdown(
        '<div class="da-sec">📄 Document Viewer · Full Content with Inline Tables</div>',
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
    selected_doc = st.selectbox("Select document", doc_names)
    doc = next((d for d in docs if d["filename"] == selected_doc), None)
    if not doc:
        return

    file_ext    = doc.get("type", "").lower()
    raw         = doc.get("raw_text", "")
    rich_blocks = doc.get("rich_blocks", [])

    # ── Stats strip ───────────────────────────────────────────────────────────
    lines = raw.split("\n")
    n_tables = sum(1 for b in rich_blocks if b.get("type") == "table")
    vs1, vs2, vs3, vs4 = st.columns(4)
    for col, val, lbl in [
        (vs1, file_ext.upper(),           "Format"),
        (vs2, f"{len(raw.split()):,}",    "Words"),
        (vs3, f"{len(lines):,}",          "Lines"),
        (vs4, str(n_tables) if n_tables else "—", "Tables"),
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

    st.markdown("---")

    # ── Route to the right renderer ───────────────────────────────────────────
    if file_ext in ("xlsx", "xls"):
        _render_excel(rich_blocks, selected_doc)
    elif rich_blocks:
        # Use rich renderer for any document with tables (PDF, DOCX, etc.)
        if has_findings:
            main_col, side_col = st.columns([3, 1])
        else:
            main_col = st.container()
            side_col = None

        sv_kw = st.text_input(
            "🔍 Highlight within document",
            placeholder="e.g. indemnify, renewal…",
            label_visibility="collapsed",
            key="viewer_search",
        )

        with main_col:
            _render_rich_document(rich_blocks, sv_kw, line_map, lines)
        if side_col:
            with side_col:
                _render_findings_panel(doc_findings)
    else:
        # Fallback to plain text viewer (for documents without rich_blocks)
        sv_kw = st.text_input(
            "🔍 Highlight within document",
            placeholder="e.g. indemnify, renewal…",
            label_visibility="collapsed",
            key="viewer_search_text",
        )

        ctrl_col, _ = st.columns([3, 1])
        with ctrl_col:
            if has_findings and doc_findings:
                first_line = min(
                    (f.get("start_line") for f in doc_findings
                     if isinstance(f.get("start_line"), int)),
                    default=1,
                )
                if st.button("⚑ Jump to first finding", use_container_width=False):
                    st.session_state["viewer_anchor"] = f"line-{first_line}"
                    st.rerun()

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

        # Page/Section view for PDFs (fallback)
        pages = doc.get("pages", [])
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
                        st.markdown(f'<div class="doc-viewer">{body}</div>', unsafe_allow_html=True)

    # ── Download ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.download_button(
        f"⬇ Download extracted text — {selected_doc}",
        data=raw,
        file_name=f"{selected_doc}_extracted.txt",
        mime="text/plain",
    )


# ── Excel renderer ────────────────────────────────────────────────────────────

def _render_excel(rich_blocks: list, filename: str):
    """Render each Excel sheet as a full interactive grid with table markers."""
    if not rich_blocks:
        st.info("No sheets found in this file.")
        return

    if len(rich_blocks) == 1:
        block = rich_blocks[0]
        df    = block["content"]
        sheet_name = block.get('sheet', block.get('label', ''))
        _render_table_with_markers(df, sheet_name, key_prefix=f"excel_{filename}_0")
    else:
        tabs = st.tabs([b.get("sheet", b.get("label", f"Sheet {i+1}"))
                        for i, b in enumerate(rich_blocks)])
        for i, (tab, block) in enumerate(zip(tabs, rich_blocks)):
            with tab:
                df = block["content"]
                sheet_name = block.get('sheet', block.get('label', f"Sheet {i+1}"))
                _render_table_with_markers(df, sheet_name, key_prefix=f"excel_{filename}_{i}")


def _render_table_with_markers(df: pd.DataFrame, label: str, key_prefix: str):
    """Display a table with start/end markers and an interactive grid."""
    # Start marker
    st.markdown(
        f'<div style="background:rgba(59,130,246,0.1); border-left:4px solid #3B82F6; '
        f'padding:6px 12px; margin:12px 0 4px; border-radius:0 4px 4px 0;">'
        f'📋 <strong>TABLE START</strong> · {html_escape(label)}</div>',
        unsafe_allow_html=True
    )

    # The table itself
    _render_df_grid(df, key_prefix)

    # End marker
    st.markdown(
        f'<div style="background:rgba(0,0,0,0.03); border-left:4px solid #94A3B8; '
        f'padding:4px 12px; margin:4px 0 16px; border-radius:0 4px 4px 0; '
        f'font-size:11px; color:#64748B;">'
        f'━━━ TABLE END ━━━</div>',
        unsafe_allow_html=True
    )


def _render_df_grid(df: pd.DataFrame, key_prefix: str = ""):
    """Render a DataFrame as a full interactive grid with search and download."""
    c1, c2 = st.columns([4, 1])
    with c1:
        search = st.text_input("Filter rows", placeholder="Filter rows…",
                               label_visibility="collapsed",
                               key=f"{key_prefix}_search")
    with c2:
        buf = io.BytesIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button("⬇ CSV", data=buf.getvalue(),
                           file_name=f"{key_prefix}.csv",
                           mime="text/csv",
                           key=f"{key_prefix}_dl",
                           use_container_width=True)

    display_df = df.copy()
    if search.strip():
        mask = display_df.astype(str).apply(
            lambda col: col.str.contains(search, case=False, na=False)
        ).any(axis=1)
        display_df = display_df[mask]
        st.caption(f"{len(display_df)} of {len(df)} rows match")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=min(800, max(200, (len(display_df) + 1) * 35 + 40)),
    )


# ── Rich document renderer (for PDF, DOCX, etc. with rich_blocks) ─────────────

def _render_rich_document(rich_blocks: list, sv_kw: str, line_map: dict, all_lines: list):
    """
    Walk rich_blocks in order. Text blocks render as highlighted line viewer.
    Table blocks render as full interactive grids with clear start/end markers.
    """
    kws           = [sv_kw.strip()] if sv_kw.strip() else []
    line_cursor   = 1   # track absolute line number across text blocks
    table_counter = 0

    for block in rich_blocks:
        btype = block.get("type")

        if btype == "text":
            text  = block.get("content", "")
            lines = text.split("\n")

            rendered = []
            for line in lines:
                safe_text = highlight(line, kws) if kws else html_escape(line)
                line_info = line_map.get(line_cursor)
                if line_info:
                    level      = line_info["level"]
                    cat_labels = html_escape(", ".join(line_info["labels"]))
                    row_class  = f"dv-line dv-hl-{level}"
                    title_attr = f' title="{cat_labels}"'
                else:
                    row_class  = "dv-line"
                    title_attr = ""
                ln_html = f'<span class="dv-ln">{line_cursor}</span>'
                rendered.append(
                    f'<span class="{row_class}"{title_attr}>{ln_html}{safe_text}</span>'
                )
                line_cursor += 1

            if rendered:
                st.markdown(
                    f'<div class="doc-viewer">{"".join(rendered)}</div>',
                    unsafe_allow_html=True,
                )

        elif btype == "table":
            df    = block.get("content")
            label = block.get("label", f"Table {table_counter + 1}")
            if df is not None and not df.empty:
                # Start marker
                st.markdown(
                    f'<div style="background:rgba(16,185,129,0.1); border-left:4px solid #10B981; '
                    f'padding:6px 12px; margin:16px 0 4px; border-radius:0 4px 4px 0;">'
                    f'📋 <strong>TABLE START</strong> · {html_escape(label)}</div>',
                    unsafe_allow_html=True
                )

                # Table grid
                _render_df_grid(df, key_prefix=f"rich_tbl_{table_counter}")

                # End marker
                st.markdown(
                    f'<div style="background:rgba(0,0,0,0.03); border-left:4px solid #94A3B8; '
                    f'padding:4px 12px; margin:4px 0 16px; border-radius:0 4px 4px 0; '
                    f'font-size:11px; color:#64748B;">'
                    f'━━━ TABLE END ━━━</div>',
                    unsafe_allow_html=True
                )
                table_counter += 1

    # Legend for risk highlights (if any)
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


# ── Standard text viewer (fallback) ───────────────────────────────────────────

def _render_full_document(lines: list, sv_kw: str, line_map: dict):
    kws           = [sv_kw.strip()] if sv_kw.strip() else []
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

    st.caption(
        f"{len(lines):,} lines total"
        + (f" · 🔦 {len(line_map)} flagged line(s)" if line_map else "")
    )
    st.markdown(
        f'<div class="doc-viewer">{"".join(rendered_lines)}</div>',
        unsafe_allow_html=True,
    )

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


# ── Findings side panel ───────────────────────────────────────────────────────

def _render_findings_panel(doc_findings: list):
    st.markdown("**Findings**")
    if not doc_findings:
        st.caption("No findings for this document.")
        return

    sorted_findings = sorted(
        doc_findings,
        key=lambda f: f.get("start_line") if isinstance(f.get("start_line"), int) else 9999,
    )
    for f in sorted_findings:
        risk  = f.get("risk_level", "LOW")
        cat   = clean(f.get("category_label", ""))
        sl, el = f.get("start_line", "?"), f.get("end_line", "?")
        txt   = clean_finding(f.get("finding", ""))
        short = txt[:110] + ("…" if len(txt) > 110 else "")
        color = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#22C55E"}.get(risk, "#94A3B8")
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