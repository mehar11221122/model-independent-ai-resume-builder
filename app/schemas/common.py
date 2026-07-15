from typing import Any, Literal

from pydantic import BaseModel, Field


class FollowUpQuestion(BaseModel):
    """One AI-generated clarification question for a specific missing or
    invalid field, optionally with quick-pick `options` (e.g. for resolving
    a detected conflict between sources)."""

    field: str = Field(description="Key to answer this under in the next /answers call.")
    question: str = Field(description="Human-readable question text, in the session's language.")
    options: list[str] = Field(default=[], description="Quick-pick choices, if any were known ahead of time.")


class SessionResponse(BaseModel):
    """Current state of a resume-building session - returned by every
    endpoint below so callers can poll or resume with the same shape."""

    thread_id: str = Field(description="Opaque session id - pass this to the answers/status endpoints.")
    status: Literal["in_progress", "awaiting_clarification", "completed", "failed"] = Field(
        description=(
            "'awaiting_clarification' means follow_up_questions must be answered next; "
            "'completed' means structured_output is ready; 'failed' means validation_errors "
            "explains why after exhausting retries."
        )
    )
    follow_up_questions: list[FollowUpQuestion] = Field(
        default=[], description="Non-empty only when status is 'awaiting_clarification'."
    )
    structured_output: dict[str, Any] | None = Field(
        default=None, description="The generated resume, matching app.modules.resume.schema.ResumeOutput."
    )
    validation_errors: list[str] = Field(default=[], description="Populated only when status is 'failed'.")


class AnswersRequest(BaseModel):
    """Body for POST /resume/sessions/{thread_id}/answers."""

    answers: dict[str, str] = Field(
        description=(
            "Map of field key -> free-text answer, using the exact `field` values from the "
            "follow_up_questions you were just given."
        )
    )
