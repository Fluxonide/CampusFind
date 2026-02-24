"""
Bot entry point.

Initialises the database, registers all handler routers, and starts polling.
"""

from __future__ import annotations

import asyncio
import sys

# Prevent aiohttp from using aiodns (which fails to resolve properly on this Windows network)
sys.modules["aiodns"] = None

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import settings
from core.logger import get_logger
from database.models import init_db

# Import routers
from handlers.common import router as common_router
from handlers.found_item import router as found_item_router
from handlers.lost_item import router as lost_item_router
from handlers.notification import router as notification_router
from handlers.admin import router as admin_router
from utils.calendar import router as calendar_router

logger = get_logger(__name__)


async def main() -> None:
    logger.info("Starting Lost & Found bot …")

    # Initialise database tables
    await init_db()

    # Create bot instance
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Create dispatcher and register routers
    dp = Dispatcher()

    # Order matters: common first so /start & /help always work regardless of FSM state
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(notification_router)
    dp.include_router(found_item_router)
    dp.include_router(lost_item_router)
    dp.include_router(calendar_router)

    logger.info("All routers registered — starting polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
