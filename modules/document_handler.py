"""
Document Handler Module
Handles loading and extracting text from PDF, Word (.docx), and Excel (.xlsx) files.
Supports batch uploads and returns structured document objects.
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
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False


def load_document(uploaded_file) -> Dict[str, Any]:
    """
    Load a single uploaded file and extract its text content.
    Returns a structured dict with filename, type, raw text, and pages.
    """
    filename = uploaded_file.name
    file_ext = filename.rsplit(".", 1)[-1].lower()
    file_bytes = uploaded_file.read()

    doc = {
        "filename": filename,
        "type": file_ext,
        "raw_text": "",
        "pages": [],       # List of page/sheet texts
        "metadata": {},
        "error": None
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


def _load_pdf(file_bytes: bytes) -> Dict[str, Any]:
    """Extract text from PDF using PyPDF2."""
    if not PDF_AVAILABLE:
        return {"error": "PyPDF2 not installed. Run: pip install PyPDF2"}

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages = []
    raw_text_parts = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append({"page_number": i + 1, "text": text.strip()})
        raw_text_parts.append(text)

    return {
        "raw_text": "\n\n".join(raw_text_parts),
        "pages": pages,
        "metadata": {"page_count": len(reader.pages)}
    }


def _load_docx(file_bytes: bytes) -> Dict[str, Any]:
    """Extract text from Word documents paragraph by paragraph."""
    if not DOCX_AVAILABLE:
        return {"error": "python-docx not installed. Run: pip install python-docx"}

    docx = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in docx.paragraphs if p.text.strip()]
    
    # Treat each paragraph as a "page" chunk for granularity
    pages = [{"page_number": i + 1, "text": p} for i, p in enumerate(paragraphs)]

    return {
        "raw_text": "\n\n".join(paragraphs),
        "pages": pages,
        "metadata": {"paragraph_count": len(paragraphs)}
    }


def _load_excel(file_bytes: bytes) -> Dict[str, Any]:
    """Extract text from all sheets of an Excel file."""
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    pages = []
    raw_parts = []

    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name).fillna("")
        # Convert sheet to readable text
        text = f"[Sheet: {sheet_name}]\n{df.to_string(index=False)}"
        pages.append({"page_number": sheet_name, "text": text})
        raw_parts.append(text)

    return {
        "raw_text": "\n\n".join(raw_parts),
        "pages": pages,
        "metadata": {"sheet_count": len(xls.sheet_names), "sheets": xls.sheet_names}
    }


def batch_load_documents(uploaded_files) -> List[Dict[str, Any]]:
    """
    Load multiple uploaded files in batch.
    Returns list of document dicts, skipping failed loads with error info.
    """
    documents = []
    for f in uploaded_files:
        doc = load_document(f)
        documents.append(doc)
    return documents