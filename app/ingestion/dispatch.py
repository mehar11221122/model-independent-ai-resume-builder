"""Picks the right loader for an uploaded file based on its extension."""
from pathlib import Path

from app.ingestion.docx_loader import load_docx
from app.ingestion.models import ExtractedDocument
from app.ingestion.ocr_loader import load_image
from app.ingestion.pdf_loader import load_pdf
from app.ingestion.text_loader import load_text

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


def load_any(filename: str, data: bytes) -> ExtractedDocument:
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return load_pdf(filename, data)
    if ext == ".docx":
        return load_docx(filename, data)
    if ext in IMAGE_EXTENSIONS:
        return load_image(filename, data)
    if ext in {".txt", ".md"}:
        return load_text(filename, data.decode("utf-8", errors="ignore"))

    raise ValueError(f"Unsupported file type: {ext or '(no extension)'}")
