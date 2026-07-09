from typing import Any, Literal

from pydantic import BaseModel


class SessionResponse(BaseModel):
    thread_id: str
    status: Literal["in_progress", "awaiting_clarification", "completed", "failed"]
    follow_up_questions: list[str] = []
    structured_output: dict[str, Any] | None = None
    validation_errors: list[str] = []


class AnswersRequest(BaseModel):
    answers: dict[str, str]
