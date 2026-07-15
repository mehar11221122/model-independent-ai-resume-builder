import io
from unittest.mock import patch

import docx
import fitz  # PyMuPDF

from app.ingestion.dispatch import load_any
from app.ingestion.docx_loader import load_docx
from app.ingestion.merge import merge_documents
from app.ingestion.models import InputKind
from app.ingestion.ocr_loader import load_image
from app.ingestion.pdf_loader import load_pdf
from app.ingestion.text_loader import load_text


def _make_text_pdf_bytes(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line)
        y += 20
    data = doc.tobytes()
    doc.close()
    return data


def _make_blank_image_pdf_bytes() -> bytes:
    """A PDF page with a rendered (rasterized) image and no text layer at
    all - the scanned-document case OCR fallback needs to handle."""
    doc = fitz.open()
    page = doc.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, (0, 0, 100, 100))
    pixmap.set_rect(pixmap.irect, (255, 255, 255))
    page.insert_image(fitz.Rect(0, 0, 100, 100), pixmap=pixmap)
    data = doc.tobytes()
    doc.close()
    return data


def _make_blank_image_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (50, 50), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_load_text():
    doc = load_text("note.txt", "Hello world")
    assert doc.kind == InputKind.TEXT
    assert doc.raw_text == "Hello world"


def test_load_docx_extracts_paragraphs():
    data = _make_docx_bytes(["Jane Sample", "Software Engineer"])
    doc = load_docx("resume.docx", data)
    assert doc.kind == InputKind.DOCX
    assert "Jane Sample" in doc.raw_text
    assert "Software Engineer" in doc.raw_text
    assert doc.warnings == []


def test_load_docx_empty_has_warning():
    data = _make_docx_bytes([])
    doc = load_docx("empty.docx", data)
    assert doc.warnings


def test_dispatch_routes_by_extension():
    data = _make_docx_bytes(["content"])
    doc = load_any("resume.docx", data)
    assert doc.kind == InputKind.DOCX


def test_dispatch_rejects_unsupported_extension():
    try:
        load_any("resume.xyz", b"data")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_merge_documents_labels_each_source():
    docs = [load_text("a.txt", "Alpha"), load_text("b.txt", "Beta")]
    merged = merge_documents(docs)
    assert "a.txt" in merged
    assert "b.txt" in merged
    assert "Alpha" in merged
    assert "Beta" in merged


def test_merge_documents_collapses_excessive_whitespace_noise():
    noisy = "Jane Sample\n\n\n\n\nSoftware   Engineer\t\t\n\n\n\nPython, SQL"
    merged = merge_documents([load_text("a.txt", noisy)])
    assert "\n\n\n" not in merged
    assert "Software Engineer" in merged
    assert "Jane Sample" in merged
    assert "Python, SQL" in merged


def test_merge_documents_truncates_pathologically_long_source():
    huge = "word " * 10_000  # ~50k chars, well over the 20k cap
    merged = merge_documents([load_text("huge.txt", huge)])
    # Header + truncated body should stay near the cap, not balloon to ~50k.
    assert len(merged) < 21_000


def test_load_pdf_extracts_text_layer():
    data = _make_text_pdf_bytes(["Jane Sample", "Software Engineer"])
    doc = load_pdf("resume.pdf", data)
    assert doc.kind == InputKind.PDF
    assert "Jane Sample" in doc.raw_text
    assert "Software Engineer" in doc.raw_text
    assert doc.warnings == []


def test_dispatch_routes_pdf_by_extension():
    data = _make_text_pdf_bytes(["content"])
    doc = load_any("resume.pdf", data)
    assert doc.kind == InputKind.PDF
    assert "content" in doc.raw_text


@patch("app.ingestion.ocr_loader._ocr_tesseract")
def test_load_pdf_falls_back_to_ocr_for_scanned_pages(mock_ocr):
    mock_ocr.return_value = "Scanned Candidate Name"
    data = _make_blank_image_pdf_bytes()
    doc = load_pdf("scanned.pdf", data)

    assert doc.kind == InputKind.PDF
    assert "Scanned Candidate Name" in doc.raw_text
    assert any("scanned" in w.lower() for w in doc.warnings)
    mock_ocr.assert_called_once()


@patch("app.ingestion.ocr_loader._ocr_tesseract")
def test_load_pdf_ocr_fallback_with_no_readable_text_warns(mock_ocr):
    mock_ocr.return_value = ""
    data = _make_blank_image_pdf_bytes()
    doc = load_pdf("blank.pdf", data)

    assert doc.raw_text == ""
    assert any("no readable text" in w.lower() for w in doc.warnings)


@patch("app.ingestion.ocr_loader._ocr_tesseract")
def test_load_image_ocr_extracts_text(mock_ocr):
    mock_ocr.return_value = "Jane Sample\nSoftware Engineer"
    doc = load_image("photo.png", _make_blank_image_bytes())

    assert doc.kind == InputKind.IMAGE
    assert doc.raw_text == "Jane Sample\nSoftware Engineer"
    assert doc.warnings == []


@patch("app.ingestion.ocr_loader._ocr_tesseract")
def test_load_image_empty_ocr_result_has_warning(mock_ocr):
    mock_ocr.return_value = ""
    doc = load_image("blank.png", _make_blank_image_bytes())
    assert doc.warnings


def test_dispatch_routes_image_by_extension():
    with patch("app.ingestion.ocr_loader._ocr_tesseract", return_value="text"):
        doc = load_any("photo.jpg", _make_blank_image_bytes())
    assert doc.kind == InputKind.IMAGE


def test_ocr_backend_google_vision_raises_not_implemented():
    from app.ingestion.ocr_loader import _ocr_google_vision

    try:
        _ocr_google_vision(b"data")
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass


def test_ocr_backend_aws_textract_raises_not_implemented():
    from app.ingestion.ocr_loader import _ocr_aws_textract

    try:
        _ocr_aws_textract(b"data")
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass
