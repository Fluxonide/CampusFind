"""
/lost — Search for lost items.

Flow:  category (inline search) → days → forward matching items from channel
Also contains the shared inline-query handler for category selection.
"""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.types import (
    CallbackQuery,
    Message,
)
from aiogram.fsm.context import FSMContext

from core.config import settings
from core.logger import get_logger
from database import services as db
from keyboards.inline import (
    CATEGORIES,
    category_filter_keyboard,
    hide_orders_keyboard,
)
from states.forms import FilterForm, SearchState

logger = get_logger(__name__)

router = Router(name="lost_item")


# ── Helpers ─────────────────────────────────────────────


async def _delete_msg(bot: Bot, chat_id: int, msg_id: int | None) -> None:
    if msg_id is None:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass


# ── /lost Entry ─────────────────────────────────────────


@router.message(lambda message: message.text == "/lost")
async def cmd_lost(message: Message, state: FSMContext) -> None:
    await state.clear()  # Reset any stuck FSM flow
    prompt_msg = await message.answer("🔍 Which category would you like to search?")
    await state.update_data(last_bot_message=prompt_msg.message_id)

    search_msg = await message.answer(
        "📂 Select a category:", reply_markup=category_filter_keyboard()
    )
    await state.update_data(search_prompt_message=search_msg.message_id)
    await state.set_state(FilterForm.category)


# ── Step 1: Category Selected ───────────────────────────


@router.callback_query(FilterForm.category, lambda c: c.data and c.data.startswith("FILTER_CATEGORY:"))
async def handle_filter_category(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    raw = callback.data.replace("FILTER_CATEGORY:", "").strip()  # type: ignore[union-attr]
    await state.update_data(filter_category=raw)

    data = await state.get_data()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    for key in ("last_bot_message", "search_prompt_message"):
        await _delete_msg(bot, chat_id, data.get(key))
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]

    days_msg = await callback.message.answer("📅 How many days back would you like to search?")  # type: ignore[union-attr]
    await state.update_data(days_message=days_msg.message_id)
    await state.set_state(FilterForm.days)
    await callback.answer()


# ── Step 2: Days ────────────────────────────────────────


@router.message(FilterForm.days)
async def handle_filter_days(message: Message, state: FSMContext, bot: Bot) -> None:
    days_text = (message.text or "").strip()
    data = await state.get_data()

    await _delete_msg(bot, message.chat.id, data.get("days_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)

    try:
        days = int(days_text)
    except ValueError:
        await message.answer("Please enter a valid number of days.")
        return

    category_key = data.get("filter_category", "other")
    message_ids = await db.get_items_by_category_and_days(category_key, days)

    if not message_ids:
        await message.answer(
            f"No items found in this category for the last {days} day(s)."
        )
        await state.clear()
        return

    sent_messages: list[int] = []
    for msg_id in message_ids:
        try:
            sent_msg = await bot.forward_message(
                chat_id=message.chat.id,
                from_chat_id=settings.channel_username,
                message_id=int(msg_id),
            )
            sent_messages.append(sent_msg.message_id)
        except Exception as exc:
            logger.error("Error forwarding message %s: %s", msg_id, exc)

    hide_msg = await message.answer(
        "Click below to hide these results:", reply_markup=hide_orders_keyboard()
    )

    await state.update_data(
        sent_messages=sent_messages,
        hide_button_message=hide_msg.message_id,
    )
    await state.set_state(SearchState.viewing)


# ── Hide Search Results ─────────────────────────────────


@router.callback_query(lambda c: c.data == "hide_orders")
async def handle_hide_orders(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()

    for msg_id in data.get("sent_messages", []):
        await _delete_msg(bot, callback.message.chat.id, msg_id)  # type: ignore[union-attr]

    await _delete_msg(
        bot,
        callback.message.chat.id,  # type: ignore[union-attr]
        data.get("hide_button_message"),
    )

    await state.clear()
    await callback.answer("All messages hidden")
