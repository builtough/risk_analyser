"""
prompts.py — SINGLE SOURCE OF TRUTH FOR ALL LLM PROMPTS
=========================================================
Edit this file to change any prompt used across the application.
Two prompt tiers are provided:
  • FULL  — for large/cloud models (GPT-4, Claude Sonnet, Mistral Large, 70b+)
  • SMALL — for small local models (7b, 3b, phi, gemma, llama3 1b-8b, Ollama defaults)

To swap tiers, change PROMPT_TIER below.
"""

from typing import List, Dict, Optional

# ── Tier selector ─────────────────────────────────────────────────────────────
# PROMPT_TIER = "small"   # use this for local / resource-constrained models
PROMPT_TIER = "auto"      # "auto" = detect from model name; "full" or "small" to force

# ── Model name hints used by auto-detection ───────────────────────────────────
_SMALL_MODEL_HINTS = [
    "gemma", "phi", "mini", "tiny", "1b", "2b", "3b", "4b", "7b",
    "llama3:latest", "llama3.2", "llama2", "mistral:latest", "mistral:7b",
    "orca", "solar", "neural-chat", "dolphin",
]
_LARGE_MODEL_HINTS = [
    "opus", "large", "gpt-4", "70b", "72b", "34b", "claude-3",
    "sonnet", "mistral-large", "mixtral", "codestral",
]


def detect_tier(model_name: str = "") -> str:
    """Return 'small' or 'full' based on model name heuristics."""
    if PROMPT_TIER != "auto":
        return PROMPT_TIER
    n = (model_name or "").lower()
    if any(h in n for h in _SMALL_MODEL_HINTS):
        return "small"
    if any(h in n for h in _LARGE_MODEL_HINTS):
        return "full"
    return "full"   # default to full when unknown


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

# Full-tier system prompt — detailed persona for large models
SYSTEM_PROMPT_ANALYSIS_FULL = (
    "You are a senior legal analyst at a top-tier international law firm "
    "specialising in cross-border deal documentation. Analyse contract clauses "
    "with precision, identify risks, and provide actionable insights. "
    "Be concise, specific, and cite relevant clause language when possible."
)

# Small-tier system prompt — stripped down for local models
SYSTEM_PROMPT_ANALYSIS_SMALL = (
    "You are a legal analyst. Identify risks in contract clauses. "
    "Be concise and specific."
)

# Query / Q&A system prompt
# SYSTEM_PROMPT_QUERY_FULL = "You answer legal questions about contracts."  # minimal alternative
SYSTEM_PROMPT_QUERY_FULL = (
    "You are an expert legal analyst helping interpret complex deal documentation. "
    "Answer questions precisely, cite sources, and flag any ambiguities."
)

SYSTEM_PROMPT_QUERY_SMALL = "You answer questions about documents. Be concise and cite sources."

# Example-question generation system prompt
SYSTEM_PROMPT_EXAMPLES_FULL = (
    "You are a helpful legal assistant. Generate insightful questions about contract documents."
)
SYSTEM_PROMPT_EXAMPLES_SMALL = "Generate questions about this document."


def get_system_prompt(purpose: str = "analysis", model_name: str = "") -> str:
    """Return the right system prompt for the purpose and model tier."""
    tier = detect_tier(model_name)
    mapping = {
        "analysis": (SYSTEM_PROMPT_ANALYSIS_FULL, SYSTEM_PROMPT_ANALYSIS_SMALL),
        "query":    (SYSTEM_PROMPT_QUERY_FULL,    SYSTEM_PROMPT_QUERY_SMALL),
        "examples": (SYSTEM_PROMPT_EXAMPLES_FULL, SYSTEM_PROMPT_EXAMPLES_SMALL),
    }
    full, small = mapping.get(purpose, mapping["analysis"])
    return small if tier == "small" else full


# ═══════════════════════════════════════════════════════════════════════════════
# 2. RISK ANALYSIS PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

