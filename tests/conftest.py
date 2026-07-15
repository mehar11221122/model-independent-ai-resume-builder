"""Shared pytest fixtures."""
import pytest

from app.llm import cache as llm_cache


@pytest.fixture(autouse=True)
def _clear_llm_cache():
    """The exact-match LLM response cache (`app/llm/cache.py`) is a
    module-level, in-process singleton so it works across every node call
    within one request - but that also means it persists across the whole
    pytest session unless reset. Different tests often reuse the same
    question/answer fixtures (e.g. "What is your email?"), so without this,
    a result cached by an earlier test could silently satisfy - and hide a
    regression in - a later test that mocks a different verdict for the
    same input.
    """
    llm_cache.clear()
    yield
    llm_cache.clear()
