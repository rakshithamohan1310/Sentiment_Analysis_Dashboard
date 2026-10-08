"""
Application settings loaded from environment variables.
All secrets live in .env (never committed). See .env.example.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://pipeline:changeme@localhost:5432/reviews_db"
    )

    @property
    def sync_database_url(self) -> str:
        """psycopg2 URL for Alembic CLI (asyncpg not supported by Alembic)."""
        return self.database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        ).replace("postgresql://", "postgresql+psycopg2://")

    # ── Security ──────────────────────────────────────────────
    author_hash_salt: str = "dev_salt_replace_in_prod"

    # ── Reddit ────────────────────────────────────────────────
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "ReviewPipeline/0.1"

    # ── YouTube ───────────────────────────────────────────────
    youtube_api_key: Optional[str] = None
    youtube_quota_buffer: int = 500

    # ── Collection ────────────────────────────────────────────
    default_max_records: int = 500

    # ── Phase 2: Processing ───────────────────────────────────
    # Records to process per batch in process_pending()
    processing_batch_size: int = 100

    # HuggingFace model ID or local path.
    # Set to "lexicon" to force the rule-based fallback (no download).
    sentiment_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"

    # Minimum keyword-overlap ratio to keep a record (0.0 = keep everything)
    min_relevance_score: float = 0.0

    # Jaccard similarity threshold for near-duplicate detection (0.0 = disabled)
    near_duplicate_threshold: float = 0.85

    # ── App ───────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"

    # ── Validators ────────────────────────────────────────────
    @field_validator(
        "reddit_client_id", "reddit_client_secret", "youtube_api_key",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, v: Optional[str]) -> Optional[str]:
        return None if v == "" else v

    # ── Derived properties ────────────────────────────────────
    @property
    def reddit_configured(self) -> bool:
        return bool(self.reddit_client_id and self.reddit_client_secret)

    @property
    def youtube_configured(self) -> bool:
        return bool(self.youtube_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
