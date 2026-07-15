"""Model routing: pick the right model tier for a given workflow step, and
chain in independent-quota providers so a single exhausted free quota does
not stall the whole engine.

The scope document calls for routing lighter/cheaper models to
extraction & classification steps, and the strongest reasoning model only
where it is actually needed (generation). This module centralizes that
decision so node code never hard-codes a model name.

Fallback chain per tier: OpenRouter primary -> OpenRouter fallback model ->
Groq (if configured) -> Gemini (if configured). The OpenRouter pair only
guards against one specific model being briefly down or congested - it does
NOT add daily capacity, because every ":free" OpenRouter model draws from the
same one account-level daily quota (see README "Scaling past free quotas").
Groq and Gemini are separate companies with their own independent free daily
quotas, so chaining them on is what actually raises the effective ceiling for
real launch traffic. Both are optional: leave their API keys blank in `.env`
and behavior is unchanged (OpenRouter-only).
"""
from enum import Enum

from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.llm.openrouter import get_chat_model
from app.llm.providers import ProviderCredentials, build_chat_model


class ModelTier(str, Enum):
    PRIMARY = "primary"       # strongest reasoning/generation model (e.g. Claude Sonnet 4)
    FALLBACK = "fallback"     # redundancy / A-B testing model
    LIGHTWEIGHT = "lightweight"  # cheap/fast model for extraction & classification


def get_model_for_tier(tier: ModelTier, **kwargs) -> ChatOpenAI:
    settings = get_settings()
    slug = {
        ModelTier.PRIMARY: settings.model_primary,
        ModelTier.FALLBACK: settings.model_fallback,
        ModelTier.LIGHTWEIGHT: settings.model_lightweight,
    }[tier]
    return get_chat_model(slug, **kwargs)


def _secondary_provider_models(tier: ModelTier, **kwargs) -> list[ChatOpenAI]:
    """Extra fallback links onto providers with their own independent daily
    quota, in priority order. Skips any provider whose API key isn't set."""
    settings = get_settings()
    models: list[ChatOpenAI] = []

    if settings.groq_api_key:
        slug = (
            settings.groq_model_lightweight
            if tier == ModelTier.LIGHTWEIGHT
            else settings.groq_model_primary
        )
        creds = ProviderCredentials(
            name="groq", api_key=settings.groq_api_key, base_url=settings.groq_base_url
        )
        models.append(build_chat_model(creds, slug, **kwargs))

    if settings.gemini_api_key:
        slug = (
            settings.gemini_model_lightweight
            if tier == ModelTier.LIGHTWEIGHT
            else settings.gemini_model_primary
        )
        creds = ProviderCredentials(
            name="gemini", api_key=settings.gemini_api_key, base_url=settings.gemini_base_url
        )
        models.append(build_chat_model(creds, slug, **kwargs))

    return models


def get_model_with_fallback(tier: ModelTier, **kwargs) -> ChatOpenAI:
    """Primary model with automatic fallback across the OpenRouter fallback
    model, then any configured secondary providers (Groq, Gemini).

    Uses LangChain's built-in `.with_fallbacks()`, so a rate-limit or outage
    hit on one link transparently spills over to the next - including across
    providers, which is what turns "one exhausted free quota" into "still
    working, just on a different provider's quota" instead of a failed
    request.
    """
    primary = get_model_for_tier(tier, **kwargs)
    if tier == ModelTier.FALLBACK:
        # This tier IS itself a fallback target for PRIMARY/LIGHTWEIGHT -
        # don't chain it onto itself.
        return primary

    fallbacks = [get_model_for_tier(ModelTier.FALLBACK, **kwargs)]
    fallbacks.extend(_secondary_provider_models(tier, **kwargs))
    return primary.with_fallbacks(fallbacks)
