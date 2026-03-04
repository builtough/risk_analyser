"""
Debug Tab — Raw LLM Output Inspector
Paste any raw LLM response and see exactly what parse_llm_risk_response()
extracts from it, field by field, before and after cleaning.
"""
import re
import streamlit as st
from html import escape as html_escape

from modules.ui.helpers import clean_finding


# ── Inline copies of the parser primitives (no import side-effects) ──────────

def _extract_structured_block(response: str) -> str:
    """Discard everything before the first RISK_LEVEL: line."""
    m = re.search(r"(RISK_LEVEL:.*)", response, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else response.strip()


def _parse_fields(structured: str) -> dict:
    out = {}
    risk_m = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW|NONE)", structured, re.IGNORECASE)
    out["RISK_LEVEL"] = risk_m.group(1).upper() if risk_m else "NOT FOUND"

    for field, pattern in [
        ("FINDING",              r"FINDING:\s*(.+?)(?=\n[A-Z_]+:|$)"),
        ("PROBLEMATIC_LANGUAGE", r"PROBLEMATIC_LANGUAGE:\s*(.+?)(?=\n[A-Z_]+:|$)"),
        ("INTERPRETATION",       r"INTERPRETATION:\s*(.+?)(?=\n[A-Z_]+:|$)"),
    ]:
        m = re.search(pattern, structured, re.DOTALL | re.IGNORECASE)
        out[field] = m.group(1).strip() if m else ""

    qs_m = re.search(r"FOLLOW_UP_QUESTIONS:(.*?)$", structured, re.DOTALL | re.IGNORECASE)
    if qs_m:
        qs = re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|$)", qs_m.group(1), re.DOTALL)
        out["FOLLOW_UP_QUESTIONS"] = [q.strip() for q in qs if q.strip()]
    else:
        out["FOLLOW_UP_QUESTIONS"] = []

    return out


def render_tab_debug():
    st.markdown('<div class="da-sec">🛠 Raw Output Inspector · Debug Tool</div>',
                unsafe_allow_html=True)

    st.markdown(
        "Paste any raw LLM response below to see exactly what the parser "
        "extracts and how `clean_finding()` transforms each field."
    )

    raw = st.text_area(
        "Raw LLM response",
        height=260,
        placeholder="""Paste raw LLM output here, e.g.:

HIGH ⚠️ Misleading Clauses
<span class="fc-src">doc.docx</span>
<span class="fc-ln">Lines 1–12</span>

RISK_LEVEL: HIGH
FINDING: The clause is ambiguous...
PROBLEMATIC_LANGUAGE: "sole discretion"
INTERPRETATION: Provider can act unilaterally.
FOLLOW_UP_QUESTIONS:
1. Can this be capped?
2. Is there a review process?""",
        label_visibility="collapsed",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        run = st.button("▶ Parse", type="primary", use_container_width=True)
    with col2:
        if st.button("Clear", use_container_width=False):
            st.session_state["debug_raw"] = ""
            st.rerun()

    if run and raw.strip():
        st.markdown("---")

        # ── Step 1: structured block ─────────────────────────────────────────
        structured = _extract_structured_block(raw)

        with st.expander("**Step 1 — After discarding preamble before RISK_LEVEL:**", expanded=True):
            if structured == raw.strip():
                st.info("No preamble found — RISK_LEVEL: was already at the top.")
            else:
                removed = raw[:raw.upper().find("RISK_LEVEL:")].strip()
                st.markdown("**Discarded preamble:**")
                st.code(removed, language=None)
            st.markdown("**Structured block passed to parser:**")
            st.code(structured, language=None)

        # ── Step 2: raw field extraction ─────────────────────────────────────
        raw_fields = _parse_fields(structured)

        with st.expander("**Step 2 — Raw extracted fields (before clean_finding):**", expanded=True):
            for key, val in raw_fields.items():
                if key == "FOLLOW_UP_QUESTIONS":
                    for i, q in enumerate(val, 1):
                        _field_row(f"Q{i}", q, q)
                else:
                    _field_row(key, val, val)

        # ── Step 3: after clean_finding ───────────────────────────────────────
        with st.expander("**Step 3 — After clean_finding() (what gets displayed):**", expanded=True):
            for key, val in raw_fields.items():
                if key in ("RISK_LEVEL",):
                    _field_row(key, val, val, show_diff=False)
                elif key == "FOLLOW_UP_QUESTIONS":
                    for i, q in enumerate(val, 1):
                        cleaned = clean_finding(q)
                        _field_row(f"Q{i}", q, cleaned)
                else:
                    cleaned = clean_finding(val)
                    _field_row(key, val, cleaned)

        # ── Step 4: still-dirty check ─────────────────────────────────────────
        st.markdown("---")
        dirt_markers = ["<span", "<div", "fc-src", "fc-ln", ".docx", ".pdf", "Lines "]
        dirty_fields = []
        for key, val in raw_fields.items():
            check = clean_finding(val) if isinstance(val, str) else ""
            if any(m in check for m in dirt_markers):
                dirty_fields.append((key, check))
        for q in raw_fields.get("FOLLOW_UP_QUESTIONS", []):
            check = clean_finding(q)
            if any(m in check for m in dirt_markers):
                dirty_fields.append(("FOLLOW_UP_Q", check))

        if dirty_fields:
            st.error(f"⚠️ {len(dirty_fields)} field(s) still contain artifacts after cleaning:")
            for key, val in dirty_fields:
                st.code(f"{key}: {val}", language=None)
        else:
            st.success("✅ All fields are clean after processing.")


def _field_row(label: str, raw_val: str, clean_val: str, show_diff: bool = True):
    has_dirt = raw_val != clean_val and show_diff
    col_label, col_val = st.columns([2, 8])
    with col_label:
        color = "#F59E0B" if has_dirt else "#22C55E"
        st.markdown(
            f'<div style="padding:6px 0;font-size:12px;font-weight:600;'
            f'color:{color};">{html_escape(label)}</div>',
            unsafe_allow_html=True,
        )
    with col_val:
        if has_dirt:
            st.markdown(
                f'<div style="font-size:12px;background:rgba(239,68,68,.07);'
                f'border-left:3px solid #EF4444;padding:6px 10px;border-radius:0 4px 4px 0;'
                f'margin-bottom:4px;"><strong>Raw:</strong> {html_escape(str(raw_val)[:300])}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="font-size:12px;background:rgba(34,197,94,.07);'
                f'border-left:3px solid #22C55E;padding:6px 10px;border-radius:0 4px 4px 0;">'
                f'<strong>Clean:</strong> {html_escape(str(clean_val)[:300])}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="font-size:12px;padding:6px 0;">'
                f'{html_escape(str(clean_val)[:300])}</div>',
                unsafe_allow_html=True,
            )