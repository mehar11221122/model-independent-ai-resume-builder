"""Unit tests for the clarify node's deterministic, templated question
phrasing - no LLM call is ever made (see `app.graph.nodes._templated_question`
and `VerticalConfig.field_questions`)."""
from unittest.mock import patch

from app.graph.nodes import build_clarify_node
from app.modules.resume.config import RESUME_VERTICAL


def test_clarify_returns_no_questions_when_nothing_missing():
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({"missing_fields": []})
    assert result == {"follow_up_questions": [], "status": "in_progress"}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_clarify_uses_templated_questions_without_calling_the_model(mock_invoke, mock_get_model):
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({"missing_fields": ["email", "full_name"], "language": "en"})

    assert not mock_get_model.called
    assert not mock_invoke.called
    assert result["status"] == "awaiting_clarification"
    assert result["follow_up_questions"] == [
        {"field": "email", "question": "What's your email address?"},
        {"field": "full_name", "question": "What's your full name?"},
    ]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_clarify_uses_arabic_template_for_known_field(mock_invoke, mock_get_model):
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({"missing_fields": ["email"], "language": "ar"})

    assert not mock_invoke.called
    assert result["follow_up_questions"] == [
        {"field": "email", "question": "ما هو بريدك الإلكتروني؟"}
    ]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_clarify_falls_back_to_generic_template_for_unknown_field(mock_invoke, mock_get_model):
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({
        "missing_fields": ["some_future_field"],
        "missing_field_hints": {"some_future_field": "a made-up hint"},
        "language": "en",
    })

    assert not mock_invoke.called
    assert result["follow_up_questions"] == [
        {"field": "some_future_field", "question": "Could you tell me about a made-up hint?"}
    ]


def test_clarify_attaches_quick_pick_options_to_matching_question():
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({
        "missing_fields": ["email"],
        "missing_field_options": {"email": ["a@x.com", "b@x.com"]},
        "language": "en",
    })

    assert result["follow_up_questions"][0]["options"] == ["a@x.com", "b@x.com"]


def test_clarify_omits_options_key_when_none_available():
    clarify = build_clarify_node(RESUME_VERTICAL)
    result = clarify({"missing_fields": ["email"], "language": "en"})
    assert "options" not in result["follow_up_questions"][0]
