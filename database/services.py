"""
Database CRUD service functions.

Every function opens its own connection via get_db() so handlers
never have to manage connections themselves.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from database.connection import get_db
from core.logger import get_logger

logger = get_logger(__name__)


# ── Users ───────────────────────────────────────────────


async def register_user(user_id: int) -> None:
    """Register a user (no-op if they already exist)."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,),
        )


async def get_all_user_ids() -> list[int]:
    """Return a list of every registered user ID."""
    async with get_db() as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


# ── Found Items ─────────────────────────────────────────


async def add_found_item(category: str, message_id: int) -> None:
    """Insert a new found-item record."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO found_items (category, message_id, date) VALUES (?, ?, ?)",
            (category, str(message_id), datetime.now()),
        )


async def get_all_items() -> list[dict]:
    """Return every found item, newest first."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT message_id, category, date FROM found_items ORDER BY date DESC"
        )
        rows = await cursor.fetchall()
        return [
            {"message_id": row[0], "category": row[1], "date": row[2]}
            for row in rows
        ]


async def get_items_by_category_and_days(
    category: str, max_days_back: int
) -> list[str]:
    """Return message IDs matching *category* within the last *max_days_back* days."""
    cutoff = (datetime.now() - timedelta(days=max_days_back)).date()
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT message_id FROM found_items
            WHERE category = ? AND DATE(date) >= DATE(?)
            ORDER BY date DESC
            """,
            (category, str(cutoff)),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_category_count(category: str) -> int:
    """Return total number of items in a category."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM found_items WHERE category = ?",
            (category,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def delete_item(message_id: str) -> None:
    """Delete a found-item record by its message_id."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM found_items WHERE message_id = ?",
            (message_id,),
        )


# ── Subscriptions ───────────────────────────────────────


async def subscribe(user_id: int, category: str) -> None:
    """Subscribe a user to a category (no-op if already subscribed)."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_subscriptions (user_id, category) VALUES (?, ?)",
            (user_id, category),
        )


async def unsubscribe(user_id: int, category: str) -> None:
    """Remove a subscription."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM user_subscriptions WHERE user_id = ? AND category = ?",
            (user_id, category),
        )


async def get_subscriptions(user_id: int) -> list[str]:
    """Return category slugs the user is subscribed to."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT DISTINCT category FROM user_subscriptions WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_subscribers(category: str) -> list[int]:
    """Return user IDs subscribed to a category."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT DISTINCT user_id FROM user_subscriptions WHERE category = ?",
            (category,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
