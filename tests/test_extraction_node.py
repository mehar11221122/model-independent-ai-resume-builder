"""Unit tests for the extraction node, including its exact-match response
cache (identical `merged_text` should skip a second model call entirely)."""
from types import SimpleNamespace
from unittest.mock import patch

from app.graph.nodes import build_extraction_node
from app.modules.resume.config import RESUME_VERTICAL


def _fake_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(content=content)


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_extract_parses_json_and_merges_into_extracted_data(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response('{"full_name": "Sam"}')
    extract = build_extraction_node(RESUME_VERTICAL)

    result = extract({"merged_text": "Sam, a software engineer.", "extracted_data": {}})

    assert result["extracted_data"] == {"full_name": "Sam"}
    assert result["status"] == "in_progress"


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_extract_defaults_to_empty_dict_on_bad_json(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response("not json")
    extract = build_extraction_node(RESUME_VERTICAL)

    result = extract({"merged_text": "garbled", "extracted_data": {"existing": "kept"}})

    assert result["extracted_data"] == {"existing": "kept"}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_identical_merged_text_hits_cache_on_second_call(mock_invoke, mock_get_model):
    mock_invoke.return_value = _fake_response('{"full_name": "Sam"}')
    extract = build_extraction_node(RESUME_VERTICAL)

    first = extract({"merged_text": "Sam, a software engineer.", "extracted_data": {}})
    second = extract({"merged_text": "Sam, a software engineer.", "extracted_data": {}})

    assert mock_invoke.call_count == 1
    assert first["extracted_data"] == second["extracted_data"] == {"full_name": "Sam"}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_different_merged_text_does_not_hit_cache(mock_invoke, mock_get_model):
    mock_invoke.side_effect = [
        _fake_response('{"full_name": "Sam"}'),
        _fake_response('{"full_name": "Alex"}'),
    ]
    extract = build_extraction_node(RESUME_VERTICAL)

    first = extract({"merged_text": "Sam, a software engineer.", "extracted_data": {}})
    second = extract({"merged_text": "Alex, a data scientist.", "extracted_data": {}})

    assert mock_invoke.call_count == 2
    assert first["extracted_data"] == {"full_name": "Sam"}
    assert second["extracted_data"] == {"full_name": "Alex"}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_failed_extraction_is_never_cached(mock_invoke, mock_get_model):
    mock_invoke.side_effect = [
        _fake_response("not json"),
        _fake_response('{"full_name": "Sam"}'),
    ]
    extract = build_extraction_node(RESUME_VERTICAL)

    first = extract({"merged_text": "same text", "extracted_data": {}})
    second = extract({"merged_text": "same text", "extracted_data": {}})

    # The failed first attempt must not have poisoned the cache - the
    # second, identical-input call gets a fresh attempt from the model.
    assert mock_invoke.call_count == 2
    assert first["extracted_data"] == {}
    assert second["extracted_data"] == {"full_name": "Sam"}


@patch("app.graph.nodes.get_settings")
@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_cache_disabled_always_calls_the_model(mock_invoke, mock_get_model, mock_get_settings):
    from app.core.config import Settings

    settings = Settings(llm_cache_enabled=False)
    mock_get_settings.return_value = settings
    mock_invoke.return_value = _fake_response('{"full_name": "Sam"}')

    extract = build_extraction_node(RESUME_VERTICAL)
    extract({"merged_text": "Sam, a software engineer.", "extracted_data": {}})
    extract({"merged_text": "Sam, a software engineer.", "extracted_data": {}})

    assert mock_invoke.call_count == 2
