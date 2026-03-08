"""
Chunker Module — line-number tracking + intelligent auto-param selection.

BUG FIXED: chunk_all_documents was defined twice; the second (simpler) definition
silently overwrote the first (smarter rich_blocks-aware one). Now only one
definition exists and it handles both cases correctly.
"""
from typing import List, Dict, Any


def chunk_document_preserve_structure(doc: Dict, chunk_size: int = 700,
                                       overlap: int = 120) -> List[Dict]:
    """
    Create chunks that preserve the original order of text and table blocks.
    Falls back to plain line-based chunking when no rich_blocks are present.
    """
    from modules.table_extractor import table_to_text

    rich_blocks = doc.get("rich_blocks", [])
    if not rich_blocks:
        return chunk_document(doc, chunk_size, overlap)

    chunks      = []
    chunk_index = 0
    cumulative_lines = 0   # absolute line count across all blocks

    for block in rich_blocks:
        if block["type"] == "text":
            text = block.get("content", "")
            if not text.strip():
                continue
            lines = text.split("\n")
            current, cur_chars, start_line_offset = [], 0, 0

            for line_num, line in enumerate(lines, start=1):
                ll = len(line) + 1
                if cur_chars + ll > chunk_size and current:
                    txt = "\n".join(current).strip()
                    if txt:
                        s = cumulative_lines + start_line_offset
                        e = cumulative_lines + start_line_offset + len(current) - 1
                        chunks.append(_make_chunk(txt, doc["filename"], chunk_index, s, e))
                        chunk_index += 1
                    # Overlap: keep tail lines
                    ov_lines, ov_chars = [], 0
                    for lv in reversed(current):
                        if ov_chars + len(lv) + 1 <= overlap:
                            ov_lines.insert(0, lv)
                            ov_chars += len(lv) + 1
                        else:
                            break
                    current          = ov_lines + [line]
                    cur_chars        = sum(len(lv) + 1 for lv in current)
                    start_line_offset = line_num - len(ov_lines)
                else:
                    if not current:
                        start_line_offset = line_num
                    current.append(line)
                    cur_chars += ll

            # Flush remaining text in this block
            if current:
                txt = "\n".join(current).strip()
                if txt:
                    s = cumulative_lines + start_line_offset
                    e = cumulative_lines + start_line_offset + len(current) - 1
                    chunks.append(_make_chunk(txt, doc["filename"], chunk_index, s, e))
                    chunk_index += 1
            cumulative_lines += len(lines)

        elif block["type"] == "table":
            # rich_blocks store DataFrame as "content"; table_to_text expects "df"
            tbl_arg    = {**block, "df": block["content"]} if "df" not in block else block
            table_text = table_to_text(tbl_arg)
            start_abs  = cumulative_lines + 1
            chunks.append({
                "chunk_id":    f"{doc['filename']}::table_{chunk_index}",
                "filename":    doc["filename"],
                "chunk_index": chunk_index,
                "start_line":  start_abs,
                "end_line":    start_abs,
                "text":        table_text,
                "char_count":  len(table_text),
                "word_count":  len(table_text.split()),
                "is_table":    True,
                "table_name":  block.get("label", ""),
                "source":      block.get("source", ""),
            })
            chunk_index      += 1
            cumulative_lines += 1

    return chunks


def chunk_document(doc: Dict[str, Any], chunk_size: int = 700,
                   overlap: int = 120) -> List[Dict[str, Any]]:
    """Plain line-based chunking — used as fallback when no rich_blocks exist."""
    text     = doc.get("raw_text", "")
    filename = doc.get("filename", "unknown")
    if not text.strip():
        return []
    lines = text.split("\n")
    return _chunk_by_lines(lines, filename, chunk_size, overlap)


def chunk_all_documents(documents: List[Dict], chunk_size: int = 700,
                         overlap: int = 120) -> List[Dict]:
    """
    Chunk all documents.  Uses structure-aware chunking when rich_blocks
    are present (PDF, DOCX), plain line chunking otherwise.

    NOTE: This is the ONLY definition of chunk_all_documents — the old code
    had a duplicate that silently discarded the rich_blocks logic.
    """
    all_chunks = []
    for doc in documents:
        if doc.get("error"):
            continue
        if doc.get("rich_blocks"):
            chunks = chunk_document_preserve_structure(doc, chunk_size, overlap)
        else:
            chunks = chunk_document(doc, chunk_size, overlap)
        all_chunks.extend(chunks)
    return all_chunks


# ── Internal helpers ──────────────────────────────────────────────────────────

def _chunk_by_lines(lines, filename, chunk_size, overlap):
    chunks, idx       = [], 0
    current, cur_chars, start_line = [], 0, 1

    for line_num, line in enumerate(lines, start=1):
        ll = len(line) + 1
        if cur_chars + ll > chunk_size and current:
            txt      = "\n".join(current).strip()
            end_line = start_line + len(current) - 1
            if txt:
                chunks.append(_make_chunk(txt, filename, idx, start_line, end_line))
                idx += 1
            ov_lines, ov_chars = [], 0
            for lv in reversed(current):
                if ov_chars + len(lv) + 1 <= overlap:
                    ov_lines.insert(0, lv); ov_chars += len(lv) + 1
                else:
                    break
            current    = ov_lines + [line]
            cur_chars  = sum(len(lv) + 1 for lv in current)
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
    n = (model_name or "").lower()

    # Large / cloud models — big context windows
    # return {"chunk_size": 1800, "overlap": 280, "max_tokens": 4096, ...}  # extra-large variant
    if any(x in n for x in ["opus", "large", "gpt-4", "70b", "72b", "34b",
                             "sonnet", "claude-3", "mistral-large", "mixtral"]):
        return {"chunk_size": 1400, "overlap": 220, "max_tokens": 4096,
                "label": "Large model — 1400c · 220c overlap · 4096 tokens"}

    # Medium models
    # return {"chunk_size": 800, "overlap": 130, "max_tokens": 2048, ...}  # conservative variant
    elif any(x in n for x in ["medium", "13b", "codestral"]):
        return {"chunk_size": 1000, "overlap": 160, "max_tokens": 3072,
                "label": "Mid model — 1000c · 160c overlap · 3072 tokens"}

    # Small / local models — tight context windows
    # return {"chunk_size": 400, "overlap": 60, "max_tokens": 512, ...}  # very small variant
    elif any(x in n for x in ["haiku", "phi", "mini", "gemma", "1b", "2b", "3b", "4b",
                               "7b", "llama2", "llama3.2", "orca", "tiny"]):
        return {"chunk_size": 600, "overlap": 80, "max_tokens": 1024,
                "label": "Small model — 600c · 80c overlap · 1024 tokens"}

    elif "ollama" in (backend_type or "").lower():
        return {"chunk_size": 700, "overlap": 110, "max_tokens": 2048,
                "label": "Ollama — 700c · 110c overlap · 2048 tokens"}

    # Default
    return {"chunk_size": 900, "overlap": 150, "max_tokens": 2048,
            "label": "Default — 900c · 150c overlap · 2048 tokens"}