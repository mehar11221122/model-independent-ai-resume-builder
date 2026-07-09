import io

import docx

from app.ingestion.dispatch import load_any
from app.ingestion.docx_loader import load_docx
from app.ingestion.merge import merge_documents
from app.ingestion.models import InputKind
from app.ingestion.text_loader import load_text


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
