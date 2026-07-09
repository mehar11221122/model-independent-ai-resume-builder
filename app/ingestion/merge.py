"""Merge multiple extracted documents into one coherent text blob.

This is a simple, deterministic pre-merge (concatenation with source
labels). The LangGraph "Information Merging" node uses an LLM on top of this
to reconcile/deduplicate content semantically - this function just prepares
clean, labeled input for that step.
"""
from app.ingestion.models import ExtractedDocument


def merge_documents(documents: list[ExtractedDocument]) -> str:
    blocks = []
    for doc in documents:
        header = f"--- Source: {doc.source_name} ({doc.kind.value}) ---"
        blocks.append(f"{header}\n{doc.raw_text}".strip())
    return "\n\n".join(blocks)
