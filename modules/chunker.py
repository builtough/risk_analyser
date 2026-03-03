"""
Chunker Module — line-number tracking + intelligent auto-param selection.
"""
from typing import List, Dict, Any
import re


def chunk_document(doc: Dict[str, Any], chunk_size: int = 700,
                   overlap: int = 120) -> List[Dict[str, Any]]:
    text     = doc.get("raw_text", "")
    filename = doc.get("filename", "unknown")
    if not text.strip():
        return []
    lines = text.split("\n")
    return _chunk_by_lines(lines, filename, chunk_size, overlap)


def _chunk_by_lines(lines, filename, chunk_size, overlap):
    chunks, idx = [], 0
    current, cur_chars, start_line = [], 0, 1

    for line_num, line in enumerate(lines, start=1):
        ll = len(line) + 1
        if cur_chars + ll > chunk_size and current:
            txt = "\n".join(current).strip()
            end_line = start_line + len(current) - 1
            if txt:
                chunks.append(_make_chunk(txt, filename, idx, start_line, end_line))
                idx += 1
            # overlap: keep tail lines
            ov_lines, ov_chars = [], 0
            for l in reversed(current):
                if ov_chars + len(l) + 1 <= overlap:
                    ov_lines.insert(0, l); ov_chars += len(l) + 1
                else:
                    break
            current   = ov_lines + [line]
            cur_chars = sum(len(l) + 1 for l in current)
            start_line = max(1, line_num - len(ov_lines))
        else:
            if not current:
                start_line = line_num
            current.append(line); cur_chars += ll

    if current:
        txt = "\n".join(current).strip()
        if txt:
            end_line = start_line + len(current) - 1
            chunks.append(_make_chunk(txt, filename, idx, start_line, end_line))
    return chunks


def chunk_all_documents(documents: List[Dict], chunk_size=700, overlap=120):
    all_chunks = []
    for doc in documents:
        if not doc.get("error"):
            all_chunks.extend(chunk_document(doc, chunk_size, overlap))
    return all_chunks


def _make_chunk(text, filename, idx, start_line, end_line):
    return {
        "chunk_id":    f"{filename}::chunk_{idx}",
        "filename":    filename,
        "chunk_index": idx,
        "start_line":  start_line,
        "end_line":    end_line,
        "text":        text,
        "char_count":  len(text),
        "word_count":  len(text.split()),
    }


def auto_chunk_params(backend_type: str = "", model_name: str = "") -> dict:
    """
    Intelligently select chunk_size / overlap / max_tokens based on model.
    Used when the user selects 'Auto' chunking mode.
    """
    n = model_name.lower()
    if any(x in n for x in ["opus", "large", "gpt-4", "70b", "72b", "34b"]):
        return {"chunk_size": 1400, "overlap": 220, "max_tokens": 4096,
                "label": "Large model — 1400c chunks · 220c overlap · 4096 tokens"}
    elif any(x in n for x in ["sonnet", "medium", "mixtral", "mistral-large", "13b"]):
        return {"chunk_size": 1000, "overlap": 160, "max_tokens": 3072,
                "label": "Mid model — 1000c chunks · 160c overlap · 3072 tokens"}
    elif any(x in n for x in ["haiku", "small", "phi", "mini", "7b", "3b"]):
        return {"chunk_size": 600,  "overlap": 100, "max_tokens": 1024,
                "label": "Small model — 600c chunks · 100c overlap · 1024 tokens"}
    elif "ollama" in backend_type.lower():
        return {"chunk_size": 800,  "overlap": 130, "max_tokens": 2048,
                "label": "Ollama default — 800c chunks · 130c overlap · 2048 tokens"}
    else:
        return {"chunk_size": 900,  "overlap": 150, "max_tokens": 2048,
                "label": "Default — 900c chunks · 150c overlap · 2048 tokens"}