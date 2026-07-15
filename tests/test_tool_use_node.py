"""Unit tests for the generic tool-use node.

Covers two paths:
1. Deterministic enrichment (`config.deterministic_enrichment`) - the path
   the resume vertical actually uses: dates get normalized directly, with
   zero LLM calls.
2. The generic LLM-mediated tool-calling primitive (`config.tools` +
   `bind_tools`), which the node falls back to for a vertical that has
   tools but no deterministic shortcut - verified here with a plain,
   non-resume config so it's clear this mechanism still works generically.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.graph.nodes import build_tool_use_node
from app.graph.vertical import VerticalConfig
from app.modules.resume.config import RESUME_VERTICAL
from app.modules.resume.tools import normalize_date


def _fake_response(tool_calls=None):
    return SimpleNamespace(content="", tool_calls=tool_calls or [])


def _base_config(**overrides):
    return VerticalConfig(
        name="no-tools",
        output_schema=object,
        required_fields=[],
        extraction_prompt="",
        generation_prompt="",
        clarification_prompt="",
        **overrides,
    )


def test_no_op_when_vertical_has_no_tools_and_no_deterministic_enrichment():
    use_tools = build_tool_use_node(_base_config())
    assert use_tools({"extracted_data": {"foo": "bar"}}) == {}


# ---- Deterministic enrichment path (used by the resume vertical) ----

@patch("app.graph.nodes.get_model_with_fallback")
def test_resume_vertical_normalizes_dates_without_calling_the_model(mock_get_model):
    use_tools = build_tool_use_node(RESUME_VERTICAL)
    result = use_tools({
        "extracted_data": {
            "full_name": "Sam",
            "work_experience": [
                {"job_title": "Engineer", "company": "Acme", "start_date": "Jan 2022", "end_date": "March 2023"}
            ],
        },
    })

    assert not mock_get_model.called
    entry = result["extracted_data"]["work_experience"][0]
    assert entry["start_date"] == "2022-01"
    assert entry["end_date"] == "2023-03"


@patch("app.graph.nodes.get_model_with_fallback")
def test_deterministic_enrichment_no_op_when_nothing_to_normalize(mock_get_model):
    use_tools = build_tool_use_node(RESUME_VERTICAL)
    result = use_tools({"extracted_data": {"full_name": "Sam"}})

    assert not mock_get_model.called
    assert result == {}


def test_deterministic_enrichment_preferred_over_llm_tools_when_both_configured():
    config = _base_config(
        tools=[normalize_date],
        deterministic_enrichment=lambda extracted: {**extracted, "touched": True},
    )
    use_tools = build_tool_use_node(config)
    with patch("app.graph.nodes.get_model_with_fallback") as mock_get_model:
        result = use_tools({"extracted_data": {"foo": "bar"}})

    assert not mock_get_model.called
    assert result == {"extracted_data": {"foo": "bar", "touched": True}}


# ---- Generic LLM-mediated tool-calling primitive (fallback path) ----

@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_no_op_when_model_calls_no_tools(mock_invoke, mock_get_model):
    mock_model = MagicMock()
    mock_model.bind_tools.return_value = mock_model
    mock_get_model.return_value = mock_model
    mock_invoke.return_value = _fake_response(tool_calls=[])

    use_tools = build_tool_use_node(_base_config(tools=[normalize_date]))
    result = use_tools({"extracted_data": {"full_name": "Sam"}})
    assert result == {}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_executes_tool_call_and_merges_result(mock_invoke, mock_get_model):
    mock_model = MagicMock()
    mock_model.bind_tools.return_value = mock_model
    mock_get_model.return_value = mock_model
    mock_invoke.return_value = _fake_response(tool_calls=[
        {"name": "normalize_date", "args": {"date_str": "Jan 2022"}, "id": "call_1"},
    ])

    use_tools = build_tool_use_node(_base_config(tools=[normalize_date]))
    result = use_tools({"extracted_data": {"full_name": "Sam"}})

    assert "extracted_data" in result
    enrichment = result["extracted_data"]["tool_enrichment"]
    assert len(enrichment) == 1
    entry = next(iter(enrichment.values()))
    assert entry["tool"] == "normalize_date"
    assert entry["result"] == "2022-01"
    # Original data is preserved alongside the enrichment.
    assert result["extracted_data"]["full_name"] == "Sam"


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_unknown_tool_call_is_skipped_gracefully(mock_invoke, mock_get_model):
    mock_model = MagicMock()
    mock_model.bind_tools.return_value = mock_model
    mock_get_model.return_value = mock_model
    mock_invoke.return_value = _fake_response(tool_calls=[
        {"name": "not_a_real_tool", "args": {}, "id": "call_1"},
    ])

    use_tools = build_tool_use_node(_base_config(tools=[normalize_date]))
    result = use_tools({"extracted_data": {"full_name": "Sam"}})
    assert result == {}


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_model_failure_is_swallowed(mock_invoke, mock_get_model):
    mock_model = MagicMock()
    mock_model.bind_tools.return_value = mock_model
    mock_get_model.return_value = mock_model
    mock_invoke.side_effect = RuntimeError("model unavailable")

    use_tools = build_tool_use_node(_base_config(tools=[normalize_date]))
    result = use_tools({"extracted_data": {"full_name": "Sam"}})
    assert result == {}
