"""LLM Query Tab — RAG-powered natural language Q&A over contracts."""
import streamlit as st
from html import escape as html_escape
from datetime import datetime

from modules.llm_backend import LLMBackend
from modules.search import build_query_prompt, simple_relevance_search
from modules.search import bm25_search

# Fallback examples if generation fails or no LLM is configured
FALLBACK_EXAMPLES = [
    "What are the termination rights of each party?",
    "Are there any automatic renewal or evergreen clauses?",
    "What royalty or fee structures are defined?",
    "What indemnification obligations does the buyer carry?",
    "What are the governing law and dispute resolution provisions?",
    "Are there non-compete or exclusivity restrictions?",
]


def generate_example_questions(documents, max_questions=6):
    """
    Use the LLM to generate example questions relevant to the loaded documents.
    Returns a list of strings, or fallback examples if generation fails.
    """
    if not documents:
        return FALLBACK_EXAMPLES

    # Build a compact summary of the first few documents (to save tokens)
    summary_parts = []
    for doc in documents[:3]:  # limit to first 3 docs
        filename = doc.get("filename", "Unknown")
        # Take first 500 chars of raw_text as a sample
        text_sample = doc.get("raw_text", "")[:500].strip()
        if text_sample:
            summary_parts.append(f"Document: {filename}\nSample: {text_sample}")

    if not summary_parts:
        return FALLBACK_EXAMPLES

    summary = "\n\n".join(summary_parts)

    prompt = f"""Based on the following contract excerpts, generate {max_questions} insightful questions that a legal analyst might ask about these documents. The questions should cover key risks, obligations, and unusual clauses.

Excerpts:
{summary}

Return only a numbered list of questions, nothing else. Each question should be a complete sentence."""

    try:
        # Use the currently configured LLM backend
        backend_kwargs = st.session_state.get("backend_kwargs", {})
        if not backend_kwargs:
            return FALLBACK_EXAMPLES
        llm = LLMBackend(**backend_kwargs)
        result = llm.query(prompt, system_prompt="You are a helpful legal assistant generating example questions.")
        if result.get("error"):
            return FALLBACK_EXAMPLES
        response = result.get("response", "")
        # Parse numbered list
        lines = response.strip().split("\n")
        questions = []
        for line in lines:
            # Remove leading numbers, dots, dashes
            line = line.strip()
            if line and line[0].isdigit() and ". " in line:
                q = line.split(". ", 1)[-1].strip()
                questions.append(q)
            elif line.startswith("- "):
                questions.append(line[2:].strip())
            elif line:
                # fallback: take whole line if it looks like a question
                if "?" in line:
                    questions.append(line)
        # Remove duplicates and limit
        seen = set()
        unique = []
        for q in questions:
            if q and q not in seen:
                seen.add(q)
                unique.append(q)
                if len(unique) >= max_questions:
                    break   
        return unique if unique else FALLBACK_EXAMPLES
    except Exception as e:
        # Log error silently, return fallback
        print(f"Question generation error: {e}")
        return FALLBACK_EXAMPLES


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

    # Generate example questions when documents are loaded (or if not yet generated)
    if st.session_state.get("documents") and "example_questions" not in st.session_state:
        with st.spinner("Generating example questions..."):
            questions = generate_example_questions(st.session_state.documents)
            st.session_state.example_questions = questions

    # Display example questions
    example_qs = st.session_state.get("example_questions", FALLBACK_EXAMPLES)
    with st.expander("💡 Example questions — click to populate"):
        ec = st.columns(2)
        for i, eq in enumerate(example_qs[:6]):  # limit to 6
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

    # ── Retrieve controls: number of chunks + neighbour window ─────────────────
    qc1, qc2, qc3 = st.columns([1, 1, 4])
    with qc1:
        top_k = st.selectbox("Context chunks", [3, 5, 6, 8, 10], index=1)
    with qc2:
        window = st.number_input("Neighbours", min_value=0, max_value=3, value=1, step=1,
                                 help="Include this many chunks before and after each matched chunk")
    with qc3:   
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
                # 1. Get top‑k relevant chunks using simple relevance
                
                relevant = bm25_search(question, top_k)

                # 2. Expand each relevant chunk with its neighbours
                expanded = []
                # Group by document to keep order correct
                by_doc = {}
                for chunk in relevant:
                    fname = chunk["filename"]
                    if fname not in by_doc:
                        by_doc[fname] = []
                    by_doc[fname].append(chunk)

                for fname, chunks_in_doc in by_doc.items():
                    # Get all chunks of this document (they are already in order in session_state.chunks)
                    all_doc_chunks = [c for c in st.session_state.chunks if c["filename"] == fname]
                    # Build index → chunk map
                    idx_map = {c["chunk_index"]: c for c in all_doc_chunks}
                    # Indices of relevant chunks
                    rel_indices = sorted({c["chunk_index"] for c in chunks_in_doc})
                    # Expand with neighbours
                    expanded_indices = set()
                    for idx in rel_indices:
                        for offset in range(-window, window + 1):
                            neighbor = idx + offset
                            if neighbor in idx_map:
                                expanded_indices.add(neighbor)
                    # Add to final list, preserving order
                    for idx in sorted(expanded_indices):
                        expanded.append(idx_map[idx])

                # 3. Build prompt with expanded context (order preserved)
                prompt = build_query_prompt(question, expanded)
                result = LLMBackend(**st.session_state.backend_kwargs).query(prompt)

            if result.get("error"):
                st.error(f"LLM Error: {result['error']}")
            else:
                st.session_state.query_history = st.session_state.get("query_history", [])
                st.session_state.query_history.append({
                    "question": question,
                    "response": result.get("response", ""),
                    "chunks":   len(expanded),
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