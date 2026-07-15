"""Proves the "human-in-the-loop workflow with resumable state" claim for
real: a session paused by one graph/checkpointer connection can be resumed
by a completely independent graph/checkpointer connection reading the same
SQLite file - i.e. genuine cross-process durability, not just in-memory
state surviving within a single request/graph object.

The LLM layer is mocked (deterministic, no network/API key needed) so this
test is fast and reliable; only the checkpointing is real.
"""
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel

from app.graph.vertical import VerticalConfig
from app.graph.workflow import build_workflow, resume_with_answers


class _TinyOutput(BaseModel):
    name: str
    email: str


_TEST_VERTICAL = VerticalConfig(
    name="test-vertical",
    output_schema=_TinyOutput,
    required_fields=["name", "email"],
    extraction_prompt="extract the fields",
    generation_prompt="generate the output",
    clarification_prompt="ask about {missing_fields} in {language}",
    # The clarify node phrases known fields deterministically (no LLM call) -
    # see `VerticalConfig.field_questions` - so this test's missing field
    # needs an entry here to get the specific wording it asserts on.
    field_questions={"email": {"en": "What is your email address?"}},
    # This test is about checkpoint durability, not the final-confirmation
    # feature - disable it so resuming with the last answer goes straight
    # to "completed" as before.
    confirm_before_generate=False,
)


def _fake_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(content=content)


def _fresh_sqlite_saver(db_path) -> SqliteSaver:
    """A brand-new connection to the given file - stands in for "a
    different process attaching to the same durable checkpoint store"."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


@patch("app.graph.nodes.get_model_with_fallback")
@patch("app.graph.nodes.invoke_with_retry")
def test_clarification_pause_resumes_across_independent_graph_instances(
    mock_invoke, mock_get_model, tmp_path
):
    db_path = tmp_path / "checkpoints.sqlite"
    thread_id = "cross-process-thread"
    config = {"configurable": {"thread_id": thread_id}}

    # --- "Process 1": start the session, pause on a missing field ---
    # Only `extract` calls the model here - `clarify` phrases the missing
    # "email" field from `field_questions` above, with no LLM call.
    mock_invoke.side_effect = [
        _fake_response('{"name": "Sam"}'),  # extract: found name, not email
    ]
    with patch("app.graph.workflow.get_checkpointer", return_value=_fresh_sqlite_saver(db_path)):
        workflow_p1 = build_workflow(_TEST_VERTICAL)
        result1 = workflow_p1.invoke(
            {
                "thread_id": thread_id,
                "vertical": "test-vertical",
                "language": "en",
                "extracted_data": {},
                "user_answers": {},
                "retry_count": 0,
                "status": "in_progress",
            },
            config,
        )

    assert result1["status"] == "awaiting_clarification"
    assert result1["follow_up_questions"] == [
        {"field": "email", "question": "What is your email address?"}
    ]

    # --- "Process 2": a brand-new graph object with its own fresh SQLite
    # connection to the SAME file - proves the paused state was actually
    # durably persisted, not just held in workflow_p1's memory. ---
    mock_invoke.side_effect = [
        _fake_response('{"email": {"valid": true}}'),  # check_answers accepts it
        _TinyOutput(name="Sam", email="sam@example.com"),  # generate
    ]
    with patch("app.graph.workflow.get_checkpointer", return_value=_fresh_sqlite_saver(db_path)):
        workflow_p2 = build_workflow(_TEST_VERTICAL)
        assert workflow_p2 is not workflow_p1

        # The new instance can see the paused state without any answers submitted yet.
        snapshot = workflow_p2.get_state(config)
        assert snapshot.values["follow_up_questions"] == [
            {"field": "email", "question": "What is your email address?"}
        ]

        result2 = resume_with_answers(workflow_p2, thread_id, {"email": "sam@example.com"})

    assert result2["status"] == "completed"
    assert result2["structured_output"] == {"name": "Sam", "email": "sam@example.com"}
