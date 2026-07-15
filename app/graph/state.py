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
    # Per-call hints for the *current* missing_fields, keyed by field name -
    # covers virtual fields gap_check invents on the fly (like
    # "conflict::email") that a vertical's static VerticalConfig.field_hints
    # can't know about ahead of time, since they depend on this run's data.
    missing_field_hints: dict[str, str]
    # Concrete choices for a missing field, when known ahead of time (e.g. a
    # conflict's exact candidate values) - lets the UI render quick-pick
    # buttons instead of forcing free text for something like "which of
    # these two emails is right?".
    missing_field_options: dict[str, list[str]]
    # Each item is {"field": <key matching extracted_data/required_fields>,
    # "question": <human-readable question text>} so callers can answer by
    # field key without guessing it from the question wording.
    follow_up_questions: list[dict[str, str]]
    user_answers: dict[str, str]
    # Fields the answer-check node judged this turn's answer didn't actually
    # satisfy (off-topic, empty, or missing a detail the question asked for)
    # - gap_check folds these back into missing_fields with the check node's
    # more specific hint, then this list is cleared. Vertical-agnostic: the
    # check works purely from question/answer text, no domain knowledge.
    invalid_answer_fields: list[str]

    structured_output: dict[str, Any] | None
    validation_errors: list[str]
    retry_count: int

    status: Literal[
        "in_progress",
        "awaiting_clarification",
        "completed",
        "failed",
    ]
