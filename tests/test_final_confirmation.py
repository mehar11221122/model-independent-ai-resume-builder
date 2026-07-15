"""Tests for the "should I generate now, or is there more?" confirmation
step (`VerticalConfig.confirm_before_generate`). It's implemented as just
another virtual missing field (`_CONFIRM_FIELD`) that flows through the
existing generic clarify/merge/gap-check loop, so these tests focus on:
gap_check only injecting it once everything else is settled, clarify
answering it deterministically (no LLM call), the answer-check node leaving
it alone, and merge_user_answers routing "yes" vs "more info" correctly.
"""
from unittest.mock import patch

from app.graph.nodes import (
    _CONFIRM_FIELD,
    build_answer_check_node,
    build_clarify_node,
    build_gap_check_node,
    merge_user_answers,
)
from app.modules.resume.config import RESUME_VERTICAL

_COMPLETE_EXTRACTED = {
    "full_name": "Sam Lee",
    "email": "sam@example.com",
    "work_experience": [
        {"job_title": "Engineer", "company": "Acme", "start_date": "2020", "end_date": "present"}
    ],
    "education": "BSc Computer Science",
    "skills": "Python, SQL",
    "summary": "Backend engineer with 4 years of experience.",
    "key_achievements": "Shipped a rewrite that cut latency by 30%.",
}


def test_gap_check_asks_confirmation_once_nothing_else_missing():
    gap_check = build_gap_check_node(RESUME_VERTICAL)
    result = gap_check({"extracted_data": dict(_COMPLETE_EXTRACTED), "language": "en"})

    assert result["missing_fields"] == [_CONFIRM_FIELD]
    assert result["missing_field_options"][_CONFIRM_FIELD] == [
        "Yes, generate it now",
        "Wait, I have more to add",
    ]


def test_gap_check_does_not_reask_once_confirmed():
    gap_check = build_gap_check_node(RESUME_VERTICAL)
    extracted = {**_COMPLETE_EXTRACTED, "_ready_to_generate": True}
    result = gap_check({"extracted_data": extracted, "language": "en"})

    assert result["missing_fields"] == []


def test_gap_check_skips_confirmation_while_real_fields_still_missing():
    gap_check = build_gap_check_node(RESUME_VERTICAL)
    result = gap_check({"extracted_data": {"full_name": "Sam"}, "language": "en"})

    assert _CONFIRM_FIELD not in result["missing_fields"]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_clarify_answers_confirmation_without_calling_the_model(mock_invoke, mock_get_model):
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({
        "missing_fields": [_CONFIRM_FIELD],
        "missing_field_options": {_CONFIRM_FIELD: ["Yes, generate it now", "Wait, I have more to add"]},
        "language": "en",
    })

    assert not mock_invoke.called
    assert result["status"] == "awaiting_clarification"
    assert result["follow_up_questions"] == [{
        "field": _CONFIRM_FIELD,
        "question": (
            "I think I have everything I need! Should I go ahead and generate "
            "it now, or is there more information you'd like to add first?"
        ),
        "options": ["Yes, generate it now", "Wait, I have more to add"],
    }]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_clarify_answers_other_fields_alongside_confirmation_without_calling_the_model(mock_invoke, mock_get_model):
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({
        "missing_fields": ["email", _CONFIRM_FIELD],
        "language": "en",
    })

    assert not mock_invoke.called
    fields = [q["field"] for q in result["follow_up_questions"]]
    assert fields == ["email", _CONFIRM_FIELD]


def test_answer_check_node_ignores_confirmation_field():
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {_CONFIRM_FIELD: "Yes, generate it now"},
        "follow_up_questions": [{"field": _CONFIRM_FIELD, "question": "Ready?"}],
        "extracted_data": {},
    })

    assert result == {"follow_up_questions": []}


def test_merge_user_answers_yes_sets_ready_flag():
    merged = merge_user_answers({}, {_CONFIRM_FIELD: "Yes, generate it now"})
    assert merged["_ready_to_generate"] is True
    assert _CONFIRM_FIELD not in merged


def test_merge_user_answers_free_typed_yes_also_counts():
    merged = merge_user_answers({}, {_CONFIRM_FIELD: "yes"})
    assert merged["_ready_to_generate"] is True


def test_merge_user_answers_more_button_sets_flag_false_without_polluting_context():
    merged = merge_user_answers({}, {_CONFIRM_FIELD: "Wait, I have more to add"})
    assert merged["_ready_to_generate"] is False
    assert "additional_context" not in merged


def test_merge_user_answers_typed_extra_info_is_captured_as_additional_context():
    merged = merge_user_answers({}, {_CONFIRM_FIELD: "Oh, I also volunteered at a food bank in 2019."})
    assert merged["_ready_to_generate"] is False
    assert merged["additional_context"] == "Oh, I also volunteered at a food bank in 2019."


def test_merge_user_answers_appends_multiple_rounds_of_additional_context():
    first = merge_user_answers({}, {_CONFIRM_FIELD: "I also speak French."})
    second = merge_user_answers(first, {_CONFIRM_FIELD: "And I have a PMP certification."})
    assert "I also speak French." in second["additional_context"]
    assert "And I have a PMP certification." in second["additional_context"]


def test_full_loop_reasks_confirmation_until_yes():
    gap_check = build_gap_check_node(RESUME_VERTICAL)

    # Round 1: nothing missing yet -> confirmation appears.
    r1 = gap_check({"extracted_data": dict(_COMPLETE_EXTRACTED), "language": "en"})
    assert r1["missing_fields"] == [_CONFIRM_FIELD]

    # User adds more info instead of confirming.
    merged = merge_user_answers(_COMPLETE_EXTRACTED, {_CONFIRM_FIELD: "One more thing: I'm fluent in Spanish."})
    r2 = gap_check({"extracted_data": merged, "language": "en"})
    assert r2["missing_fields"] == [_CONFIRM_FIELD]  # asked again

    # User confirms.
    merged2 = merge_user_answers(merged, {_CONFIRM_FIELD: "Yes, generate it now"})
    r3 = gap_check({"extracted_data": merged2, "language": "en"})
    assert r3["missing_fields"] == []  # proceeds to generate
