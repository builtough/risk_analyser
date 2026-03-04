"""Document Search Tab — results grouped by document with correct occurrence counts."""
import streamlit as st
from collections import defaultdict
from html import escape as html_escape

from modules.search import keyword_search, get_keyword_frequencies
from modules.ui.helpers import highlight


def render_tab_search():
    st.markdown('<div class="da-sec">🔍 Keyword & Context Search · Multi-Document</div>',
                unsafe_allow_html=True)

    if not st.session_state.get("chunks"):
        st.markdown(
            '<div class="empty-state"><div class="es-icon">🔍</div>'
            '<h3>No Documents Loaded</h3>'
            '<p>Upload and load documents via the sidebar first.</p></div>',
            unsafe_allow_html=True)
        return

    sc1, sc2 = st.columns([4, 1])
    with sc1:
        kw_input = st.text_input(
            "Keywords",
            placeholder="e.g. indemnify, royalty, automatic renewal, sole discretion",
            label_visibility="collapsed",
        )
    with sc2:
        run_search = st.button("🔍 Search", use_container_width=True, type="primary")

    cs_check = st.checkbox("Case-sensitive match", value=False)

    if run_search and kw_input.strip():
        kws = [k.strip() for k in kw_input.split(",") if k.strip()]
        with st.spinner("Searching…"):
            results = keyword_search(st.session_state.chunks, kws, cs_check)
            freq    = get_keyword_frequencies(st.session_state.chunks, kws)
        st.session_state.search_results = results
        st.session_state.freq_data      = freq
        st.session_state.last_keywords  = kws

    if st.session_state.get("search_results"):
        results = st.session_state.search_results
        kws     = st.session_state.get("last_keywords", [])

        # ── Group chunks by document ─────────────────────────────────────────
        by_doc = defaultdict(list)
        for r in results:
            by_doc[r.get("filename", "unknown")].append(r)

        # Total unique (doc, keyword, line) occurrences across corpus
        all_pairs = set()
        for r in results:
            for s in r.get("match_snippets", []):
                all_pairs.add((r["filename"], s["keyword"], s["exact_line"]))
        total_occ = len(all_pairs)

        st.markdown(
            f"**{len(by_doc)} document(s) matched · {total_occ} unique occurrence(s)**")
        st.markdown("")

        for doc_name, doc_results in by_doc.items():
            # Unique (keyword, line) pairs for this doc only
            doc_pairs = set()
            for r in doc_results:
                for s in r.get("match_snippets", []):
                    doc_pairs.add((s["keyword"], s["exact_line"]))
            doc_occ = len(doc_pairs)

            all_matched_kws = sorted({
                kw for r in doc_results for kw in r.get("matched_keywords", [])
            })
            all_exact_lines = sorted({
                ln for r in doc_results for ln in r.get("exact_lines", [])
            })

            if len(all_exact_lines) == 1:
                line_display = f"Line {all_exact_lines[0]}"
            elif len(all_exact_lines) <= 8:
                line_display = "Lines " + ", ".join(str(l) for l in all_exact_lines)
            else:
                line_display = (f"Lines {all_exact_lines[0]}–{all_exact_lines[-1]} "
                                f"({len(all_exact_lines)} matches)")

            kw_badges = " ".join(
                f'<span class="sr-kw">{html_escape(k)}</span>' for k in all_matched_kws
            )

            # Collect all snippets across chunks, sort by line, deduplicate
            all_snippets = sorted(
                (s for r in doc_results for s in r.get("match_snippets", [])),
                key=lambda s: s.get("exact_line", 0),
            )
            seen = set()
            match_blocks = ""
            for s in all_snippets:
                key = (s["keyword"], s["exact_line"])
                if key in seen:
                    continue
                seen.add(key)
                high = highlight(s.get("snippet", ""), kws)
                ln   = s.get("exact_line", "?")
                kw   = html_escape(s.get("keyword", ""))
                match_blocks += (
                    f'<div class="sr-match">'
                    f'<div class="sr-match-kw">'
                    f'Keyword: <strong>"{kw}"</strong>'
                    f' &nbsp;·&nbsp; '
                    f'<span style="color:#3B82F6;font-family:\'Roboto Mono\',monospace;">'
                    f'Line {ln}</span>'
                    f'</div>'
                    f'<div class="sr-ctx">…{high}…</div>'
                    f'</div>'
                )

            st.markdown(f"""
            <div class="sr">
              <div class="sr-hdr">
                <span class="sr-doc">📄 {html_escape(doc_name)}</span>
                <span class="sr-ln">{line_display}</span>
                <span class="sr-cnt">×{doc_occ} occurrence(s)</span>
                {kw_badges}
              </div>
              <div class="sr-body">{match_blocks}</div>
            </div>""", unsafe_allow_html=True)

    elif run_search:
        st.warning("No matches found. Try different keywords.")