"""OpenRouter-backed chat model factory.

OpenRouter exposes an OpenAI-compatible API, so we reuse LangChain's
`ChatOpenAI` client and simply point it at OpenRouter's base URL. This is the
single place in the codebase that knows how to talk to "an LLM provider" -
every provider swap (OpenAI <-> Anthropic <-> Google <-> anything else
OpenRouter lists) happens by changing a model slug string, never this code.
"""
from langchain_openai import ChatOpenAI

from app.core.config import get_settings


def get_chat_model(model: str, *, temperature: float = 0.2, **kwargs) -> ChatOpenAI:
    """Return a LangChain chat model bound to a specific OpenRouter model slug.

    Args:
        model: OpenRouter model slug, e.g. "anthropic/claude-sonnet-4".
        temperature: Sampling temperature.
        **kwargs: Passed through to ChatOpenAI (e.g. max_tokens).
    """
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=temperature,
        default_headers={
            # Recommended by OpenRouter for attribution / rate-limit tiers.
            "HTTP-Referer": "https://github.com/",
            "X-Title": "Model-Independent AI Engine",
        },
        **kwargs,
    )
