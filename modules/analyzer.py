"""
Analyzer Module
Detects contractual risks using advanced prompt engineering.

Built-in categories: Misleading Clauses, Profit-Shifting, Hidden Obligations,
                     Indemnity Risks, Competition Restrictions, Penalty Traps.

Custom categories can be passed at runtime to any function via the `categories`
parameter — they are merged with RISK_CATEGORIES transparently.
"""

import re
from typing import List, Dict, Any, Optional

# ─────────────────────────────────────────────
# Built-in Risk Categories
# ─────────────────────────────────────────────

RISK_CATEGORIES: Dict[str, Dict] = {
    "misleading_clauses": {
        "label":       "⚠️ Misleading Clauses",
        "color":       "#F59E0B",
        "description": "Vague or ambiguous language that obscures obligations or rights",
        "keywords":    ["as appropriate", "reasonable efforts", "may at its discretion",
                        "subject to change", "as deemed necessary", "sole discretion",
                        "from time to time", "generally", "typically"],
        "custom":      False,
    },
    "profit_shifting": {
        "label":       "💰 Profit-Shifting Language",
        "color":       "#EF4444",
        "description": "Hidden fees, royalty structures, or mechanisms transferring profit",
        "keywords":    ["royalty", "management fee", "service charge", "administrative fee",
                        "overhead allocation", "cost-plus", "transfer pricing",
                        "intercompany", "license fee", "markup"],
        "custom":      False,
    },
    "hidden_obligations": {
        "label":       "🔒 Hidden Obligations",
        "color":       "#8B5CF6",
        "description": "Indirect responsibilities buried in definitions or schedules",
        "keywords":    ["as specified in schedule", "incorporated by reference",
                        "including but not limited to", "shall procure", "shall ensure that",
                        "shall cause", "indirectly responsible", "affiliate obligations"],
        "custom":      False,
    },
    "indemnity_risks": {
        "label":       "⚖️ Indemnity & Liability Risks",
        "color":       "#EC4899",
        "description": "Overly broad or one-sided indemnification and liability clauses",
        "keywords":    ["indemnify", "indemnification", "hold harmless", "unlimited liability",
                        "consequential damages", "including loss of profit", "any and all claims",
                        "defend and indemnify", "third party claims"],
        "custom":      False,
    },
    "competition_restrictions": {
        "label":       "🚫 Competition Restrictions",
        "color":       "#06B6D4",
        "description": "Non-compete, exclusivity, and market restriction clauses",
        "keywords":    ["non-compete", "non compete", "exclusivity", "exclusive",
                        "non-solicitation", "restraint of trade", "market restriction",
                        "territory restriction", "competing business", "competitive activity"],
        "custom":      False,
    },
    "penalty_traps": {
        "label":       "🪤 Penalty & Termination Traps",
        "color":       "#F97316",
        "description": "Automatic renewals, unilateral rights, and punitive exit clauses",
        "keywords":    ["automatic renewal", "auto-renew", "evergreen", "unilateral termination",
                        "liquidated damages", "termination for convenience", "break fee",
                        "exit penalty", "early termination fee", "rollover"],
        "custom":      False,
    },
}

RISK_LEVELS = {
    "HIGH":   {"score": 3, "color": "#EF4444", "label": "🔴 HIGH"},
    "MEDIUM": {"score": 2, "color": "#F59E0B", "label": "🟡 MEDIUM"},
    "LOW":    {"score": 1, "color": "#22C55E", "label": "🟢 LOW"},
}

# Colour palette cycled for custom categories
_CUSTOM_COLORS = ["#6366F1", "#10B981", "#F43F5E", "#0EA5E9",
                  "#84CC16", "#A855F7", "#FB923C", "#14B8A6"]


# ─────────────────────────────────────────────
# Category helpers
# ─────────────────────────────────────────────

def merge_categories(custom_categories: Optional[Dict] = None) -> Dict:
    """
    Return RISK_CATEGORIES merged with any runtime custom categories.
    Custom categories take precedence if they share a key (they won't under
    normal operation since keys are generated with a 'custom_' prefix).
    """
    if not custom_categories:
        return RISK_CATEGORIES
    return {**RISK_CATEGORIES, **custom_categories}