def build_analysis_prompt(chunk_text: str, category: str,
                          cat_info: Dict, model_name: str = "") -> str:
    """
    Build the risk analysis prompt for a single chunk + category.
    Automatically selects full or small version based on model_name.
    """
    tier = detect_tier(model_name)
    if tier == "small":
        return _analysis_prompt_small(chunk_text, category, cat_info)
    return _analysis_prompt_full(chunk_text, category, cat_info)


def _analysis_prompt_full(chunk_text: str, category: str, cat_info: Dict) -> str:
    return f"""You are a senior legal analyst at a top-tier international law firm.

TASK: Analyse the following contract excerpt for: {cat_info['label']}
DEFINITION: {cat_info['description']}

CONTRACT EXCERPT:
\"\"\"
{chunk_text}
\"\"\"

If this excerpt contains risks related to {cat_info['label']}, respond in this EXACT format:

RISK_LEVEL: [HIGH/MEDIUM/LOW or NONE if no risk]
FINDING: [1-2 sentence description of the specific risk]
PROBLEMATIC_LANGUAGE: [Exact risky phrase(s), or N/A]
INTERPRETATION: [Plain-English explanation of practical impact]
FOLLOW_UP_QUESTIONS:
1. [Question for legal team]
2. [Question for legal team]
3. [Question for legal team]

RULES:
- Plain text only. No HTML, markdown, or code blocks.
- Do not reference filenames or line numbers.
- Start your response with RISK_LEVEL:

If NO risk found: respond with only: RISK_LEVEL: NONE"""


def _analysis_prompt_small(chunk_text: str, category: str, cat_info: Dict) -> str:
    """Compact prompt for small/local models — fewer tokens, same structured output."""
    # Truncate chunk to keep prompt within small model context window
    # MAX_CHUNK_CHARS = 800   # tighter limit for very small models
    MAX_CHUNK_CHARS = 1200
    chunk = chunk_text[:MAX_CHUNK_CHARS] + ("..." if len(chunk_text) > MAX_CHUNK_CHARS else "")

    return f"""Legal risk analysis task.

Category: {cat_info['label']}
Description: {cat_info['description']}

Text to analyse:
{chunk}

If you find a risk, respond EXACTLY like this:
RISK_LEVEL: HIGH
FINDING: Brief description of risk.
PROBLEMATIC_LANGUAGE: Exact risky phrase or N/A
INTERPRETATION: What this means practically.
FOLLOW_UP_QUESTIONS:
1. First question.
2. Second question.
3. Third question.

If no risk: respond with only:
RISK_LEVEL: NONE"""


# ═══════════════════════════════════════════════════════════════════════════════
# 3. RAG / QUERY PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

def build_query_prompt(user_query: str, relevant_chunks: List[Dict],
                       max_context_chars: int = 5000,
                       model_name: str = "") -> str:
    """
    Build a RAG query prompt. Selects full or small version.
    For Excel/spreadsheet content, uses a table-aware variant.
    """
    # Detect if context is primarily tabular
    has_tables = any(c.get("is_table") or "--- BEGIN TABLE ---" in c.get("text", "")
                     for c in relevant_chunks)

    tier = detect_tier(model_name)
    context = _build_context_block(relevant_chunks, max_context_chars)

    if has_tables:
        return _query_prompt_tables(user_query, context, tier)
    if tier == "small":
        return _query_prompt_small(user_query, context)
    return _query_prompt_full(user_query, context)


def _build_context_block(chunks: List[Dict], max_chars: int) -> str:
    """Assemble context string from chunks, respecting char limit."""
    parts, total = [], 0
    for chunk in chunks[:10]:
        sl    = chunk.get("start_line", "?")
        entry = (f"[Source: {chunk.get('filename', '')} · Line {sl}]\n"
                 f"{chunk.get('text', '')}")
        if total + len(entry) > max_chars:
            break
        parts.append(entry)
        total += len(entry)
    return "\n\n---\n\n".join(parts)


