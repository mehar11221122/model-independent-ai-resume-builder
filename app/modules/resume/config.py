from app.graph.vertical import VerticalConfig
from app.modules.resume.completeness import (
    FIELD_DISPLAY_NAMES,
    FIELD_HINTS,
    FIELD_QUESTIONS,
    check_resume_completeness,
)
from app.modules.resume.prompts import (
    CLARIFICATION_PROMPT,
    EXTRACTION_PROMPT,
    GENERATION_PROMPT,
)
from app.modules.resume.schema import ResumeOutput
from app.modules.resume.tools import RESUME_TOOLS, apply_deterministic_enrichment
from app.modules.resume.validation import RESUME_VALIDATORS

RESUME_VERTICAL = VerticalConfig(
    name="resume",
    output_schema=ResumeOutput,
    required_fields=["full_name", "email", "work_experience", "education", "skills"],
    extraction_prompt=EXTRACTION_PROMPT,
    generation_prompt=GENERATION_PROMPT,
    clarification_prompt=CLARIFICATION_PROMPT,
    extra_validators=RESUME_VALIDATORS,
    extra_missing_check=check_resume_completeness,
    field_hints=FIELD_HINTS,
    field_questions=FIELD_QUESTIONS,
    conflict_field_labels=FIELD_DISPLAY_NAMES,
    tools=RESUME_TOOLS,
    deterministic_enrichment=apply_deterministic_enrichment,
    max_retries=2,
)
