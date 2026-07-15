"""Unit tests for the answer-check node: catches off-topic or incomplete
clarification answers before they're trusted for generation, with the LLM
call mocked out (no API key needed)."""
from types import SimpleNamespace
from unittest.mock import patch

from app.graph.nodes import build_answer_check_node, build_gap_check_node
from app.modules.resume.config import RESUME_VERTICAL


def _fake_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(content=content)


def test_check_answers_noop_when_no_matching_questions():
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({"user_answers": {"email": "sam@example.com"}, "follow_up_questions": []})
    assert result == {"follow_up_questions": []}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_accepts_valid_answer(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response('{"email": {"valid": true}}')
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"email": "sam@example.com"},
        "follow_up_questions": [{"field": "email", "question": "What is your email?"}],
        "extracted_data": {"email": "sam@example.com"},
    })
    assert result == {"follow_up_questions": []}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_rejects_off_topic_answer(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response(
        '{"education": {"valid": false, "reason": "That described achievements, not your education - '
        'what degree did you study and where?"}}'
    )
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"education": "I increased sales by 40% and won employee of the month."},
        "follow_up_questions": [{"field": "education", "question": "Tell me about your education."}],
        "extracted_data": {"education": "I increased sales by 40% and won employee of the month."},
    })

    assert result["invalid_answer_fields"] == ["education"]
    assert "degree" in result["missing_field_hints"]["education"]
    assert "education" not in result["extracted_data"]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_rejects_incomplete_answer(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response(
        '{"education": {"valid": false, "reason": "You gave the dates but not the degree/subject or school - '
        'what did you study and where?"}}'
    )
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"education": "My degree lasted from 2026 to 2030."},
        "follow_up_questions": [
            {"field": "education", "question": "What's your degree, school, and dates?"}
        ],
        "extracted_data": {"education": "My degree lasted from 2026 to 2030."},
    })

    assert result["invalid_answer_fields"] == ["education"]
    assert "school" in result["missing_field_hints"]["education"]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_fails_open_on_broken_response(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response("not valid json at all")
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"email": "sam@example.com"},
        "follow_up_questions": [{"field": "email", "question": "What is your email?"}],
        "extracted_data": {"email": "sam@example.com"},
    })
    assert result == {"follow_up_questions": []}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_call_failure_fails_open(mock_invoke, mock_get_model):
    mock_invoke.side_effect = RuntimeError("free-tier model timed out")
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"email": "sam@example.com"},
        "follow_up_questions": [{"field": "email", "question": "What is your email?"}],
        "extracted_data": {"email": "sam@example.com"},
    })
    assert result == {"follow_up_questions": []}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_rejects_empty_answer_without_calling_the_model(mock_invoke, mock_get_model):
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"email": "   "},
        "follow_up_questions": [{"field": "email", "question": "What is your email?"}],
        "extracted_data": {"email": "   "},
    })

    assert not mock_get_model.called
    assert not mock_invoke.called
    assert result["invalid_answer_fields"] == ["email"]
    assert "email" not in result["extracted_data"]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_rejects_bad_email_with_direct_correction_hint(mock_invoke, mock_get_model):
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"email": "not-an-email"},
        "follow_up_questions": [{"field": "email", "question": "What is your email?"}],
        "extracted_data": {"email": "not-an-email"},
    })

    assert not mock_get_model.called
    assert not mock_invoke.called
    assert result["invalid_answer_fields"] == ["email"]
    assert "Please correct" in result["missing_field_hints"]["email"]
    assert "email" not in result["extracted_data"]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_rejects_echoed_question_without_calling_the_model(mock_invoke, mock_get_model):
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"email": "What is your email?"},
        "follow_up_questions": [{"field": "email", "question": "What is your email?"}],
        "extracted_data": {"email": "What is your email?"},
    })

    assert not mock_get_model.called
    assert not mock_invoke.called
    assert result["invalid_answer_fields"] == ["email"]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_check_answers_only_sends_ambiguous_answers_to_the_model(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response('{"education": {"valid": true}}')
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    result = check_answers({
        "user_answers": {"email": "", "education": "BSc Computer Science, State University, 2020"},
        "follow_up_questions": [
            {"field": "email", "question": "What is your email?"},
            {"field": "education", "question": "Tell me about your education."},
        ],
        "extracted_data": {"education": "BSc Computer Science, State University, 2020"},
    })

    # The empty "email" answer never reaches the model's payload (sent as
    # the human message, separate from the static system instructions)...
    sent_payload = mock_invoke.call_args[0][1][1][1]
    assert "email" not in sent_payload
    assert "education" in sent_payload
    # ...but is still reported invalid alongside whatever the model checked.
    assert result["invalid_answer_fields"] == ["email"]


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_identical_ambiguous_answer_hits_cache_on_second_call(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response('{"education": {"valid": true}}')
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    state = {
        "user_answers": {"education": "BSc Computer Science, State University, 2020"},
        "follow_up_questions": [{"field": "education", "question": "Tell me about your education."}],
        "extracted_data": {"education": "BSc Computer Science, State University, 2020"},
    }

    first = check_answers(state)
    second = check_answers(state)

    assert mock_invoke.call_count == 1
    assert first == second == {"follow_up_questions": []}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_failed_verdict_call_is_never_cached(mock_invoke, mock_get_model):
    mock_invoke.side_effect = [
        RuntimeError("free-tier model timed out"),
        _fake_response('{"education": {"valid": true}}'),
    ]
    check_answers = build_answer_check_node(RESUME_VERTICAL)
    state = {
        "user_answers": {"education": "BSc Computer Science, State University, 2020"},
        "follow_up_questions": [{"field": "education", "question": "Tell me about your education."}],
        "extracted_data": {"education": "BSc Computer Science, State University, 2020"},
    }

    check_answers(state)
    check_answers(state)

    # The failed first call must not have poisoned the cache.
    assert mock_invoke.call_count == 2


def test_gap_check_reasks_invalid_answer_fields_with_their_hint():
    gap_check = build_gap_check_node(RESUME_VERTICAL)
    extracted = {
        "full_name": "Sam",
        "email": "sam@example.com",
        "work_experience": [{"job_title": "Engineer", "company": "Acme"}],
        "skills": "Python",
        # `education` was reverted by check_answers because the answer was rejected.
    }
    result = gap_check({
        "extracted_data": extracted,
        "invalid_answer_fields": ["education"],
        "missing_field_hints": {"education": "What did you study and where?"},
    })

    assert "education" in result["missing_fields"]
    assert result["missing_field_hints"]["education"] == "What did you study and where?"
    assert result["invalid_answer_fields"] == []
