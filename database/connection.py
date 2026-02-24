"""
Async SQLite connection helper using aiosqlite.

Usage:
    from database.connection import get_db
    async with get_db() as db:
        await db.execute(...)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

from core.config import settings


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield an aiosqlite connection with row_factory enabled."""
    db = await aiosqlite.connect(settings.db_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
