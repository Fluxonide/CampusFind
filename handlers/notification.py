"""
/notification — Manage category subscriptions.

Flow:  choose subscribe/unsubscribe → pick categories → done
"""

from __future__ import annotations

import asyncio

from aiogram import Bot, Router
from aiogram.types import (
    CallbackQuery,
    Message,
)
from aiogram.fsm.context import FSMContext

from core.logger import get_logger
from database import services as db
from keyboards.inline import (
    CATEGORIES,
    notification_action_keyboard,
    notify_subscribe_keyboard,
    unsubscribe_keyboard,
)
from states.forms import NotificationForm

logger = get_logger(__name__)

router = Router(name="notification")


# ── Helpers ─────────────────────────────────────────────


async def _delete_msg(bot: Bot, chat_id: int, msg_id: int | None) -> None:
    if msg_id is None:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass


async def _delete_after_delay(bot: Bot, chat_id: int, message_id: int, delay: int = 15) -> None:
    await asyncio.sleep(delay)
    await _delete_msg(bot, chat_id, message_id)


# ── /notification Entry ─────────────────────────────────


@router.message(lambda message: message.text == "/notification")
async def cmd_notification(message: Message, state: FSMContext) -> None:
    await state.clear()  # Reset any stuck FSM flow
    msg = await message.answer(
        "What would you like to do?",
        reply_markup=notification_action_keyboard(),
    )
    await state.update_data(
        what_would_message=msg.message_id,
        notification_chat_id=message.chat.id,
    )
    await state.set_state(NotificationForm.action)


# ── Subscribe / Unsubscribe Choice ──────────────────────


@router.callback_query(lambda c: c.data in ("notify_subscribe", "notify_unsubscribe"))
async def handle_notification_action(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    action = callback.data.split("_")[1]  # type: ignore[union-attr]
    data = await state.get_data()

    await _delete_msg(bot, data.get("notification_chat_id", callback.message.chat.id), data.get("what_would_message"))  # type: ignore[union-attr]

    if action == "subscribe":
        search_msg = await callback.message.answer(  # type: ignore[union-attr]
            "📂 Select a category to subscribe:",
            reply_markup=notify_subscribe_keyboard(),
        )
        await state.update_data(search_prompt_message=search_msg.message_id)
        await state.set_state(NotificationForm.subscribe)
    else:
        # Show current subscriptions
        subscriptions = await db.get_subscriptions(callback.from_user.id)
        if not subscriptions:
            await callback.message.answer("You have no active subscriptions.")  # type: ignore[union-attr]
            await state.clear()
            return

        await callback.message.answer(  # type: ignore[union-attr]
            "Tap categories to unsubscribe:",
            reply_markup=unsubscribe_keyboard(subscriptions),
        )
        await state.set_state(NotificationForm.unsubscribe)


# ── Handle Subscription Selection ───────────────────────


@router.callback_query(NotificationForm.subscribe, lambda c: c.data and c.data.startswith("SELECTED_SUB:"))
async def handle_subscription_selection(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    raw = callback.data.replace("SELECTED_SUB:", "").strip()  # type: ignore[union-attr]
    category = CATEGORIES.get(raw)

    if not category:
        await callback.answer("Invalid category")
        return

    try:
        await db.subscribe(callback.from_user.id, raw)
        success_msg = await callback.message.answer(f"✅ Subscribed to {category} notifications!")  # type: ignore[union-attr]
        asyncio.create_task(
            _delete_after_delay(bot, callback.message.chat.id, success_msg.message_id)  # type: ignore[union-attr]
        )
    except Exception as exc:
        await callback.answer("❌ Failed to subscribe")
        logger.error("Subscription error: %s", exc)

    data = await state.get_data()
    await _delete_msg(bot, callback.message.chat.id, data.get("search_prompt_message"))  # type: ignore[union-attr]
    await callback.message.delete()  # type: ignore[union-attr]

    await state.clear()
    await callback.answer()


# ── Unsubscribe ─────────────────────────────────────────


@router.callback_query(lambda c: c.data is not None and c.data.startswith("unsub_"))
async def handle_unsubscribe(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    payload = callback.data.split("_", 1)[1]  # type: ignore[union-attr]

    if payload == "finish":
        await callback.message.delete()  # type: ignore[union-attr]
        success_msg = await callback.message.answer("✅ Subscription settings updated")  # type: ignore[union-attr]
        asyncio.create_task(
            _delete_after_delay(bot, success_msg.chat.id, success_msg.message_id)
        )
        await state.clear()
        return

    # Remove the subscription
    category = payload
    try:
        await db.unsubscribe(callback.from_user.id, category)

        # Refresh the keyboard
        subscriptions = await db.get_subscriptions(callback.from_user.id)
        await callback.message.edit_reply_markup(  # type: ignore[union-attr]
            reply_markup=unsubscribe_keyboard(subscriptions)
        )
    except Exception as exc:
        await callback.answer("Error updating subscription")
        logger.error("Unsubscription error: %s", exc)
