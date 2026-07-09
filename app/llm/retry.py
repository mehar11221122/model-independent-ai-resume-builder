"""Resilience wrapper for LLM calls.

Free OpenRouter models (":free" suffix) are rate-limited (~20 req/min,
200 req/day) and return HTTP 429 when exceeded. This wraps every model
invocation with exponential-backoff retry so transient rate-limit hits
don't fail a whole workflow run.
"""
import logging

from openai import APIConnectionError, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError)


def _log_retry(retry_state):
    exc = retry_state.outcome.exception()
    logger.warning(
        "LLM call failed (attempt %s), retrying: %s",
        retry_state.attempt_number,
        exc,
    )


@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    wait=wait_exponential_jitter(initial=2, max=30),
    stop=stop_after_attempt(5),
    before_sleep=_log_retry,
    reraise=True,
)
def invoke_with_retry(model, messages):
    """Drop-in replacement for `model.invoke(messages)` with retry/backoff
    on rate-limit and transient connection errors."""
    return model.invoke(messages)
