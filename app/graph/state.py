from typing import Any, Literal, TypedDict


class EngineState(TypedDict, total=False):
    """Shared state that flows through every node of the LangGraph workflow.

    This is intentionally domain-agnostic - the same shape is used whether the
    active vertical is Resume, Marketing, Automotive, etc. Vertical-specific
    behavior comes from the VerticalConfig passed into the graph, not from
    extra fields here.
    """

    thread_id: str
    vertical: str
    language: str

    raw_documents: list[dict[str, Any]]
    merged_text: str

    extracted_data: dict[str, Any]
    missing_fields: list[str]
    follow_up_questions: list[str]
    user_answers: dict[str, str]

    structured_output: dict[str, Any] | None
    validation_errors: list[str]
    retry_count: int

    status: Literal[
        "in_progress",
        "awaiting_clarification",
        "completed",
        "failed",
    ]
