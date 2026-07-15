"""Tests for the generic "detect missing OR inconsistent data" capability:
extraction prompts (any vertical) can flag cross-source disagreements via
extracted_data["conflicts"], and the engine surfaces + resolves them through
the same clarify/merge loop used for plain missing fields."""
from unittest.mock import patch

from app.graph.nodes import build_clarify_node, build_gap_check_node, merge_user_answers
from app.modules.resume.config import RESUME_VERTICAL


def test_gap_check_surfaces_conflict_as_virtual_field():
    gap_check = build_gap_check_node(RESUME_VERTICAL)
    extracted = {
        "full_name": "Sara Ahmad",
        "email": "sara@example.com",
        "work_experience": [{"job_title": "Engineer", "company": "Acme"}],
        "education": "BSc",
        "skills": "Python",
        "conflicts": [
            {"field": "full_name", "values": ["Sara Ahmad", "Sarah Ahmed"], "note": "spelling differs across sources"},
        ],
    }
    result = gap_check({"extracted_data": extracted})

    assert "conflict::full_name" in result["missing_fields"]
    hint = result["missing_field_hints"]["conflict::full_name"]
    assert "Sara Ahmad" in hint
    assert "Sarah Ahmed" in hint


def test_gap_check_returns_quick_pick_options_for_conflicts():
    gap_check = build_gap_check_node(RESUME_VERTICAL)
    extracted = {
        "full_name": "Sara Ahmad",
        "email": "sara@example.com",
        "work_experience": [{"job_title": "Engineer", "company": "Acme"}],
        "education": "BSc",
        "skills": "Python",
        "conflicts": [
            {"field": "full_name", "values": ["Sara Ahmad", "Sarah Ahmed"]},
        ],
    }
    result = gap_check({"extracted_data": extracted})
    assert result["missing_field_options"]["conflict::full_name"] == ["Sara Ahmad", "Sarah Ahmed"]


def test_gap_check_ignores_conflicts_without_a_field_key():
    gap_check = build_gap_check_node(RESUME_VERTICAL)
    extracted = {
        "full_name": "Sam",
        "email": "sam@example.com",
        "work_experience": [{"job_title": "Engineer", "company": "Acme"}],
        "education": "BSc",
        "skills": "Python",
        "conflicts": [{"values": ["x", "y"]}],
    }
    result = gap_check({"extracted_data": extracted})
    assert not any(f.startswith("conflict::") for f in result["missing_fields"])


def test_merge_user_answers_resolves_conflict_and_clears_it():
    extracted = {
        "full_name": "Sara Ahmad",
        "conflicts": [
            {"field": "full_name", "values": ["Sara Ahmad", "Sarah Ahmed"], "note": "spelling"},
            {"field": "email", "values": ["a@x.com", "b@x.com"]},
        ],
    }
    merged = merge_user_answers(extracted, {"conflict::full_name": "Sarah Ahmed"})

    assert merged["full_name"] == "Sarah Ahmed"
    remaining_fields = [c["field"] for c in merged["conflicts"]]
    assert "full_name" not in remaining_fields
    assert "email" in remaining_fields


def test_merge_user_answers_plain_fields_still_work():
    merged = merge_user_answers({"full_name": "Sam"}, {"email": "sam@example.com"})
    assert merged == {"full_name": "Sam", "email": "sam@example.com"}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_clarify_builds_conflict_question_from_options_without_calling_the_model(mock_invoke, mock_get_model):
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({
        "missing_fields": ["conflict::full_name"],
        "missing_field_hints": {
            "conflict::full_name": "the sources disagree on 'full_name' - values found: Sara Ahmad, Sarah Ahmed",
        },
        "missing_field_options": {"conflict::full_name": ["Sara Ahmad", "Sarah Ahmed"]},
        "language": "en",
    })

    assert not mock_invoke.called
    assert result["status"] == "awaiting_clarification"
    question = result["follow_up_questions"][0]
    assert question["field"] == "conflict::full_name"
    assert "Sara Ahmad" in question["question"]
    assert "Sarah Ahmed" in question["question"]
    assert question["options"] == ["Sara Ahmad", "Sarah Ahmed"]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_clarify_omits_options_key_when_none_available(mock_invoke, mock_get_model):
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({"missing_fields": ["email"], "language": "en"})

    assert not mock_invoke.called
    assert "options" not in result["follow_up_questions"][0]
