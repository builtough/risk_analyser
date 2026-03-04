"""Shared UI helper functions used across all tab modules."""
import re
import html as _html_lib
from html import escape as html_escape


def clean(t: str) -> str:
    """Strip HTML tags (keeping inner text), decode entities, collapse whitespace."""
    t = re.sub(r'<[^>]+>', ' ', t or '')
    t = _html_lib.unescape(t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def clean_finding(t: str) -> str:
    """
    Sanitize a finding text field for display.

    Drops ALL paired HTML tags AND their content (so filename/line text inside
    <span class="fc-src">…</span> is never shown), then strips remaining bare
    tags, removes filename/line-number tokens, and collapses whitespace.
    """
    t = t or ''
    # 1. Nuke every <tag>...</tag> pair AND its inner content (repeat for nesting)
    for _ in range(5):
        prev = t
        t = re.sub(r'<(\w+)[^>]*>.*?</\1>', '', t, flags=re.DOTALL | re.IGNORECASE)
        if t == prev:
            break
    # 2. Strip any leftover self-closing or unclosed tags
    t = re.sub(r'<[^>]+>', ' ', t)
    # 3. Decode HTML entities  (&quot; → "  &#x27; → '  etc.)
    t = _html_lib.unescape(t)
    # 4. Remove markdown code fences
    t = re.sub(r'```[\w]*\n?|~~~[\w]*\n?', '', t)
    # 5. Remove residual filename tokens  e.g. "misleading doc.docx"
    t = re.sub(r'\b[\w][\w \-]*\.(docx?|pdf|xlsx?|txt)\b', '', t, flags=re.IGNORECASE)
    # 6. Remove residual line-number tokens  e.g. "Lines 24–42" "Line 5"
    t = re.sub(r'\bLines?\s+\d+\s*[\u2013\u2014\-]+\s*\d+\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bLines?\s+\d+\b', '', t, flags=re.IGNORECASE)
    # 7. Collapse whitespace
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def highlight(text: str, keywords: list) -> str:
    """Wrap keyword matches in <mark> tags (HTML-escaped input)."""
    out = html_escape(text)
    for kw in keywords:
        if not kw:
            continue
        out = re.sub(
            re.escape(html_escape(kw)),
            lambda m: f"<mark>{m.group()}</mark>",
            out, flags=re.IGNORECASE,
        )
    return out


def badge(level: str) -> str:
    return f'<span class="badge badge-{level}">{level}</span>'


def metric_card(val, label: str, cls: str = "mc-blue") -> str:
    return (f'<div class="mc {cls}">'
            f'<div class="mc-v">{val}</div>'
            f'<div class="mc-l">{label}</div>'
            f'</div>')


def doc_pills(docs: list) -> str:
    icons = {"pdf": "📄", "docx": "📝", "doc": "📝", "xlsx": "📊", "xls": "📊"}
    out = "".join(
        f'<span class="dp">{icons.get(d.get("type",""), "📎")} {html_escape(d["filename"])}</span>'
        for d in docs[:8]
    )
    if len(docs) > 8:
        out += f'<span class="dp">+{len(docs)-8} more</span>'
    return out


def empty_state(icon: str, title: str, msg: str = "") -> str:
    return (f'<div class="empty-state">'
            f'<div class="es-icon">{icon}</div>'
            f'<h3>{title}</h3>'
            + (f'<p>{msg}</p>' if msg else '')
            + '</div>')


def build_finding_line_map(findings: list) -> dict:
    """Build line_number → worst_risk_level mapping for document viewer."""
    line_map: dict = {}
    level_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    for f in findings:
        sl = f.get("start_line")
        el = f.get("end_line")
        if not (isinstance(sl, int) and isinstance(el, int)):
            continue
        level = f.get("risk_level", "LOW")
        label = clean(f.get("category_label", ""))
        for ln in range(sl, el + 1):
            if ln not in line_map:
                line_map[ln] = {"level": level, "labels": [label]}
            else:
                if level_rank.get(level, 1) > level_rank.get(line_map[ln]["level"], 1):
                    line_map[ln]["level"] = level
                if label and label not in line_map[ln]["labels"]:
                    line_map[ln]["labels"].append(label)
    return line_map