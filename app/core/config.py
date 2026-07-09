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
