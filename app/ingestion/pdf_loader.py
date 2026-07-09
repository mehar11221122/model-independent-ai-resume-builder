"""PDF text/layout extraction.

Uses PyMuPDF (fast, good general-purpose text extraction) with pdfplumber as
a fallback for PDFs where PyMuPDF returns little/no text (e.g. some
table-heavy layouts pdfplumber handles better).
"""
import io

import fitz  # PyMuPDF
import pdfplumber

from app.ingestion.models import ExtractedDocument, InputKind


def _extract_with_pymupdf(data: bytes) -> str:
    text_parts: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


def _extract_with_pdfplumber(data: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts).strip()


def load_pdf(source_name: str, data: bytes) -> ExtractedDocument:
    warnings: list[str] = []
    text = _extract_with_pymupdf(data)

    if not text:
        warnings.append("PyMuPDF returned no text; fell back to pdfplumber.")
        text = _extract_with_pdfplumber(data)

    if not text:
        warnings.append("No extractable text found; the PDF may be a scanned image.")

    return ExtractedDocument(
        source_name=source_name, kind=InputKind.PDF, raw_text=text, warnings=warnings
    )
