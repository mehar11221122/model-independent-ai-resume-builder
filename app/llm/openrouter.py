"""OpenRouter-backed chat model factory.

OpenRouter is our default/primary provider - see `app/llm/providers.py` for
the generic OpenAI-compatible client this builds on, and `app/llm/router.py`
for how it's chained with independent secondary providers (Groq, Gemini) as
capacity fallbacks.
"""
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.llm.providers import ProviderCredentials, build_chat_model


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

    creds = ProviderCredentials(
        name="openrouter",
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    return build_chat_model(creds, model, temperature=temperature, **kwargs)
