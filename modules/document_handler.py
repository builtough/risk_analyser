"""
Document Handler Module
Handles loading and extracting text from PDF, Word (.docx), and Excel files.
Produces rich_blocks for PDF, DOCX, and Excel so the viewer can render tables as grids
inline with text content, rather than flattening everything to line-by-line text.
"""

import io
import pandas as pd
from typing import List, Dict, Any

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    from docx.oxml.ns import qn
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

# Import helpers from table_extractor to reuse header promotion and fake table detection
from modules.table_extractor import _promote_header, _is_fake_table


def load_document(uploaded_file) -> Dict[str, Any]:
    filename  = uploaded_file.name
    file_ext  = filename.rsplit(".", 1)[-1].lower()
    file_bytes = uploaded_file.read()

    doc = {
        "filename":    filename,
        "type":        file_ext,
        "raw_text":    "",
        "pages":       [],
        "rich_blocks": [],   # ordered list of {type: text|table, content: str|DataFrame}
        "metadata":    {},
        "error":       None,
    }

    try:
        if file_ext == "pdf":
            doc.update(_load_pdf(file_bytes))
        elif file_ext in ("docx", "doc"):
            doc.update(_load_docx(file_bytes))
        elif file_ext in ("xlsx", "xls"):
            doc.update(_load_excel(file_bytes))
        else:
            doc["error"] = f"Unsupported file format: {file_ext}"
    except Exception as e:
        doc["error"] = f"Failed to load {filename}: {str(e)}"

    return doc


# ── PDF ───────────────────────────────────────────────────────────────────────

def _load_pdf(file_bytes: bytes) -> Dict[str, Any]:
    if not PDF_AVAILABLE:
        return {"error": "PyPDF2 not installed. Run: pip install PyPDF2"}

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages, raw_parts, rich_blocks = [], [], []
    page_counter = 0

    # Use pdfplumber if available for table extraction
    pdf_plumber = None
    if PDFPLUMBER_AVAILABLE:
        pdf_plumber = pdfplumber.open(io.BytesIO(file_bytes))

    for i, page in enumerate(reader.pages):
        # Extract text via PyPDF2
        text = page.extract_text() or ""
        pages.append({"page_number": i + 1, "text": text.strip()})
        raw_parts.append(text)

        # Text block for this page
        rich_blocks.append({
            "type": "text",
            "content": text,
            "label": f"Page {i + 1}",
            "page": i + 1,
        })

        # Extract tables with pdfplumber if available
        if pdf_plumber:
            plumber_page = pdf_plumber.pages[i]
            # Try both lattice and stream strategies
            tables = plumber_page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            }) or plumber_page.extract_tables({
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
            })

            for t_idx, table_data in enumerate(tables):
                if not table_data:
                    continue
                # Convert to DataFrame
                df = pd.DataFrame(table_data)
                # Basic cleaning: drop empty rows/columns
                df = df.replace("", pd.NA).dropna(how="all").dropna(axis=1, how="all").fillna("")
                if df.empty or df.shape[0] < 2 or df.shape[1] < 2:
                    continue
                # Promote header if first row looks like headers
                df = _promote_header(df)
                if _is_fake_table(df):
                    continue
                rich_blocks.append({
                    "type": "table",
                    "content": df,
                    "label": f"Page {i + 1}, Table {t_idx + 1}",
                    "page": i + 1,
                    "source": f"Page {i + 1}",
                })

    if pdf_plumber:
        pdf_plumber.close()

    full_text = "\n\n".join(raw_parts)
    return {
        "raw_text":    full_text,
        "pages":       pages,
        "rich_blocks": rich_blocks,
        "metadata":    {"page_count": len(reader.pages)},
    }


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _load_docx(file_bytes: bytes) -> Dict[str, Any]:
    """
    Walk the document body in XML order so tables appear inline with text.
    rich_blocks = ordered list of:
      {"type": "text",  "content": str}
      {"type": "table", "content": DataFrame, "label": str}
    """
    if not DOCX_AVAILABLE:
        return {"error": "python-docx not installed. Run: pip install python-docx"}

    docx        = DocxDocument(io.BytesIO(file_bytes))
    body        = docx.element.body
    blocks      = []
    text_parts  = []   # accumulates text for raw_text
    text_buffer = []   # accumulates current paragraph run
    table_idx   = 0

    for child in body.iterchildren():
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            # Paragraph — collect text
            para_text = "".join(r.text for r in child.iter(qn("w:t"))
                                if r.text).strip()
            if para_text:
                text_buffer.append(para_text)

        elif tag == "tbl":
            # Flush accumulated text before the table
            if text_buffer:
                chunk = "\n".join(text_buffer)
                blocks.append({"type": "text", "content": chunk})
                text_parts.append(chunk)
                text_buffer = []

            # Extract table into a DataFrame
            rows = []
            for tr in child.iter(qn("w:tr")):
                row_cells = []
                for tc in tr.iter(qn("w:tc")):
                    cell_text = "".join(
                        r.text for r in tc.iter(qn("w:t")) if r.text
                    ).strip()
                    row_cells.append(cell_text)
                if row_cells:
                    rows.append(row_cells)

            if rows:
                df = _rows_to_df(rows)
                if df is not None and not df.empty:
                    label = f"Table {table_idx + 1}"
                    blocks.append({"type": "table", "content": df, "label": label})
                    # Also add table as text for raw_text / chunking
                    text_parts.append(_df_to_plain(df, label))
                    table_idx += 1

    # Flush any remaining text
    if text_buffer:
        chunk = "\n".join(text_buffer)
        blocks.append({"type": "text", "content": chunk})
        text_parts.append(chunk)

    raw_text = "\n\n".join(text_parts)
    pages    = [{"page_number": i + 1, "text": b["content"] if b["type"] == "text"
                 else _df_to_plain(b["content"], b.get("label", ""))}
                for i, b in enumerate(blocks)]

    return {
        "raw_text":    raw_text,
        "pages":       pages,
        "rich_blocks": blocks,
        "metadata":    {
            "paragraph_count": sum(1 for b in blocks if b["type"] == "text"),
            "table_count":     table_idx,
        },
    }


