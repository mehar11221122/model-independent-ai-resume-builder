"""Model routing: pick the right model tier for a given workflow step.

The scope document calls for routing lighter/cheaper models to
extraction & classification steps, and the strongest reasoning model only
where it is actually needed (generation). This module centralizes that
decision so node code never hard-codes a model name.
"""
from enum import Enum

from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.llm.openrouter import get_chat_model


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


def get_model_with_fallback(tier: ModelTier, **kwargs) -> ChatOpenAI:
    """Primary model with automatic fallback to the configured fallback model.

    Uses LangChain's built-in `.with_fallbacks()` so a provider outage or
    rate-limit on the primary model doesn't fail the whole workflow step.
    """
    primary = get_model_for_tier(tier, **kwargs)
    if tier == ModelTier.FALLBACK:
        return primary
    fallback = get_model_for_tier(ModelTier.FALLBACK, **kwargs)
    return primary.with_fallbacks([fallback])
