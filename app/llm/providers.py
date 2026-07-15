"""Generic OpenAI-compatible chat model factory.

OpenRouter, Groq, and Google Gemini (via its OpenAI-compatibility endpoint)
all speak the same OpenAI-style chat-completions API, so a single
`ChatOpenAI` client works against any of them - "a provider" is nothing more
than a base_url + api_key + model slug. This is the piece that makes the
engine genuinely provider-independent (not just model-independent within one
gateway): adding, swapping, or removing a whole provider is a config change
here and in `app/core/config.py`, never a change to node code.
"""
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from app.core.config import get_settings


@dataclass(frozen=True)
class ProviderCredentials:
    name: str
    api_key: str
    base_url: str


def build_chat_model(
    creds: ProviderCredentials, model: str, *, temperature: float = 0.2, **kwargs
) -> ChatOpenAI:
    """Build a `ChatOpenAI` bound to an arbitrary OpenAI-compatible provider.

    Args:
        creds: Which provider to hit (api key + base url).
        model: That provider's own model slug/name (providers do not share a
            slug namespace - e.g. OpenRouter's "meta-llama/llama-3.3-70b" vs.
            Groq's "llama-3.3-70b-versatile" for a similar underlying model).
        temperature: Sampling temperature.
        **kwargs: Passed through to `ChatOpenAI` (e.g. max_tokens, timeout).
    """
    settings = get_settings()
    kwargs.setdefault("timeout", settings.llm_request_timeout_seconds)
    # The underlying openai SDK client has its OWN internal retry-on-429
    # behavior, which honors the provider's `Retry-After` header (observed:
    # 26-30s sleeps against OpenRouter's free-tier limiter) - completely
    # independent of, and BEFORE, our own `invoke_with_retry`/`.with_fallbacks()`
    # logic ever gets a chance to fail over to the next provider. Left at
    # its default it can single-handedly blow well past any gateway timeout
    # sitting in front of this app. Disabling it here means a 429 surfaces
    # immediately, so our own (much faster) fallback chain takes over.
    kwargs.setdefault("max_retries", 0)

    return ChatOpenAI(
        model=model,
        api_key=creds.api_key,
        base_url=creds.base_url,
        temperature=temperature,
        default_headers={
            # Harmless on Groq/Gemini (unrecognized headers are ignored);
            # OpenRouter uses these for attribution / rate-limit tiers.
            "HTTP-Referer": "https://github.com/",
            "X-Title": "Model-Independent AI Engine",
        },
        **kwargs,
    )
