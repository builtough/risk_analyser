"""
LLM Query Tab — RAG-powered natural language Q&A over documents.

Changes:
 • Uses prompts.py for all prompt construction (Excel-aware variant included)
 • Example questions now use prompts.py for generation
 • model_name passed through so small-model tier is respected
 • BM25 search + neighbour window context expansion preserved
"""
import streamlit as st
from html import escape as html_escape
from datetime import datetime

from modules.llm_backend import LLMBackend
from modules.search import bm25_search, build_query_prompt_for_LLM_search
from modules.prompts import (
    build_example_questions_prompt,
    get_system_prompt,
)

# Fallback questions shown when LLM generation fails or no backend is configured
FALLBACK_EXAMPLES = [
    "What are the termination rights of each party?",
    "Are there any automatic renewal or evergreen clauses?",
    "What royalty or fee structures are defined?",
    "What indemnification obligations does the buyer carry?",
    "What are the governing law and dispute resolution provisions?",
    "Are there non-compete or exclusivity restrictions?",
]

# Excel / table specific fallbacks
FALLBACK_EXAMPLES_TABLE = [
    "What columns are present in the spreadsheet?",
    "What is the total or sum of the main numeric column?",
    "Are there any rows with missing or unusual values?",
    "What date range does the data cover?",
    "What are the top 5 entries by value?",
    "Summarise the key data points in the table.",
]


def _is_primarily_tabular(documents) -> bool:
    """Return True if most loaded documents are Excel/CSV files."""
    if not documents:
        return False
    tabular_count = sum(
        1 for d in documents
        if d.get("type", "").lower() in ("xlsx", "xls", "csv")
    )
    return tabular_count > len(documents) / 2


def generate_example_questions(documents, llm: LLMBackend, max_questions: int = 4):
    """
    Use the LLM to generate example questions relevant to the loaded documents.
    Falls back to static examples if generation fails.
    """
    if not documents:
        return FALLBACK_EXAMPLES_TABLE if _is_primarily_tabular(documents) else FALLBACK_EXAMPLES

    # Build compact summaries — use first 600 chars of each doc (or table preview)
    summaries = []
    for doc in documents[:3]:
        fname    = doc.get("filename", "Unknown")
        # MAX_SAMPLE = 300   # tighter for very small models
        MAX_SAMPLE = 600
        sample   = doc.get("raw_text", "")[:MAX_SAMPLE].strip()
        if sample:
            summaries.append(f"File: {fname}\n{sample}")

    if not summaries:
        return FALLBACK_EXAMPLES_TABLE if _is_primarily_tabular(documents) else FALLBACK_EXAMPLES

    model_name = llm.active_model_name
    prompt     = build_example_questions_prompt(summaries, n=max_questions,
                                                 model_name=model_name)
    sys_prompt = get_system_prompt("examples", model_name)

    try:
        result = llm.query(prompt, system_prompt=sys_prompt)
        if result.get("error"):
            return FALLBACK_EXAMPLES

        response  = result.get("response", "")
        lines     = response.strip().split("\n")
        questions = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Strip leading number / bullet
            if line[0].isdigit() and ". " in line:
                q = line.split(". ", 1)[-1].strip()
            elif line.startswith(("- ", "• ", "* ")):
                q = line[2:].strip()
            elif "?" in line:
                q = line
            else:
                continue
            if q:
                questions.append(q)

        # Deduplicate and limit
        seen, unique = set(), []
        for q in questions:
            if q not in seen:
                seen.add(q)
                unique.append(q)
                if len(unique) >= max_questions:
                    break

        return unique if unique else FALLBACK_EXAMPLES

    except Exception as e:
        print(f"[tab_query] Question generation error: {e}")
        return FALLBACK_EXAMPLES


