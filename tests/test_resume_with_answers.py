"""`resume_with_answers` must replicate `merge_answers` node's effect exactly
(including conflict resolution) since LangGraph's `as_node` resume trick
skips actually running the node."""
from unittest.mock import MagicMock

from app.graph.workflow import resume_with_answers


def _fake_compiled_graph(extracted_data: dict):
    graph = MagicMock()
    graph.get_state.return_value = MagicMock(values={"extracted_data": extracted_data})
    graph.invoke.return_value = {"status": "in_progress"}
    return graph


def test_resume_with_answers_merges_plain_fields():
    graph = _fake_compiled_graph({"full_name": "Sam"})
    resume_with_answers(graph, "thread-1", {"email": "sam@example.com"})

    update_args = graph.update_state.call_args[0]
    merged = update_args[1]["extracted_data"]
    assert merged == {"full_name": "Sam", "email": "sam@example.com"}


def test_resume_with_answers_resolves_conflicts():
    extracted = {
        "full_name": "Sara Ahmad",
        "conflicts": [{"field": "full_name", "values": ["Sara Ahmad", "Sarah Ahmed"]}],
    }
    graph = _fake_compiled_graph(extracted)
    resume_with_answers(graph, "thread-1", {"conflict::full_name": "Sarah Ahmed"})

    update_args = graph.update_state.call_args[0]
    merged = update_args[1]["extracted_data"]
    assert merged["full_name"] == "Sarah Ahmed"
    assert merged["conflicts"] == []
    assert graph.update_state.call_args.kwargs["as_node"] == "merge_answers"
