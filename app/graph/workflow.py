"""Builds the shared LangGraph workflow described in the scope document:

    Input -> Document Extraction (incl. cross-source merging/reconciliation)
    -> Gap Detection -> Follow-up Questions -> Answer Validation ->
    Structured Generation -> Validation -> JSON Response

There is no separate "Information Merging" node: `app/ingestion/merge.py`
concatenates multi-source text with labels, and the `extract` node's LLM
reconciles/deduplicates facts and flags disagreements (as `conflicts`) in
that same pass - see its module docstring for why. Conflicts and other gaps
both flow through the same clarify -> merge_answers -> check_answers ->
gap_check loop below. That loop also asks one final "generate now, or is
there more?" confirmation once nothing else is missing (see
`VerticalConfig.confirm_before_generate` / `_CONFIRM_FIELD` in nodes.py) -
it's just another virtual missing field, so it costs zero extra graph
wiring or LLM calls beyond the (deterministic, non-LLM) question itself.

The graph itself is 100% generic. A vertical (Resume, Marketing, ...) is
"added" by calling `build_workflow()` with its own VerticalConfig - no graph
code needs to change.
"""
from langgraph.graph import END, StateGraph

from app.graph.checkpointer import get_checkpointer
from app.graph.nodes import (
    build_answer_check_node,
    build_clarify_node,
    build_extraction_node,
    build_gap_check_node,
    build_generation_node,
    build_merge_answers_node,
    build_tool_use_node,
    build_validation_node,
    merge_user_answers,
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
    graph.add_node("check_answers", build_answer_check_node(config))
    graph.add_node("gap_check", build_gap_check_node(config))
    graph.add_node("clarify", build_clarify_node(config))
    graph.add_node("tool_use", build_tool_use_node(config))
    graph.add_node("generate", build_generation_node(config))
    graph.add_node("validate", build_validation_node(config))
    graph.add_node("mark_failed", _mark_failed)

    graph.set_entry_point("extract")
    graph.add_edge("extract", "gap_check")
    graph.add_edge("merge_answers", "check_answers")
    graph.add_edge("check_answers", "gap_check")

    graph.add_conditional_edges(
        "gap_check",
        route_after_gap_check,
        {"clarify": "clarify", "generate": "tool_use"},
    )
    graph.add_conditional_edges(
        "clarify",
        route_after_clarify,
        {"pause": END, "generate": "tool_use"},
    )
    graph.add_edge("tool_use", "generate")
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
    execution from where it left off
    (merge_answers -> check_answers -> gap_check -> ...).

    `as_node="merge_answers"` tells LangGraph this update represents the
    output of that node, so the next `invoke(None, ...)` resumes with
    whatever comes after it in the graph (check_answers -> gap_check -> ...),
    even though the thread actually paused at END after `clarify`. Because
    the node itself is being skipped this way, we must compute its effect
    (merging answers into extracted_data, via the same `merge_user_answers`
    helper the node itself uses) here ourselves - passing only
    `user_answers` would leave extracted_data unmerged and gap_check would
    ask the same question again.

    `follow_up_questions` is deliberately left as-is (not cleared here) -
    the real `check_answers` node that runs next needs the original
    question text to judge each answer, and clears the list itself once
    done, exactly like the in-graph `merge_answers` node does.
    """
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = compiled_graph.get_state(config)
    extracted = dict(snapshot.values.get("extracted_data", {})) if snapshot else {}
    language = snapshot.values.get("language", "en") if snapshot else "en"
    merged = merge_user_answers(extracted, answers, language)

    compiled_graph.update_state(
        config,
        {
            "user_answers": answers,
            "extracted_data": merged,
            "status": "in_progress",
        },
        as_node="merge_answers",
    )
    return compiled_graph.invoke(None, config)
