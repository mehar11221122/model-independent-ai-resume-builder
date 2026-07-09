from app.graph.nodes import route_after_clarify, route_after_gap_check, route_after_validate
from app.modules.resume.config import RESUME_VERTICAL


def test_route_after_gap_check_goes_to_clarify_when_missing_fields():
    state = {"missing_fields": ["email"]}
    assert route_after_gap_check(state) == "clarify"


def test_route_after_gap_check_goes_to_generate_when_nothing_missing():
    state = {"missing_fields": []}
    assert route_after_gap_check(state) == "generate"


def test_route_after_clarify_pauses_when_awaiting_clarification():
    state = {"status": "awaiting_clarification"}
    assert route_after_clarify(state) == "pause"


def test_route_after_clarify_continues_otherwise():
    state = {"status": "in_progress"}
    assert route_after_clarify(state) == "generate"


def test_route_after_validate_done_when_no_errors():
    router = route_after_validate(RESUME_VERTICAL)
    assert router({"validation_errors": []}) == "done"


def test_route_after_validate_retries_under_limit():
    router = route_after_validate(RESUME_VERTICAL)
    state = {"validation_errors": ["bad"], "retry_count": 1}
    assert router(state) == "retry"


def test_route_after_validate_fails_at_max_retries():
    router = route_after_validate(RESUME_VERTICAL)
    state = {"validation_errors": ["bad"], "retry_count": RESUME_VERTICAL.max_retries}
    assert router(state) == "failed"
