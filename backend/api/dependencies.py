"""
FastAPI dependencies shared across routers.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, committing on success and rolling back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
