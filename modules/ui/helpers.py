"""Shared UI helper functions used across all tab modules."""
import re
from html import escape as html_escape


def clean(t: str) -> str:
    """Strip HTML tags and whitespace."""
    return re.sub(r'<[^>]+>', '', t or '').strip()


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
    """
    Build a mapping of line_number -> worst_risk_level for document viewer highlighting.
    Also stores category labels for tooltip-like display.
    """
    line_map: dict = {}  # line_num -> {"level": str, "labels": list}
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
                existing_rank = level_rank.get(line_map[ln]["level"], 1)
                new_rank = level_rank.get(level, 1)
                if new_rank > existing_rank:
                    line_map[ln]["level"] = level
                if label and label not in line_map[ln]["labels"]:
                    line_map[ln]["labels"].append(label)
    return line_map