def make_custom_category(label: str, description: str, keywords: List[str],
                         index: int = 0) -> Dict:
    """Build a well-formed custom category dict."""
    color = _CUSTOM_COLORS[index % len(_CUSTOM_COLORS)]
    return {
        "label":       label,
        "color":       color,
        "description": description,
        "keywords":    keywords,
        "custom":      True,
    }


def custom_category_key(label: str) -> str:
    """Convert a display label to a safe dict key."""
    key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return f"custom_{key}" if key else f"custom_category"


# ─────────────────────────────────────────────
# Prompt building
# ─────────────────────────────────────────────

def build_analysis_prompt(chunk_text: str, category: str,
                          categories: Optional[Dict] = None) -> str:
    """Build an LLM prompt for a specific risk category."""
    all_cats = merge_categories(categories)
    cat_info = all_cats[category]
    return f"""You are a senior legal analyst at a top-tier international law firm specializing in cross-border deal documentation.

TASK: Analyze the following contract clause excerpt for: {cat_info['label']}
DEFINITION: {cat_info['description']}

CONTRACT EXCERPT:
\"\"\"
{chunk_text}
\"\"\"

If this excerpt contains risks related to {cat_info['label']}, provide your analysis in this EXACT format:

RISK_LEVEL: [HIGH/MEDIUM/LOW or NONE if no risk found]
FINDING: [1-2 sentence description of the specific risk identified]
PROBLEMATIC_LANGUAGE: [Quote the exact phrase(s) that are risky, or 'N/A']
INTERPRETATION: [Plain-English explanation of what this means practically for the party signing]
FOLLOW_UP_QUESTIONS:
1. [Specific question for legal team]
2. [Specific question for legal team]
3. [Specific question for legal team]

CRITICAL RULES — your response must follow these exactly:
- Output ONLY plain text. Do NOT include any HTML tags, markdown, code blocks, or formatting.
- Do NOT reference filenames, document names, or line numbers anywhere in your response.
- Do NOT repeat or echo any part of the instructions above.
- Do NOT include any text before RISK_LEVEL:.

If there is NO risk in this category, respond with only: RISK_LEVEL: NONE"""


# ─────────────────────────────────────────────
# Response parsing
# ─────────────────────────────────────────────

