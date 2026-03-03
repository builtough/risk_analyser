"""
Analyzer Module
Detects contractual risks using advanced prompt engineering.
Categories: Misleading Clauses, Profit-Shifting, Hidden Obligations,
            Indemnity Risks, Competition Restrictions, Penalty Traps.
Returns risk-scored findings with explanations and suggested follow-up questions.
"""

import re
from typing import List, Dict, Any, Optional


# ─────────────────────────────────────────────
# Risk Categories & Detection Prompts
# ─────────────────────────────────────────────

RISK_CATEGORIES = {
    "misleading_clauses": {
        "label": "⚠️ Misleading Clauses",
        "color": "#F59E0B",
        "description": "Vague or ambiguous language that obscures obligations or rights",
        "keywords": ["as appropriate", "reasonable efforts", "may at its discretion", "subject to change",
                     "as deemed necessary", "sole discretion", "from time to time", "generally", "typically"]
    },
    "profit_shifting": {
        "label": "💰 Profit-Shifting Language",
        "color": "#EF4444",
        "description": "Hidden fees, royalty structures, or mechanisms transferring profit",
        "keywords": ["royalty", "management fee", "service charge", "administrative fee", "overhead allocation",
                     "cost-plus", "transfer pricing", "intercompany", "license fee", "markup"]
    },
    "hidden_obligations": {
        "label": "🔒 Hidden Obligations",
        "color": "#8B5CF6",
        "description": "Indirect responsibilities buried in definitions or schedules",
        "keywords": ["as specified in schedule", "incorporated by reference", "including but not limited to",
                     "shall procure", "shall ensure that", "shall cause", "indirectly responsible", "affiliate obligations"]
    },
    "indemnity_risks": {
        "label": "⚖️ Indemnity & Liability Risks",
        "color": "#EC4899",
        "description": "Overly broad or one-sided indemnification and liability clauses",
        "keywords": ["indemnify", "indemnification", "hold harmless", "unlimited liability", "consequential damages",
                     "including loss of profit", "any and all claims", "defend and indemnify", "third party claims"]
    },
    "competition_restrictions": {
        "label": "🚫 Competition Restrictions",
        "color": "#06B6D4",
        "description": "Non-compete, exclusivity, and market restriction clauses",
        "keywords": ["non-compete", "non compete", "exclusivity", "exclusive", "non-solicitation", "restraint of trade",
                     "market restriction", "territory restriction", "competing business", "competitive activity"]
    },
    "penalty_traps": {
        "label": "🪤 Penalty & Termination Traps",
        "color": "#F97316",
        "description": "Automatic renewals, unilateral rights, and punitive exit clauses",
        "keywords": ["automatic renewal", "auto-renew", "evergreen", "unilateral termination", "liquidated damages",
                     "termination for convenience", "break fee", "exit penalty", "early termination fee", "rollover"]
    }
}

RISK_LEVELS = {
    "HIGH": {"score": 3, "color": "#EF4444", "label": "🔴 HIGH"},
    "MEDIUM": {"score": 2, "color": "#F59E0B", "label": "🟡 MEDIUM"},
    "LOW": {"score": 1, "color": "#22C55E", "label": "🟢 LOW"}
}


def build_analysis_prompt(chunk_text: str, category: str) -> str:
    """Build an advanced prompt for a specific risk category."""
    cat_info = RISK_CATEGORIES[category]
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

If there is NO risk in this category, respond with only: RISK_LEVEL: NONE"""


def parse_llm_risk_response(response: str, chunk: Dict, category: str) -> Optional[Dict[str, Any]]:
    """Parse structured LLM response into a risk finding dict."""
    if "RISK_LEVEL: NONE" in response.upper() or not response.strip():
        return None

    finding = {
        "category": category,
        "category_label": RISK_CATEGORIES[category]["label"],
        "category_color": RISK_CATEGORIES[category]["color"],
        "filename": chunk.get("filename", ""),
        "chunk_id": chunk.get("chunk_id", ""),
        "source_text": chunk.get("text", "")[:300] + "..." if len(chunk.get("text", "")) > 300 else chunk.get("text", ""),
        "risk_level": "MEDIUM",  # default
        "finding": "",
        "problematic_language": "",
        "interpretation": "",
        "follow_up_questions": [],
        "raw_response": response
    }

    # Extract risk level
    risk_match = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW)", response, re.IGNORECASE)
    if risk_match:
        finding["risk_level"] = risk_match.group(1).upper()

    # Extract other fields
    for field, pattern in [
        ("finding", r"FINDING:\s*(.+?)(?=\n[A-Z_]+:|$)"),
        ("problematic_language", r"PROBLEMATIC_LANGUAGE:\s*(.+?)(?=\n[A-Z_]+:|$)"),
        ("interpretation", r"INTERPRETATION:\s*(.+?)(?=\n[A-Z_]+:|$)")
    ]:
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            finding[field] = match.group(1).strip()

    # Extract follow-up questions
    questions_match = re.search(r"FOLLOW_UP_QUESTIONS:(.*?)$", response, re.DOTALL | re.IGNORECASE)
    if questions_match:
        questions_text = questions_match.group(1)
        questions = re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|$)", questions_text, re.DOTALL)
        finding["follow_up_questions"] = [q.strip() for q in questions if q.strip()]

    return finding


def keyword_scan_chunk(chunk_text: str) -> Dict[str, List[str]]:
    """
    Fast keyword scan (no LLM) to pre-filter chunks before sending to LLM.
    Returns dict of category → matched keywords found in chunk.
    """
    chunk_lower = chunk_text.lower()
    hits = {}
    for category, info in RISK_CATEGORIES.items():
        matched = [kw for kw in info["keywords"] if kw.lower() in chunk_lower]
        if matched:
            hits[category] = matched
    return hits


def score_findings(findings: List[Dict]) -> Dict[str, Any]:
    """
    Aggregate risk scores across all findings.
    Returns summary statistics for the dashboard.
    """
    if not findings:
        return {"total": 0, "high": 0, "medium": 0, "low": 0, "by_category": {}, "overall_risk": "LOW"}

    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_category = {cat: {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": 0} for cat in RISK_CATEGORIES}

    for f in findings:
        level = f.get("risk_level", "LOW")
        counts[level] = counts.get(level, 0) + 1
        cat = f.get("category", "")
        if cat in by_category:
            by_category[cat][level] += 1
            by_category[cat]["total"] += 1

    total_score = counts["HIGH"] * 3 + counts["MEDIUM"] * 2 + counts["LOW"]
    max_score = len(findings) * 3

    if max_score > 0:
        risk_ratio = total_score / max_score
        overall = "HIGH" if risk_ratio > 0.6 else "MEDIUM" if risk_ratio > 0.3 else "LOW"
    else:
        overall = "LOW"

    return {
        "total": len(findings),
        "high": counts["HIGH"],
        "medium": counts["MEDIUM"],
        "low": counts["LOW"],
        "by_category": by_category,
        "overall_risk": overall
    }