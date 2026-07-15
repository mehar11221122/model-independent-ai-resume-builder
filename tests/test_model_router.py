"""Unit tests for `app.llm.router`'s multi-provider fallback chain.

OpenRouter's free daily quota is shared across every ":free" model on one
account, so these tests exist to lock in the actual fix for that: Groq/
Gemini being chained on as EXTRA fallback links (independent quota pools),
not just another OpenRouter model.
"""
from app.core.config import get_settings
from app.llm.router import ModelTier, get_model_with_fallback


def _reset_settings_cache(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()


def test_primary_tier_falls_back_to_openrouter_fallback_only_by_default(monkeypatch):
    _reset_settings_cache(monkeypatch)

    model = get_model_with_fallback(ModelTier.PRIMARY)

    assert len(model.fallbacks) == 1
    assert model.fallbacks[0].model_name == get_settings().model_fallback


def test_primary_tier_chains_groq_when_configured(monkeypatch):
    _reset_settings_cache(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    get_settings.cache_clear()

    model = get_model_with_fallback(ModelTier.PRIMARY)

    assert len(model.fallbacks) == 2
    groq_model = model.fallbacks[1]
    assert groq_model.model_name == get_settings().groq_model_primary
    assert "groq.com" in str(groq_model.openai_api_base)


def test_primary_tier_chains_both_secondary_providers_when_configured(monkeypatch):
    _reset_settings_cache(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_test")
    get_settings.cache_clear()

    model = get_model_with_fallback(ModelTier.PRIMARY)

    assert len(model.fallbacks) == 3
    assert model.fallbacks[1].model_name == get_settings().groq_model_primary
    assert model.fallbacks[2].model_name == get_settings().gemini_model_primary
    assert "generativelanguage.googleapis.com" in str(model.fallbacks[2].openai_api_base)


def test_lightweight_tier_uses_lightweight_slugs_for_secondary_providers(monkeypatch):
    _reset_settings_cache(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    get_settings.cache_clear()

    model = get_model_with_fallback(ModelTier.LIGHTWEIGHT)

    assert model.fallbacks[1].model_name == get_settings().groq_model_lightweight


def test_fallback_tier_does_not_chain_onto_itself(monkeypatch):
    _reset_settings_cache(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    get_settings.cache_clear()

    model = get_model_with_fallback(ModelTier.FALLBACK)

    assert not hasattr(model, "fallbacks") or model.fallbacks == []