def _clean_field(text: str) -> str:
    """
    Sanitize a single extracted LLM field value:
      - Remove markdown code fences
      - Strip all HTML tags
      - Decode HTML entities
      - Remove residual filename tokens  (e.g. "misleading doc.docx")
      - Remove residual line-number tokens (e.g. "Lines 1–12")
      - Collapse whitespace
    """
    import html as _html
    text = text or ""
    text = re.sub(r"```[\w]*\n?|~~~[\w]*\n?", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)
    # Remove filename artifacts left after tag-stripping
    text = re.sub(r"[\w][\w \-]*\.(docx?|pdf|xlsx?|txt)\b", "", text, flags=re.IGNORECASE)
    # Remove line-range / line-number tokens
    text = re.sub(r"\bLines?\s+\d+\s*[\u2013\u2014\-]+\s*\d+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bLines?\s+\d+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_structured_block(response: str) -> str:
    """
    Discard EVERYTHING before the first RISK_LEVEL: marker.

    The LLM frequently prepends a formatted preamble (HTML spans, category
    headers, document names, line numbers) before the structured fields.
    Truncating at RISK_LEVEL: eliminates all of that in one step, making
    every downstream field regex operate on clean structured text only.
    """
    m = re.search(r"(RISK_LEVEL:.*)", response, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else response.strip()


def _strip(text: str) -> str:
    """Legacy alias — kept so any existing callers still work."""
    return _clean_field(text)


def parse_llm_risk_response(response: str, chunk: Dict, category: str,
                             categories: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """Parse a structured LLM response into a risk finding dict.

    The entire raw response is sanitized FIRST (HTML, markdown, file/line
    artifacts removed), then field regexes run on the clean text.
    This prevents any LLM-echoed markup from reaching the UI.
    """
    if not response or not response.strip():
        return None

    # ── Step 1: discard everything before RISK_LEVEL: ─────────────────────────
    # The LLM often prepends a formatted preamble (HTML, document names, line
    # numbers) before the structured output. Truncating here removes it all.
    structured = _extract_structured_block(response)

    if "RISK_LEVEL: NONE" in structured.upper():
        return None

    # ── Step 2: clean the structured block ────────────────────────────────────
    clean_response = structured

    all_cats = merge_categories(categories)
    cat_info = all_cats.get(category, {})

    finding: Dict[str, Any] = {
        "category":            category,
        "category_label":      cat_info.get("label", category),
        "category_color":      cat_info.get("color", "#94A3B8"),
        "is_custom":           cat_info.get("custom", False),
        "filename":            chunk.get("filename", ""),
        "chunk_id":            chunk.get("chunk_id", ""),
        "source_text":         (chunk.get("text", "")[:300] + "…"
                                if len(chunk.get("text", "")) > 300
                                else chunk.get("text", "")),
        "risk_level":          "MEDIUM",
        "finding":             "",
        "problematic_language":"",
        "interpretation":      "",
        "follow_up_questions": [],
        "raw_response":        response,   # keep original for debugging only
    }

    risk_match = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW)", clean_response, re.IGNORECASE)
    if risk_match:
        finding["risk_level"] = risk_match.group(1).upper()

    for field, pattern in [
        ("finding",              r"FINDING:\s*(.+?)(?=\n[A-Z_]+:|$)"),
        ("problematic_language", r"PROBLEMATIC_LANGUAGE:\s*(.+?)(?=\n[A-Z_]+:|$)"),
        ("interpretation",       r"INTERPRETATION:\s*(.+?)(?=\n[A-Z_]+:|$)"),
    ]:
        m = re.search(pattern, clean_response, re.DOTALL | re.IGNORECASE)
        if m:
            finding[field] = _clean_field(m.group(1))

    qs_match = re.search(r"FOLLOW_UP_QUESTIONS:(.*?)$", clean_response, re.DOTALL | re.IGNORECASE)
    if qs_match:
        qs = re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|$)", qs_match.group(1), re.DOTALL)
        finding["follow_up_questions"] = [_clean_field(q) for q in qs if q.strip()]

    return finding


# ─────────────────────────────────────────────
# Keyword scanning
# ─────────────────────────────────────────────

def keyword_scan_chunk(chunk_text: str,
                       categories: Optional[Dict] = None) -> Dict[str, List[str]]:
    """
    Fast keyword pre-filter (no LLM).
    Returns {category_key: [matched_keywords]} for categories that have hits.
    """
    all_cats   = merge_categories(categories)
    chunk_lower = chunk_text.lower()
    return {
        cat: [kw for kw in info["keywords"] if kw.lower() in chunk_lower]
        for cat, info in all_cats.items()
        if any(kw.lower() in chunk_lower for kw in info["keywords"])
    }


# ─────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────

def score_findings(findings: List[Dict],
                   categories: Optional[Dict] = None) -> Dict[str, Any]:
    """Aggregate risk scores. Works with both built-in and custom categories."""
    if not findings:
        return {"total": 0, "high": 0, "medium": 0, "low": 0,
                "by_category": {}, "overall_risk": "LOW"}

    all_cats   = merge_categories(categories)
    counts     = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_category: Dict[str, Dict] = {
        cat: {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": 0}
        for cat in all_cats
    }

    for f in findings:
        level = f.get("risk_level", "LOW")
        counts[level] = counts.get(level, 0) + 1
        cat = f.get("category", "")
        if cat not in by_category:
            by_category[cat] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": 0}
        by_category[cat][level]   += 1
        by_category[cat]["total"] += 1

    total_score = counts["HIGH"] * 3 + counts["MEDIUM"] * 2 + counts["LOW"]
    max_score   = len(findings) * 3
    if max_score > 0:
        r       = total_score / max_score
        overall = "HIGH" if r > 0.6 else "MEDIUM" if r > 0.3 else "LOW"
    else:
        overall = "LOW"

    return {
        "total":        len(findings),
        "high":         counts["HIGH"],
        "medium":       counts["MEDIUM"],
        "low":          counts["LOW"],
        "by_category":  by_category,
        "overall_risk": overall,
    }
