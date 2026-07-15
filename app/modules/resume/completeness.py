"""Deeper "is this actually enough to write a good resume" checks.

`required_fields` on the vertical config only verifies a top-level key is
present (e.g. "work_experience" is a non-empty list) - it can't tell that the
list it found only has a company name and no job title/dates, or that there's
no professional summary to work with. This module adds those checks as an
`extra_missing_check` hook so the normal clarify/resume loop asks about them
too, instead of silently generating a thin resume.

Each check returns a *virtual* field name (not necessarily a literal key in
the output schema) the moment it detects a gap, and skips itself once the
user has already answered that virtual field (i.e. `extracted[field]` is
truthy) - the raw text answer is passed to the generation model alongside
everything else, which is enough for it to fill in the details even though it
isn't restructured into the nested schema.
"""

FIELD_JOB_TITLES_AND_DATES = "job_title_and_dates"
FIELD_SUMMARY = "career_summary"
FIELD_ACHIEVEMENTS = "key_achievements"

FIELD_HINTS = {
    "full_name": "the candidate's full name",
    "email": "the candidate's email address",
    "work_experience": "their work history - employer, role, and roughly when they worked there",
    "education": "their education history - degree/qualification, school, and dates (or 'none' if not applicable)",
    "skills": "a list of their key skills or tools they're proficient in",
    FIELD_JOB_TITLES_AND_DATES: (
        "the exact job title and start/end dates for each role already mentioned"
    ),
    FIELD_SUMMARY: (
        "a 2-3 sentence professional summary or elevator pitch about their career"
    ),
    FIELD_ACHIEVEMENTS: (
        "1-3 specific, measurable achievements or results from their work experience "
        "(e.g. numbers, impact, awards)"
    ),
}

# Pre-written question text per field, in every language the vertical
# supports ("en"/"ar") - see `VerticalConfig.field_questions`. This is the
# *entire* set of fields resume's `required_fields` + `extra_missing_check`
# can ever ask about, so there is no case where the clarify node needs an
# LLM to phrase one: every field it will ever see already has a hand-written
# question here.
FIELD_QUESTIONS = {
    "full_name": {
        "en": "What's your full name?",
        "ar": "ما هو اسمك الكامل؟",
    },
    "email": {
        "en": "What's your email address?",
        "ar": "ما هو بريدك الإلكتروني؟",
    },
    "work_experience": {
        "en": "Tell me about your work history - employer, role, and roughly when you worked there.",
        "ar": "أخبرني عن تاريخك الوظيفي - جهة العمل والمنصب وتقريباً متى عملت هناك.",
    },
    "education": {
        "en": "Tell me about your education - degree/qualification, school, and dates (or say 'none' if not applicable).",
        "ar": "أخبرني عن تعليمك - الشهادة، والمدرسة، والتواريخ (أو قل 'لا يوجد' إن لم ينطبق).",
    },
    "skills": {
        "en": "What are your key skills or tools you're proficient in?",
        "ar": "ما هي مهاراتك الأساسية أو الأدوات التي تتقنها؟",
    },
    FIELD_JOB_TITLES_AND_DATES: {
        "en": "Could you give me the exact job title and start/end dates for each role you mentioned?",
        "ar": "هل يمكنك إعطائي المسمى الوظيفي الدقيق وتواريخ البدء/الانتهاء لكل دور ذكرته؟",
    },
    FIELD_SUMMARY: {
        "en": "Could you give me a short 2-3 sentence professional summary or elevator pitch about your career?",
        "ar": "هل يمكنك تزويدي بملخص مهني قصير (2-3 جمل) عن مسارك المهني؟",
    },
    FIELD_ACHIEVEMENTS: {
        "en": "What are 1-3 specific, measurable achievements or results from your work (e.g. numbers, impact, awards)?",
        "ar": "ما هي 1-3 إنجازات أو نتائج محددة وقابلة للقياس من عملك (مثل الأرقام أو الأثر أو الجوائز)؟",
    },
}

# Display names for the fields conflict-detection can flag (see
# EXTRACTION_PROMPT's `conflicts` convention) - used to phrase a
# conflict::<field> question without needing a model, e.g. "I found
# different information for your email: ...".
FIELD_DISPLAY_NAMES = {
    "full_name": {"en": "your name", "ar": "اسمك"},
    "email": {"en": "your email", "ar": "بريدك الإلكتروني"},
    "phone": {"en": "your phone number", "ar": "رقم هاتفك"},
    "location": {"en": "your location", "ar": "موقعك"},
    "linkedin": {"en": "your LinkedIn", "ar": "حسابك على لينكد إن"},
    "portfolio_url": {"en": "your portfolio URL", "ar": "رابط ملفك الشخصي"},
}


def _entries_missing_title_or_dates(work_experience: object) -> bool:
    if not isinstance(work_experience, list):
        return False
    for entry in work_experience:
        if not isinstance(entry, dict):
            continue
        has_title = bool(entry.get("job_title"))
        has_dates = bool(entry.get("start_date") or entry.get("end_date"))
        if not has_title or not has_dates:
            return True
    return False


def check_resume_completeness(extracted: dict) -> list[str]:
    missing: list[str] = []

    if not extracted.get(FIELD_JOB_TITLES_AND_DATES) and _entries_missing_title_or_dates(
        extracted.get("work_experience")
    ):
        missing.append(FIELD_JOB_TITLES_AND_DATES)

    if not extracted.get(FIELD_SUMMARY) and not extracted.get("summary"):
        missing.append(FIELD_SUMMARY)

    if not extracted.get(FIELD_ACHIEVEMENTS) and extracted.get("work_experience"):
        missing.append(FIELD_ACHIEVEMENTS)

    return missing
