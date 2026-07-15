"""Date-handling helpers for the resume vertical, used two ways:

1. `apply_deterministic_enrichment` - a plain function the tool-use node
   calls directly (see `VerticalConfig.deterministic_enrichment`) to
   normalize every date in `extracted_data` before generation. There is no
   real judgment call in "should this date be normalized" - it always
   should - so this runs unconditionally with zero LLM calls, which is
   both cheaper and more reliable than asking a free-tier model to decide.
2. `RESUME_TOOLS` (`normalize_date`/`compute_duration`, LangChain
   `@tool`-wrapped) - kept available for the engine's generic,
   model-mediated tool-use path (`app.graph.build_tool_use_node`'s
   `bind_tools` fallback), for any future flow that genuinely needs a model
   to decide which tool to call rather than always running one.
"""
from datetime import date

from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from langchain_core.tools import tool

_CURRENT_WORDS = {"present", "current", "now", "ongoing", "today"}


def _normalize_date_str(date_str: str) -> str:
    text = (date_str or "").strip()
    if not text:
        return text
    if text.isdigit() and len(text) == 4:
        return text
    try:
        parsed = date_parser.parse(text, default=date(1904, 1, 1))
    except (ValueError, OverflowError, TypeError):
        return text
    if parsed.year == 1904 and str(1904) not in text:
        # dateutil filled in a bogus year from our sentinel default - the
        # string had no real year in it, so don't fabricate one.
        return text
    return f"{parsed.year:04d}-{parsed.month:02d}"


def _compute_duration_str(start_date: str, end_date: str = "") -> str:
    start_text = (start_date or "").strip()
    if not start_text:
        return "unknown duration"
    try:
        start = date_parser.parse(start_text, default=date(1904, 1, 1))
    except (ValueError, OverflowError, TypeError):
        return "unknown duration"

    end_text = (end_date or "").strip().lower()
    if not end_text or end_text in _CURRENT_WORDS:
        end = date.today()
    else:
        try:
            end = date_parser.parse(end_date.strip(), default=date(1904, 1, 1))
        except (ValueError, OverflowError, TypeError):
            end = date.today()

    if end < start:
        start, end = end, start

    delta = relativedelta(end, start)
    parts = []
    if delta.years:
        parts.append(f"{delta.years} year{'s' if delta.years != 1 else ''}")
    if delta.months:
        parts.append(f"{delta.months} month{'s' if delta.months != 1 else ''}")
    return " ".join(parts) if parts else "less than a month"


@tool
def normalize_date(date_str: str) -> str:
    """Parse a loosely-formatted date (e.g. "March 2023", "Mar '23",
    "2023-03-01", "2022") and return it in canonical form: "YYYY-MM" if a
    month is known, otherwise just "YYYY". Returns the input unchanged if it
    can't be confidently parsed - never guesses wildly."""
    return _normalize_date_str(date_str)


@tool
def compute_duration(start_date: str, end_date: str = "") -> str:
    """Compute a human-readable duration (e.g. "2 years 3 months") between a
    start date and an end date, both loosely-formatted date strings. Pass an
    empty end_date, or one of "present"/"current"/"now"/"ongoing", to
    compute the duration up to today. Returns "unknown duration" if
    start_date can't be parsed."""
    return _compute_duration_str(start_date, end_date)


RESUME_TOOLS = [normalize_date, compute_duration]

_DATED_SECTIONS = ("work_experience", "education", "volunteer_experience")


def apply_deterministic_enrichment(extracted: dict) -> dict:
    """Normalizes every `start_date`/`end_date` across the dated repeatable
    sections, unconditionally and without any model involved - see the
    module docstring. Returns a new dict; never mutates the input.
    """
    updated = dict(extracted)
    for section in _DATED_SECTIONS:
        entries = updated.get(section)
        if not isinstance(entries, list):
            continue
        new_entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                new_entries.append(entry)
                continue
            entry = dict(entry)
            if entry.get("start_date"):
                entry["start_date"] = _normalize_date_str(entry["start_date"])
            if entry.get("end_date"):
                entry["end_date"] = _normalize_date_str(entry["end_date"])
            new_entries.append(entry)
        updated[section] = new_entries
    return updated
