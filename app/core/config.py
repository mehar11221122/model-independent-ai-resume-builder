"""Central application settings.

Everything that can vary between environments (which LLM provider/model to
use, which checkpoint backend, which storage backend, etc.) lives here as an
env-driven setting instead of being hard-coded. This is what keeps the engine
"model-independent": swapping a model or a backend is a `.env` change, not a
code change.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    # --- OpenRouter / model routing -----------------------------------
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    model_primary: str = "anthropic/claude-sonnet-4"
    model_fallback: str = "openai/gpt-4o"
    model_lightweight: str = "openai/gpt-4o-mini"

    # --- Secondary free-tier providers (independent quota pools) -------
    # OpenRouter's free daily quota (see README "Scaling past free quotas")
    # is one pool shared across every ":free" model on a single account, so
    # an OpenRouter "fallback" model adds redundancy against one model being
    # briefly congested but adds ZERO extra daily capacity once that shared
    # pool is exhausted. Groq and Google Gemini are separate companies with
    # their own, completely independent free daily quotas, and both expose
    # an OpenAI-compatible endpoint - so `get_model_with_fallback()` chains
    # them on as extra fallback links (see app/llm/router.py) whenever a key
    # is present here. Leave either blank to skip that provider entirely;
    # behavior is unchanged (OpenRouter-only) with both blank, which is the
    # default. Neither requires a credit card to sign up.
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model_primary: str = "llama-3.3-70b-versatile"
    groq_model_lightweight: str = "llama-3.1-8b-instant"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    # Newly-created Gemini API keys can get 404 "no longer available to new
    # users" on pinned model versions (e.g. gemini-2.5-flash) even though
    # they're still listed by the API - the "-latest" alias slugs are what
    # Google actually grants new free-tier keys access to. flash-lite is
    # used for both tiers here (not just lightweight) because gemini-flash-
    # latest itself was observed to be heavily congested (503s) on a fresh
    # key - lite is the more reliable of the two for this last-resort
    # fallback slot. Bump to gemini-flash-latest if your account handles it.
    gemini_model_primary: str = "gemini-flash-lite-latest"
    gemini_model_lightweight: str = "gemini-flash-lite-latest"

    # Hard per-attempt cap on a single LLM call. Without this, a congested
    # free-tier model can hang far longer than any reverse proxy in front of
    # this app is willing to wait (e.g. Cloudflare's ~100s edge timeout,
    # which fires as a 524 before our own retry/fallback logic ever gets a
    # chance to recover) - better to fail one attempt fast and let
    # `invoke_with_retry` retry/back off than to sit silently past that.
    llm_request_timeout_seconds: float = 20.0

    # --- Token/cost optimization ----------------------------------------
    # Explicit output-length ceilings per call type (see app/graph/nodes.py)
    # - "restrict output lengths" so a model can never ramble/repeat its way
    # into burning far more output tokens than the task genuinely needs.
    # Each is sized generously for its task's realistic worst case (e.g. a
    # long multi-job resume), not tightly, so this is a safety ceiling, not
    # a quality-limiting truncation.
    max_tokens_extract: int = 2000
    max_tokens_check_answers: int = 800
    max_tokens_tool_use: int = 500
    max_tokens_generate: int = 3000

    # Exact-match (hash-based) response cache for LLM calls - see
    # app/llm/cache.py. Skips the model entirely (zero tokens, zero
    # quota/latency) when an identical (tier, prompt, messages) call was
    # already made recently. Only ever matches byte-identical input, so
    # there's no cross-user "cache poisoning" risk to guard against the way
    # there would be with semantic/embedding-based caching. Safe to disable
    # for debugging or if you need every call to genuinely hit the model.
    llm_cache_enabled: bool = True
    llm_cache_max_entries: int = 512
    llm_cache_ttl_seconds: float = 3600.0

    # --- Checkpointing / state persistence -----------------------------
    checkpoint_backend: Literal["memory", "sqlite", "postgres"] = "sqlite"
    sqlite_checkpoint_path: str = "./data/checkpoints.sqlite"
    postgres_dsn: str = "postgresql://user:password@localhost:5432/ai_engine"

    # --- OCR -------------------------------------------------------------
    ocr_backend: Literal["tesseract", "google_vision", "aws_textract"] = "tesseract"
    tesseract_cmd: str = ""

    # --- Storage ---------------------------------------------------------
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: str = "./data/uploads"
    aws_s3_bucket: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_endpoint_url: str = ""  # set for Cloudflare R2 / other S3-compatible providers

    # --- Auth --------------------------------------------------------------
    api_auth_enabled: bool = False
    api_key: str = "change-me"

    # --- Observability -------------------------------------------------
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "ai-engine"


@lru_cache
def get_settings() -> Settings:
    return Settings()