def _rows_to_df(rows: list) -> pd.DataFrame:
    """Convert a list-of-lists into a DataFrame with header promotion."""
    if not rows:
        return None
    max_cols = max(len(r) for r in rows)
    padded   = [r + [""] * (max_cols - len(r)) for r in rows]
    df       = pd.DataFrame(padded)

    # Promote header if first row looks like headers
    first = df.iloc[0].astype(str).str.strip().tolist()
    non_empty = sum(bool(x) for x in first)
    if non_empty >= max(2, int(0.5 * len(first))):
        seen, new_cols = {}, []
        for x in first:
            base = x if x else "Col"
            cnt  = seen.get(base, 0)
            seen[base] = cnt + 1
            new_cols.append(base if cnt == 0 else f"{base}_{cnt + 1}")
        df = df.iloc[1:].copy()
        df.columns = new_cols
        df.reset_index(drop=True, inplace=True)

    df.replace("", pd.NA, inplace=True)
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    df.fillna("", inplace=True)
    return df


def _df_to_plain(df: pd.DataFrame, label: str = "") -> str:
    """Convert a DataFrame to plain text for raw_text / chunking."""
    header = f"[{label}] " if label else ""
    return header + df.to_string(index=False)


# ── Excel ─────────────────────────────────────────────────────────────────────

def _load_excel(file_bytes: bytes) -> Dict[str, Any]:
    """
    Each sheet becomes one rich_block of type 'table' with a DataFrame.
    raw_text also contains a plain-text version for chunking/search.
    """
    xls       = pd.ExcelFile(io.BytesIO(file_bytes))
    pages     = []
    raw_parts = []
    blocks    = []

    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name).fillna("")

        # Clean up the DataFrame
        df = df.loc[:, (df.astype(str).ne("")).any(axis=0)]
        df = df.loc[(df.astype(str).ne("")).any(axis=1)]
        df.reset_index(drop=True, inplace=True)

        plain = f"[Sheet: {sheet_name}]\n{df.to_string(index=False)}"
        pages.append({"page_number": sheet_name, "text": plain})
        raw_parts.append(plain)
        blocks.append({
            "type":    "table",
            "content": df,
            "label":   f"Sheet: {sheet_name}",
            "sheet":   sheet_name,
        })

    return {
        "raw_text":    "\n\n".join(raw_parts),
        "pages":       pages,
        "rich_blocks": blocks,
        "metadata":    {"sheet_count": len(xls.sheet_names), "sheets": xls.sheet_names},
    }


def batch_load_documents(uploaded_files) -> List[Dict[str, Any]]:
    documents = []
    for f in uploaded_files:
        doc = load_document(f)
        documents.append(doc)
    return documents