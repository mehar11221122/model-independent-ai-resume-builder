"""PDF text/layout extraction.

Uses PyMuPDF (fast, good general-purpose text extraction) with pdfplumber as
a fallback for PDFs where PyMuPDF returns little/no text (e.g. some
table-heavy layouts pdfplumber handles better). If both come back empty -
the classic sign of a scanned/image-only PDF with no embedded text layer -
each page is rasterized and run through the same OCR loader used for
uploaded images, so a scanned resume is still readable instead of just
producing a warning and an empty document.
"""
import io

import fitz  # PyMuPDF
import pdfplumber

from app.ingestion.models import ExtractedDocument, InputKind
from app.ingestion.ocr_loader import load_image

# Render scanned pages at a higher-than-screen DPI so small print stays
# legible to the OCR engine; 72 is PDF's native DPI baseline.
_OCR_RENDER_DPI = 200


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


def _extract_with_ocr(source_name: str, data: bytes) -> tuple[str, list[str]]:
    """Rasterizes each page to a PNG and OCRs it - the last-resort path for
    scanned/image-only PDFs with no embedded text layer at all."""
    text_parts: list[str] = []
    ocr_warnings: list[str] = []
    zoom = _OCR_RENDER_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(stream=data, filetype="pdf") as doc:
        for page_number, page in enumerate(doc, start=1):
            png_bytes = page.get_pixmap(matrix=matrix).tobytes("png")
            try:
                page_doc = load_image(f"{source_name} (page {page_number}, OCR)", png_bytes)
            except Exception as exc:  # noqa: BLE001
                ocr_warnings.append(f"OCR failed on page {page_number}: {exc}")
                continue
            if page_doc.raw_text:
                text_parts.append(page_doc.raw_text)
            ocr_warnings.extend(page_doc.warnings)

    return "\n".join(text_parts).strip(), ocr_warnings


def load_pdf(source_name: str, data: bytes) -> ExtractedDocument:
    warnings: list[str] = []
    text = _extract_with_pymupdf(data)

    if not text:
        warnings.append("PyMuPDF returned no text; fell back to pdfplumber.")
        text = _extract_with_pdfplumber(data)

    if not text:
        warnings.append(
            "No extractable text layer found; the PDF looks like a scanned "
            "image - falling back to OCR."
        )
        try:
            text, ocr_warnings = _extract_with_ocr(source_name, data)
            warnings.extend(ocr_warnings)
            if not text:
                warnings.append("OCR fallback also found no readable text on any page.")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"OCR fallback failed: {exc}")

    return ExtractedDocument(
        source_name=source_name, kind=InputKind.PDF, raw_text=text, warnings=warnings
    )