def _query_prompt_full(user_query: str, context: str) -> str:
    return f"""You are an expert legal analyst helping interpret complex deal documentation.

Answer the question based on the document excerpts below. Cite source documents and line numbers.

DOCUMENT EXCERPTS:
{context}

USER QUESTION:
{user_query}

Provide a thorough, legally-informed answer. End with:
SOURCES USED: [list document names and line numbers referenced]"""


def _query_prompt_small(user_query: str, context: str) -> str:
    """Compact RAG prompt for small local models."""
    # MAX_CONTEXT = 2000  # very tight budget
    MAX_CONTEXT = 3000
    ctx = context[:MAX_CONTEXT] + ("..." if len(context) > MAX_CONTEXT else "")
    return f"""Answer the question using only the context below.
Cite the source document name.

CONTEXT:
{ctx}

QUESTION: {user_query}

ANSWER:"""


def _query_prompt_tables(user_query: str, context: str, tier: str = "full") -> str:
    """
    Specialised prompt for queries where context includes spreadsheet / table data.
    This ensures the model reads column names and row values correctly.
    """
    if tier == "small":
        # MAX_CONTEXT = 2500  # tighter for small models
        MAX_CONTEXT = 3500
        ctx = context[:MAX_CONTEXT]
        return f"""You are given structured table data from a spreadsheet.
Answer the question using only the data below.

DATA:
{ctx}

QUESTION: {user_query}

- Refer to column names exactly as they appear.
- If data is not in the table, say so.
- Be concise.

ANSWER:"""

    return f"""You are a data analyst helping interpret spreadsheet and tabular document content.

The context below may contain structured data extracted from Excel sheets, CSV files,
or tables embedded in documents. Column headers appear after "Columns:" and row data
is formatted as "ColumnName: value | ColumnName: value".

DOCUMENT / TABLE EXCERPTS:
{context}

USER QUESTION:
{user_query}

Instructions:
1. Identify which table(s) or sheet(s) contain relevant data.
2. Reference column names exactly as shown.
3. Summarise relevant rows or patterns.
4. If the question requires calculation, state your reasoning step by step.
5. If the data does not contain the answer, say so explicitly.

End with:
SOURCES USED: [table/sheet names and file references]"""


# ═══════════════════════════════════════════════════════════════════════════════
# 4. EXAMPLE QUESTION GENERATION PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

def build_example_questions_prompt(doc_summaries: List[str],
                                   n: int = 4,
                                   model_name: str = "") -> str:
    """
    Prompt to generate example questions relevant to the loaded documents.
    Shorter for small models.
    """
    tier = detect_tier(model_name)
    summary = "\n\n".join(doc_summaries)

    if tier == "small":
        # MAX_SUMMARY = 500  # very tight
        MAX_SUMMARY = 800
        summary = summary[:MAX_SUMMARY]
        return f"""Given this document excerpt, write {n} useful questions a user might ask.

{summary}

Return only a numbered list of questions."""

    # MAX_SUMMARY = 1500  # allow more context for large models
    MAX_SUMMARY = 2000
    summary = summary[:MAX_SUMMARY]
    return f"""Based on the following document excerpts, generate {n} insightful questions
a user might ask about the content. Focus on key facts, obligations, dates,
amounts, or risk areas present in the text.

Excerpts:
{summary}

Return only a numbered list of questions, nothing else.
Each question should be a complete sentence ending with '?'"""


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DOCUMENT SUMMARY PROMPT  (used by viewer / dashboard)
# ═══════════════════════════════════════════════════════════════════════════════

def build_summary_prompt(text_sample: str, filename: str,
                         model_name: str = "") -> str:
    """One-paragraph summary of a document for the viewer header."""
    tier = detect_tier(model_name)
    # MAX_CHARS = 600   # tighter
    MAX_CHARS = 1000
    sample = text_sample[:MAX_CHARS]

    if tier == "small":
        return f"Summarise this document in 2 sentences:\n\n{sample}"

    return f"""Provide a 2-3 sentence executive summary of the following document excerpt.
State the document type, key parties (if mentioned), and the main subject matter.

File: {filename}

Excerpt:
{sample}

Summary:"""
