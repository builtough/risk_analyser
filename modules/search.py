"""
Search Module
Keyword search with EXACT line numbers per match occurrence.
Line number = chunk.start_line + (newlines before match position in chunk text).
Also provides BM25 retrieval for better relevance in LLM queries.

BUG FIXED: build_query_prompt_for_LLM_search had a typo "s    tart_line"
           which silently returned "?" for every line reference.
"""

import re
import string
from typing import List, Dict, Any

# Prompts are now centralised in modules/prompts.py
from modules.prompts import build_query_prompt as _build_query_prompt_base

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False


# ── Keyword search ────────────────────────────────────────────────────────────

def keyword_search(chunks: List[Dict], keywords: List[str],
                   case_sensitive: bool = False) -> List[Dict[str, Any]]:
    """
    Search all chunks for keyword matches.
    Returns results grouped by chunk, each snippet carrying the EXACT line number
    of the match within the source document.
    """
    results = []
    flags = 0 if case_sensitive else re.IGNORECASE

    for chunk in chunks:
        text       = chunk.get("text", "")
        start_line = chunk.get("start_line", 1)
        filename   = chunk.get("filename", "")

        if not isinstance(start_line, int):
            start_line = 1

        matched_keywords        = []
        all_match_snippets: List[Dict] = []

        for kw in keywords:
            kw = kw.strip()
            if not kw:
                continue

            pattern = re.escape(kw)
            matches = list(re.finditer(pattern, text, flags))
            if not matches:
                continue

            matched_keywords.append(kw)

            for m in matches:
                lines_before = text[: m.start()].count("\n")
                exact_line   = start_line + lines_before

                line_start = text.rfind("\n", 0, m.start())
                line_start = 0 if line_start == -1 else line_start + 1
                line_end   = m.end()
                newlines_found = 0
                while line_end < len(text) and newlines_found < 3:
                    if text[line_end] == "\n":
                        newlines_found += 1
                    line_end += 1

                pre_start = line_start
                for _ in range(1):
                    pre_start = text.rfind("\n", 0, max(0, pre_start - 1))
                    pre_start = 0 if pre_start == -1 else pre_start + 1

                snippet = text[pre_start:line_end].replace("\n", " ").strip()

                all_match_snippets.append({
                    "keyword":    kw,
                    "exact_line": exact_line,
                    "snippet":    snippet,
                    "match_start": m.start(),
                })

        if not matched_keywords:
            continue

        total_hits       = len(all_match_snippets)
        exact_lines_sorted = sorted(set(s["exact_line"] for s in all_match_snippets))

        results.append({
            "chunk_id":         chunk.get("chunk_id", ""),
            "filename":         filename,
            "chunk_start_line": start_line,
            "chunk_end_line":   chunk.get("end_line", start_line),
            "exact_lines":      exact_lines_sorted,
            "chunk_index":      chunk.get("chunk_index", 0),
            "matched_keywords": matched_keywords,
            "match_snippets":   all_match_snippets,
            "total_hits":       total_hits,
            "relevance_score":  len(matched_keywords),
        })

    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results


def get_keyword_frequencies(chunks: List[Dict], keywords: List[str]) -> Dict[str, Dict[str, int]]:
    freq: Dict[str, Dict[str, int]] = {}
    for chunk in chunks:
        fname = chunk.get("filename", "unknown")
        text  = chunk.get("text", "").lower()
        if fname not in freq:
            freq[fname] = {kw: 0 for kw in keywords}
        for kw in keywords:
            freq[fname][kw] = freq[fname].get(kw, 0) + len(
                re.findall(re.escape(kw.lower()), text)
            )
    return freq


# ── Query prompts (delegate to prompts.py) ────────────────────────────────────

def build_query_prompt(user_query: str, relevant_chunks: List[Dict],
                       max_context_chars: int = 5000,
                       model_name: str = "") -> str:
    """Build a RAG query prompt. Delegates to modules/prompts.py."""
    return _build_query_prompt_base(
        user_query, relevant_chunks,
        max_context_chars=max_context_chars,
        model_name=model_name,
    )


# Alias kept for backwards compatibility with any existing callers
def build_query_prompt_for_LLM_search(user_query: str, relevant_chunks: List[Dict],
                                       max_context_chars: int = 5000,
                                       model_name: str = "") -> str:
    """
    RAG prompt for the LLM Query tab.
    BUG FIX: was using 'chunk.get("s    tart_line")' (typo with spaces) which
    always fell back to "?" and broke source citation in every answer.
    Now delegates to prompts.py which uses the correct "start_line" key.
    """
    return _build_query_prompt_base(
        user_query, relevant_chunks,
        max_context_chars=max_context_chars,
        model_name=model_name,
    )


# ── Simple fallback search ────────────────────────────────────────────────────

def simple_relevance_search(chunks: List[Dict], query: str, top_k: int = 6) -> List[Dict]:
    """Fallback relevance search: count overlapping words between query and chunk."""
    query_terms = set(re.findall(r'\b\w{3,}\b', query.lower()))
    if not query_terms:
        return chunks[:top_k]
    scored = [(len(query_terms & set(re.findall(r'\b\w{3,}\b', c.get("text","").lower()))), c)
              for c in chunks]
    scored = [(s, c) for s, c in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


# ── BM25 retrieval ────────────────────────────────────────────────────────────

def build_bm25_index(chunks):
    """Build a BM25 index from chunk texts and store it in session state."""
    import streamlit as st

    if not chunks:
        return
    if not BM25_AVAILABLE:
        st.warning("rank-bm25 not installed — falling back to simple relevance search. "
                   "Install with: pip install rank-bm25")
        return

    translator       = str.maketrans('', '', string.punctuation)
    tokenized_corpus = [
        chunk.get("text", "").lower().translate(translator).split()
        for chunk in chunks
    ]
    st.session_state.bm25        = BM25Okapi(tokenized_corpus)
    st.session_state.bm25_chunks = chunks


def bm25_search(query: str, top_k: int = 6) -> List[Dict]:
    """
    Retrieve top_k chunks using BM25 index from session state.
    Falls back to simple_relevance_search when index is unavailable.
    """
    import streamlit as st

    if not BM25_AVAILABLE or "bm25" not in st.session_state:
        return simple_relevance_search(st.session_state.get("chunks", []), query, top_k)

    chunks      = st.session_state.bm25_chunks
    translator  = str.maketrans('', '', string.punctuation)
    query_tokens = query.lower().translate(translator).split()

    if not query_tokens:
        return chunks[:top_k]

    scores      = st.session_state.bm25.get_scores(query_tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [chunks[i] for i in top_indices]
