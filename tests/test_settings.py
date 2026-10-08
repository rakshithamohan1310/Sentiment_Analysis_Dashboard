"""
Tests that missing / empty credentials never crash the app and are handled cleanly.
"""
from __future__ import annotations

import os
from unittest.mock import patch


def test_empty_reddit_credentials_treated_as_none():
    """Empty string env vars for Reddit should be coerced to None."""
    with patch.dict(os.environ, {
        "REDDIT_CLIENT_ID": "",
        "REDDIT_CLIENT_SECRET": "",
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
        "AUTHOR_HASH_SALT": "test_salt",
    }):
        # Re-import to pick up patched env
        from importlib import reload
        import backend.config.settings as settings_module
        settings_module.get_settings.cache_clear()
        settings = settings_module.Settings(
            reddit_client_id="",
            reddit_client_secret="",
            youtube_api_key="",
        )
        assert settings.reddit_client_id is None
        assert settings.reddit_client_secret is None
        assert settings.reddit_configured is False


def test_empty_youtube_key_treated_as_none():
    """Empty YOUTUBE_API_KEY should mean youtube_configured is False."""
    from backend.config.settings import Settings
    settings = Settings(youtube_api_key="")
    assert settings.youtube_api_key is None
    assert settings.youtube_configured is False


def test_reddit_configured_true_with_both_keys():
    from backend.config.settings import Settings
    settings = Settings(reddit_client_id="client_id", reddit_client_secret="client_secret")
    assert settings.reddit_configured is True


def test_youtube_configured_true_with_key():
    from backend.config.settings import Settings
    settings = Settings(youtube_api_key="some_api_key")
    assert settings.youtube_configured is True


def test_sync_database_url_replaces_asyncpg():
    from backend.config.settings import Settings
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/db"
    )
    assert "asyncpg" not in settings.sync_database_url
    assert "psycopg2" in settings.sync_database_url


def test_sync_database_url_handles_plain_postgresql():
    from backend.config.settings import Settings
    settings = Settings(database_url="postgresql://user:pass@localhost:5432/db")
    assert "psycopg2" in settings.sync_database_url
