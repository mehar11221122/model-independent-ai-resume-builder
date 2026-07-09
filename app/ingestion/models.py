from enum import Enum

from pydantic import BaseModel


class InputKind(str, Enum):
    TEXT = "text"
    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"


class ExtractedDocument(BaseModel):
    """Normalized output of any loader, regardless of source file type."""

    source_name: str
    kind: InputKind
    raw_text: str
    warnings: list[str] = []
    storage_uri: str | None = None
