from app.graph.vertical import VerticalConfig
from app.modules.resume.prompts import (
    CLARIFICATION_PROMPT,
    EXTRACTION_PROMPT,
    GENERATION_PROMPT,
)
from app.modules.resume.schema import ResumeOutput
from app.modules.resume.validation import RESUME_VALIDATORS

RESUME_VERTICAL = VerticalConfig(
    name="resume",
    output_schema=ResumeOutput,
    required_fields=["full_name", "email", "work_experience"],
    extraction_prompt=EXTRACTION_PROMPT,
    generation_prompt=GENERATION_PROMPT,
    clarification_prompt=CLARIFICATION_PROMPT,
    extra_validators=RESUME_VALIDATORS,
    max_retries=2,
)