# ═══════════════════════════════════════════════════════════════════════════════
# Main render function
# ═══════════════════════════════════════════════════════════════════════════════

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

    docs     = st.session_state.get("documents", [])
    is_tabular = _is_primarily_tabular(docs)

    # ── Hint for tabular content ──────────────────────────────────────────────
    if is_tabular:
        st.markdown(
            '<div class="info-strip">📊 <strong>Spreadsheet mode</strong> — '
            'the query engine will use a table-aware prompt to read your Excel/CSV data. '
            'Ask questions about column values, row counts, or specific data points.</div>',
            unsafe_allow_html=True,
        )

    # ── Generate example questions once per session load ─────────────────────
    if docs and st.session_state.get("example_questions") is None:
        if "backend_kwargs" in st.session_state:
            with st.spinner("Generating example questions…"):
                llm       = LLMBackend(**st.session_state.backend_kwargs)
                questions = generate_example_questions(docs, llm)
                st.session_state.example_questions = questions
        else:
            st.session_state.example_questions = (
                FALLBACK_EXAMPLES_TABLE if is_tabular else FALLBACK_EXAMPLES
            )

    example_qs = st.session_state.get("example_questions",
                                       FALLBACK_EXAMPLES_TABLE if is_tabular else FALLBACK_EXAMPLES)

    with st.expander("💡 Example questions — click to populate"):
        ec = st.columns(2)
        for i, eq in enumerate(example_qs[:6]):
            with ec[i % 2]:
                if st.button(eq, key=f"eq_{i}", use_container_width=True):
                    st.session_state.active_query = eq
                    st.rerun()

    # ── Query input ───────────────────────────────────────────────────────────
    user_q = st.text_area(
        "Your question",
        value=st.session_state.get("active_query", ""),
        placeholder="Type or click an example above…",
        height=90, label_visibility="collapsed",
    )
    st.session_state.active_query = user_q

    # ── Retrieve controls ─────────────────────────────────────────────────────
    qc1, qc2, qc3 = st.columns([1, 1, 4])
    with qc1:
        # top_k_default = 3   # use fewer chunks for small models
        top_k = st.selectbox("Context chunks", [3, 5, 6, 8, 10], index=1)
    with qc2:
        window = st.number_input(
            "Neighbours", min_value=0, max_value=3, value=1, step=1,
            help="Include chunks before/after each matched chunk for context",
        )
    with qc3:
        st.markdown("<div style='padding-top:22px'></div>", unsafe_allow_html=True)
        submit_q = st.button("💬 Ask Question", type="primary")

    if submit_q:
        _handle_query(user_q, top_k, window)

    # ── History ───────────────────────────────────────────────────────────────
    history = st.session_state.get("query_history", [])
    if history:
        st.markdown("---")
        for item in reversed(history):
            st.markdown(
                f'<div class="q-bub">Q: {html_escape(item["question"])}</div>',
                unsafe_allow_html=True)
            resp = html_escape(item["response"]).replace("\n", "<br>")
            src_note = ""
            if item.get("is_tabular"):
                src_note = " · 📊 Spreadsheet data"
            st.markdown(
                f'<div class="a-bub">'
                f'<div class="a-lbl">🤖 AI Answer · {item["ts"]} · '
                f'{item["chunks"]} sections{src_note}</div>'
                f'{resp}</div>',
                unsafe_allow_html=True)
            st.markdown("")

        if st.button("🗑 Clear History"):
            st.session_state.query_history = []
            st.rerun()


def _handle_query(user_q: str, top_k: int, window: int):
    """Run the RAG pipeline and store result in query_history."""
    question = user_q.strip()
    if not question:
        st.warning("Please type or select a question first.")
        return
    if "backend_kwargs" not in st.session_state:
        st.error("Configure the AI backend in the sidebar.")
        return

    with st.spinner("Retrieving context and generating answer…"):
        # 1. BM25 retrieval
        relevant = bm25_search(question, top_k)

        # 2. Context window expansion (neighbour chunks)
        expanded = _expand_with_neighbours(relevant, window)

        # 3. Build prompt — passes model_name so Excel-aware / small-model
        #    tiers are selected automatically in prompts.py
        llm        = LLMBackend(**st.session_state.backend_kwargs)
        model_name = llm.active_model_name
        prompt     = build_query_prompt_for_LLM_search(
            question, expanded, model_name=model_name
        )
        result     = llm.query_for_LLM_query(prompt)

    is_tabular = any(c.get("is_table") or "BEGIN TABLE" in c.get("text", "")
                     for c in expanded)

    if result.get("error"):
        st.error(f"LLM Error: {result['error']}")
    else:
        history = st.session_state.get("query_history", [])
        history.append({
            "question":   question,
            "response":   result.get("response", ""),
            "chunks":     len(expanded),
            "ts":         datetime.now().strftime("%H:%M"),
            "is_tabular": is_tabular,
        })
        st.session_state.query_history  = history
        st.session_state.active_query   = ""
        st.rerun()


def _expand_with_neighbours(relevant_chunks: list, window: int) -> list:
    """Add neighbouring chunks around each relevant chunk for richer context."""
    all_chunks = st.session_state.get("chunks", [])

    by_doc = {}
    for chunk in relevant_chunks:
        fname = chunk["filename"]
        by_doc.setdefault(fname, []).append(chunk)

    expanded = []
    for fname, chunks_in_doc in by_doc.items():
        all_doc   = [c for c in all_chunks if c["filename"] == fname]
        idx_map   = {c["chunk_index"]: c for c in all_doc}
        rel_idxs  = sorted({c["chunk_index"] for c in chunks_in_doc})

        exp_idxs = set()
        for idx in rel_idxs:
            for offset in range(-window, window + 1):
                nb = idx + offset
                if nb in idx_map:
                    exp_idxs.add(nb)

        for idx in sorted(exp_idxs):
            expanded.append(idx_map[idx])

    return expanded
