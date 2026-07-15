"""Resilience wrapper for LLM calls.

Free OpenRouter models (":free" suffix) are rate-limited (~20 req/min,
200 req/day) and return HTTP 429 when exceeded. This wraps every model
invocation with exponential-backoff retry so transient rate-limit hits
don't fail a whole workflow run.

The bounds here are deliberately tight: each `ChatOpenAI` call already has
its own hard per-attempt timeout (`Settings.llm_request_timeout_seconds`),
and every node in the graph runs synchronously inside a single HTTP
request/response - so the *total* worst case across every retry here has to
comfortably fit under whatever timeout the reverse proxy in front of this
app enforces (e.g. Cloudflare's free-tier ~100s edge timeout, which fires
as a 524 with no useful error body if we blow past it). 3 attempts x ~20s
+ short backoff keeps the worst case well under that even with a fully
congested free model, at the cost of slightly less retry depth than an
uncapped backend would allow.
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
    wait=wait_exponential_jitter(initial=2, max=10),
    stop=stop_after_attempt(3),
    before_sleep=_log_retry,
    reraise=True,
)
def invoke_with_retry(model, messages):
    """Drop-in replacement for `model.invoke(messages)` with retry/backoff
    on rate-limit and transient connection errors."""
    return model.invoke(messages)
