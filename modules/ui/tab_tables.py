import re
import hashlib
"""
Tables Tab — displays all extracted tables from loaded documents.
Tables are grouped by source file.
Each table is shown as an interactive dataframe with download and preview controls.
"""
import io
import streamlit as st
import pandas as pd
from collections import defaultdict
from html import escape as html_escape


def _table_signature(df: pd.DataFrame) -> str:
    """Generate a hash signature from the first few rows to identify duplicates."""
    sample = df.head(3).to_string(index=False)
    return hashlib.md5(sample.encode()).hexdigest()


def render_tab_tables():
    st.markdown(
        '<div class="da-sec">📋 Extracted Tables · All Documents</div>',
        unsafe_allow_html=True,
    )

    tables = st.session_state.get("extracted_tables", [])

    if not tables:
        docs = st.session_state.get("documents", [])
        if not docs:
            st.markdown(
                '<div class="empty-state"><div class="es-icon">📋</div>'
                '<h3>No Documents Loaded</h3>'
                '<p>Upload and load documents via the sidebar first.</p></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="empty-state"><div class="es-icon">📋</div>'
                '<h3>No Tables Detected</h3>'
                '<p>No structured tables were found in the loaded documents. '
                'Tables are detected in PDF, Word, PowerPoint, Excel, and CSV files.</p></div>',
                unsafe_allow_html=True,
            )
        return

    # ── Deduplicate tables within each file (by content signature) ─────────────
    # Some documents may report the same table multiple times (e.g., PDF table extraction quirks).
    # We'll keep only the first occurrence of each unique signature per file.
    deduped_tables = []
    seen_per_file = defaultdict(set)
    for t in tables:
        filename = t["filename"]
        sig = _table_signature(t["df"])
        if sig not in seen_per_file[filename]:
            seen_per_file[filename].add(sig)
            deduped_tables.append(t)
    tables = deduped_tables

    # ── Summary strip ────────────────────────────────────────────────────────
    files_with_tables = len(set(t["filename"] for t in tables))
    total_rows  = sum(t["row_count"] for t in tables)
    total_cols  = sum(t["col_count"]  for t in tables)

    m1, m2, m3, m4 = st.columns(4)
    for col, val, lbl in [
        (m1, len(tables),        "Tables Found"),
        (m2, files_with_tables,  "Source Files"),
        (m3, f"{total_rows:,}",  "Total Rows"),
        (m4, f"{total_cols:,}",  "Total Columns"),
    ]:
        with col:
            st.markdown(
                f'<div class="mc mc-blue">'
                f'<div class="mc-v">{val}</div>'
                f'<div class="mc-l">{lbl}</div></div>',
                unsafe_allow_html=True,
            )
    st.markdown("")

    # ── Filter by file ───────────────────────────────────────────────────────
    all_files = sorted(set(t["filename"] for t in tables))
    if len(all_files) > 1:
        selected_file = st.selectbox(
            "Filter by document",
            ["All documents"] + all_files,
            key="tables_filter_file",
        )
        show_tables = tables if selected_file == "All documents" \
                      else [t for t in tables if t["filename"] == selected_file]
    else:
        show_tables = tables

    st.markdown(f"Showing **{len(show_tables)}** table(s)")
    st.markdown("---")

    # ── Group by file and render ─────────────────────────────────────────────
    by_file = defaultdict(list)
    for t in show_tables:
        by_file[t["filename"]].append(t)

    for filename, file_tables in by_file.items():
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        icon = {"pdf": "📄", "docx": "📝", "doc": "📝",
                "xlsx": "📊", "xls": "📊", "pptx": "📑",
                "csv": "🗂"}.get(ext, "📎")

        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'margin:16px 0 6px;">'
            f'<span style="font-size:18px;">{icon}</span>'
            f'<span style="font-weight:700;font-size:15px;color:#1E3A5F;">'
            f'{html_escape(filename)}</span>'
            f'<span style="font-size:12px;color:#64748B;margin-left:4px;">'
            f'· {len(file_tables)} table(s)</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Ensure each expander has a unique key based on filename and table index
        for idx, table in enumerate(file_tables):
            df     = table["df"]
            source = table.get("source", "")
            tname  = table.get("table_name", f"table_{idx}")

            # Create a unique key for the expander to avoid conflicts
            expander_key = f"table_expander_{filename}_{idx}_{_table_signature(df)[:8]}"

            with st.expander(
                f"📋  {source}  ·  {table['row_count']} rows × {table['col_count']} cols",
                expanded=True,
                key=expander_key,
            ):
                # Search + download controls
                cc1, cc2 = st.columns([4, 1])
                with cc1:
                    search_term = st.text_input(
                        "Filter rows",
                        placeholder="Filter rows…",
                        key=f"tbl_search_{tname}_{idx}",
                        label_visibility="collapsed",
                    )
                with cc2:
                    csv_buf = io.BytesIO()
                    df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
                    st.download_button(
                        "⬇ CSV",
                        data=csv_buf.getvalue(),
                        file_name=f"{tname}.csv",
                        mime="text/csv",
                        key=f"dl_{tname}_{idx}",
                        use_container_width=True,
                    )

                # Apply search filter — all rows shown, no limit
                display_df = df.copy()
                if search_term.strip():
                    mask = display_df.astype(str).apply(
                        lambda col: col.str.contains(search_term, case=False, na=False)
                    ).any(axis=1)
                    display_df = display_df[mask]
                    st.caption(f"{len(display_df)} of {len(df)} rows match")

                # Full table — no row cap
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    height=min(800, max(200, (len(display_df) + 1) * 35 + 40)),
                )

        st.markdown("---")

    # ── Bulk download ─────────────────────────────────────────────────────────
    if len(show_tables) > 1:
        st.markdown("#### Download All Tables")
        st.caption("Each table exported as a separate sheet in one Excel workbook.")
        if st.button("⬇ Download All as Excel", key="dl_all_tables"):
            xl_buf = io.BytesIO()
            with pd.ExcelWriter(xl_buf, engine="xlsxwriter") as writer:
                for table in show_tables:
                    sheet = re.sub(r"[\\/*?:\[\]]", "_", table["source"])[:31]
                    # Ensure sheet names are unique
                    base_sheet = sheet or "Table"
                    sheet_name = base_sheet
                    counter = 1
                    while sheet_name in writer.sheets:
                        sheet_name = f"{base_sheet}_{counter}"
                        counter += 1
                    table["df"].to_excel(writer, sheet_name=sheet_name, index=False)
            st.download_button(
                "⬇ Save Excel",
                data=xl_buf.getvalue(),
                file_name="extracted_tables.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_all_excel",
            )