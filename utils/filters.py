"""
Custom aiogram filters.
"""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union

from core.config import settings


class IsAdmin(BaseFilter):
    """Pass only if the user's ID is in the configured ADMIN_IDS list."""

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user = event.from_user
        return user is not None and user.id in settings.admin_ids
