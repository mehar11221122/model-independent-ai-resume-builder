"""Verifies the generation node feeds previous validation errors back to the
model on retry, instead of blindly repeating the exact same prompt."""
from unittest.mock import MagicMock, patch

from app.graph.nodes import build_generation_node
from app.modules.resume.config import RESUME_VERTICAL


def _mock_structured_model():
    mock_model = MagicMock()
    mock_model.with_structured_output.return_value = mock_model
    return mock_model


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_first_attempt_has_no_error_feedback(mock_invoke, mock_get_model):
    mock_get_model.return_value = _mock_structured_model()
    mock_invoke.return_value = MagicMock(model_dump=lambda: {"ok": True})

    generate = build_generation_node(RESUME_VERTICAL)
    generate({"extracted_data": {"full_name": "Sam"}, "retry_count": 0, "validation_errors": []})

    messages = mock_invoke.call_args[0][1]
    human_payload = messages[1][1]
    assert "Previous attempt" not in human_payload


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_retry_includes_previous_validation_errors(mock_invoke, mock_get_model):
    mock_get_model.return_value = _mock_structured_model()
    mock_invoke.return_value = MagicMock(model_dump=lambda: {"ok": True})

    generate = build_generation_node(RESUME_VERTICAL)
    generate({
        "extracted_data": {"full_name": "Sam"},
        "retry_count": 1,
        "validation_errors": ["job_title Field required"],
    })

    messages = mock_invoke.call_args[0][1]
    human_payload = messages[1][1]
    assert "job_title Field required" in human_payload
    assert "Previous attempt" in human_payload


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_identical_state_hits_cache_on_second_call(mock_invoke, mock_get_model):
    mock_get_model.return_value = _mock_structured_model()
    mock_invoke.return_value = MagicMock(model_dump=lambda: {"ok": True})

    generate = build_generation_node(RESUME_VERTICAL)
    state = {"extracted_data": {"full_name": "Sam"}, "retry_count": 0, "validation_errors": []}

    first = generate(state)
    second = generate(state)

    assert mock_invoke.call_count == 1
    assert first == second == {"structured_output": {"ok": True}}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_failed_generation_is_never_cached(mock_invoke, mock_get_model):
    mock_get_model.return_value = _mock_structured_model()
    mock_invoke.side_effect = [RuntimeError("boom"), MagicMock(model_dump=lambda: {"ok": True})]

    generate = build_generation_node(RESUME_VERTICAL)
    state = {"extracted_data": {"full_name": "Sam"}, "retry_count": 0, "validation_errors": []}

    first = generate(state)
    second = generate(state)

    assert mock_invoke.call_count == 2
    assert first == {"structured_output": None}
    assert second == {"structured_output": {"ok": True}}
