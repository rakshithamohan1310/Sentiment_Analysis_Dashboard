"""
Async SQLAlchemy engine and session factory.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config.settings import get_settings

_settings = get_settings()

_engine_kwargs: dict = {"echo": _settings.app_env == "development"}
if not _settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)

engine = create_async_engine(_settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
