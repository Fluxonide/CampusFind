"""
Database schema initialisation.

Tables:
    users              – every user who has pressed /start
    found_items        – items reported via /found
    user_subscriptions – notification subscriptions per category
"""

from __future__ import annotations

from database.connection import get_db
from core.logger import get_logger

logger = get_logger(__name__)


async def init_db() -> None:
    """Create tables if they do not already exist."""
    async with get_db() as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS found_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                category   TEXT     NOT NULL,
                message_id TEXT     NOT NULL,
                date       DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                user_id  INTEGER NOT NULL,
                category TEXT    NOT NULL,
                PRIMARY KEY (user_id, category)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS lost_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                category   TEXT     NOT NULL,
                message_id TEXT     NOT NULL,
                date       DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    logger.info("Database tables initialised")
