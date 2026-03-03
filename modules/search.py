"""
Search Module
Keyword search with EXACT line numbers per match occurrence.
Line number = chunk.start_line + (newlines before match position in chunk text).
"""

import re
from typing import List, Dict, Any


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
        start_line = chunk.get("start_line", 1)   # absolute line where chunk begins
        filename   = chunk.get("filename", "")

        if not isinstance(start_line, int):
            start_line = 1                         # fallback if not set

        matched_keywords = []
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

            # ── Per-match snippet with exact line number ──────────────────
            kw_snippets = []
            for m in matches:
                # Count newlines before match start to get line offset
                lines_before = text[: m.start()].count("\n")
                exact_line   = start_line + lines_before

                # Extend context to full lines around the match
                line_start = text.rfind("\n", 0, m.start())
                line_start = 0 if line_start == -1 else line_start + 1
                # Walk forward up to 4 lines for context
                line_end = m.end()
                newlines_found = 0
                while line_end < len(text) and newlines_found < 3:
                    if text[line_end] == "\n":
                        newlines_found += 1
                    line_end += 1

                # Also include 1 line before for context
                pre_start = line_start
                for _ in range(1):
                    pre_start = text.rfind("\n", 0, max(0, pre_start - 1))
                    pre_start = 0 if pre_start == -1 else pre_start + 1

                snippet = text[pre_start:line_end].replace("\n", " ").strip()

                kw_snippets.append({
                    "keyword":    kw,
                    "exact_line": exact_line,
                    "snippet":    snippet,
                    "match_start": m.start(),
                })

            all_match_snippets.extend(kw_snippets)

        if not matched_keywords:
            continue

        # Total occurrence count across all keywords
        total_hits = len(all_match_snippets)

        # Collect the sorted unique exact lines for display in the card header
        exact_lines_sorted = sorted(set(s["exact_line"] for s in all_match_snippets))

        results.append({
            "chunk_id":         chunk.get("chunk_id", ""),
            "filename":         filename,
            "chunk_start_line": start_line,
            "chunk_end_line":   chunk.get("end_line", start_line),
            "exact_lines":      exact_lines_sorted,   # ← exact per-match lines
            "chunk_index":      chunk.get("chunk_index", 0),
            "matched_keywords": matched_keywords,
            "match_snippets":   all_match_snippets,   # ← per-match with exact_line
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


def build_query_prompt(user_query: str, relevant_chunks: List[Dict],
                       max_context_chars: int = 5000) -> str:
    context_parts, total = [], 0
    for chunk in relevant_chunks[:10]:
        sl    = chunk.get("start_line", "?")
        entry = f"[Source: {chunk.get('filename','')} · Line {sl}]\n{chunk.get('text','')}"
        if total + len(entry) > max_context_chars:
            break
        context_parts.append(entry)
        total += len(entry)
    context = "\n\n---\n\n".join(context_parts)
    return f"""You are an expert legal analyst helping interpret complex deal documentation.

Answer based on the following excerpts. Cite source documents and line numbers.

DOCUMENT EXCERPTS:
{context}

USER QUESTION:
{user_query}

Provide a thorough, legally-informed answer. End with:
SOURCES USED: [list document names and line numbers referenced]"""


def simple_relevance_search(chunks: List[Dict], query: str, top_k: int = 6) -> List[Dict]:
    query_terms = set(re.findall(r'\b\w{3,}\b', query.lower()))
    if not query_terms:
        return chunks[:top_k]
    scored = [(len(query_terms & set(re.findall(r'\b\w{3,}\b', c.get("text","").lower()))), c)
              for c in chunks]
    scored = [(s, c) for s, c in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]