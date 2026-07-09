from app.ingestion.models import ExtractedDocument, InputKind


def load_text(source_name: str, content: str) -> ExtractedDocument:
    return ExtractedDocument(source_name=source_name, kind=InputKind.TEXT, raw_text=content)
