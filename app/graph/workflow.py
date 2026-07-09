"""Builds the shared LangGraph workflow described in the scope document:

    Input -> Document Extraction -> Information Merging -> Gap Detection ->
    Follow-up Questions -> Structured Generation -> Validation -> JSON Response

The graph itself is 100% generic. A vertical (Resume, Marketing, ...) is
"added" by calling `build_workflow()` with its own VerticalConfig - no graph
code needs to change.
"""
from langgraph.graph import END, StateGraph

from app.graph.checkpointer import get_checkpointer
from app.graph.nodes import (
    build_clarify_node,
    build_extraction_node,
    build_gap_check_node,
    build_generation_node,
    build_merge_answers_node,
    build_validation_node,
    route_after_clarify,
    route_after_gap_check,
    route_after_validate,
)
from app.graph.state import EngineState
from app.graph.vertical import VerticalConfig


def _mark_failed(state: EngineState) -> dict:
    return {"status": "failed"}


def build_workflow(config: VerticalConfig):
    graph = StateGraph(EngineState)

    graph.add_node("extract", build_extraction_node(config))
    graph.add_node("merge_answers", build_merge_answers_node(config))
    graph.add_node("gap_check", build_gap_check_node(config))
    graph.add_node("clarify", build_clarify_node(config))
    graph.add_node("generate", build_generation_node(config))
    graph.add_node("validate", build_validation_node(config))
    graph.add_node("mark_failed", _mark_failed)

    graph.set_entry_point("extract")
    graph.add_edge("extract", "gap_check")
    graph.add_edge("merge_answers", "gap_check")

    graph.add_conditional_edges(
        "gap_check",
        route_after_gap_check,
        {"clarify": "clarify", "generate": "generate"},
    )
    graph.add_conditional_edges(
        "clarify",
        route_after_clarify,
        {"pause": END, "generate": "generate"},
    )
    graph.add_conditional_edges(
        "validate",
        route_after_validate(config),
        {"done": END, "retry": "generate", "failed": "mark_failed"},
    )
    graph.add_edge("generate", "validate")
    graph.add_edge("mark_failed", END)

    return graph.compile(checkpointer=get_checkpointer())


def resume_with_answers(compiled_graph, thread_id: str, answers: dict[str, str]):
    """Feed clarification answers back into a paused thread and continue
    execution from where it left off (merge_answers -> gap_check -> ...).

    `as_node="merge_answers"` tells LangGraph this update represents the
    output of that node, so the next `invoke(None, ...)` resumes with
    whatever comes after it in the graph (gap_check -> ...), even though the
    thread actually paused at END after `clarify`.
    """
    config = {"configurable": {"thread_id": thread_id}}
    compiled_graph.update_state(
        config, {"user_answers": answers}, as_node="merge_answers"
    )
    return compiled_graph.invoke(None, config)
