"""Merge multiple extracted documents into one coherent text blob.

This is a deterministic pre-merge only: concatenation with source labels so
the extraction LLM can see exactly where each fact came from. The actual
semantic reconciliation - deduplicating overlapping facts, and flagging
genuine disagreements between sources - happens inside the extraction
node's prompt (`EXTRACTION_PROMPT`) as it reads this labeled text in a
single pass, not in a separate graph node. Anything the model can't safely
resolve on its own is surfaced as a `conflicts` entry, which the engine
turns into a follow-up question via the same clarify/merge-answers loop
used for missing fields (see `app/graph/nodes.py::_detect_conflicts`).

Before concatenation, each source is cleaned and capped (see `_clean_text`/
`_MAX_CHARS_PER_SOURCE` below) - the extraction model gains nothing from
re-reading OCR/PDF whitespace artifacts or a pathologically long upload, it
only costs input tokens on every single call downstream, so this is the
"focused context, not massive uncurated documents" principle applied at the
one choke point every source passes through regardless of type.
"""
import logging
import re

from app.ingestion.models import ExtractedDocument

logger = logging.getLogger(__name__)

# ~5k tokens - generous for even a multi-page resume/transcript, but a real
# ceiling against an accidental huge upload (e.g. a whole ebook attached by
# mistake) burning a proportionally huge extraction token bill for no
# benefit to resume quality.
_MAX_CHARS_PER_SOURCE = 20_000

_RUNS_OF_BLANK_LINES = re.compile(r"\n{3,}")
_RUNS_OF_SPACES_OR_TABS = re.compile(r"[ \t]+")


def _clean_text(text: str) -> str:
    """Strips token-wasting formatting noise (OCR's runs of blank lines,
    PDFs' repeated whitespace/page-break padding) without touching the
    actual words - never removes content, only redundant whitespace."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _RUNS_OF_SPACES_OR_TABS.sub(" ", text)
    text = _RUNS_OF_BLANK_LINES.sub("\n\n", text)
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _cap_length(text: str, source_name: str) -> str:
    if len(text) <= _MAX_CHARS_PER_SOURCE:
        return text
    logger.warning(
        "Source '%s' was %d chars - truncated to %d before extraction to "
        "avoid an oversized token bill for a single unusually long upload.",
        source_name, len(text), _MAX_CHARS_PER_SOURCE,
    )
    return text[:_MAX_CHARS_PER_SOURCE]


def merge_documents(documents: list[ExtractedDocument]) -> str:
    blocks = []
    for doc in documents:
        cleaned = _cap_length(_clean_text(doc.raw_text), doc.source_name)
        header = f"--- Source: {doc.source_name} ({doc.kind.value}) ---"
        blocks.append(f"{header}\n{cleaned}".strip())
    return "\n\n".join(blocks)
