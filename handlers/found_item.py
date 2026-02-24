"""
/found — Report a found item.

Flow:  photo → category (inline search) → summary (with edit options) → confirm & submit
Also handles editing individual fields and notifying subscribers.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import Bot, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from core.config import settings
from core.logger import get_logger
from database import services as db
from keyboards.inline import (
    CATEGORIES,
    category_select_keyboard,
    channel_found_keyboard,
    confirm_edit_keyboard,
    notification_delete_keyboard,
)
from states.forms import EditingForm, FoundItemForm, FilterForm

logger = get_logger(__name__)

router = Router(name="found_item")


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


async def _show_summary(message: Message, data: dict, state: FSMContext, bot: Bot) -> None:
    """Display (or re-display) the form summary with edit/confirm buttons."""
    # Clean up previous summary messages
    await _delete_msg(bot, message.chat.id, data.get("summary_message"))
    await _delete_msg(bot, message.chat.id, data.get("buttons_message"))

    summary = (
        f"📄 <b>Review Your Form:</b>\n"
        f"<b>Category:</b> {data.get('category', '-')}\n"
        f"<b>Location:</b> {data.get('location', '-')}\n"
        f"<b>Comments:</b> {data.get('comments', '-')}"
    )

    if data.get("photo"):
        new_summary_msg = await message.answer_photo(
            photo=data["photo"], caption=summary, parse_mode=ParseMode.HTML
        )
    else:
        new_summary_msg = await message.answer(summary, parse_mode=ParseMode.HTML)

    new_buttons_msg = await message.answer(
        "Is everything correct?", reply_markup=confirm_edit_keyboard(data)
    )

    await state.update_data(
        summary_message=new_summary_msg.message_id,
        buttons_message=new_buttons_msg.message_id,
    )


# ── /found Entry ────────────────────────────────────────


@router.message(lambda message: message.text == "/found")
async def cmd_found(message: Message, state: FSMContext) -> None:
    await state.clear()  # Reset any stuck FSM flow
    await state.set_state(FoundItemForm.photo)
    msg = await message.answer("📸 Please send a photo of the item you found.")
    await state.update_data(last_bot_message=msg.message_id)


@router.callback_query(lambda c: c.data == "makeOrder")
async def start_make_order(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FoundItemForm.photo)
    await callback.message.edit_text("📸 Please send a photo of the item you found.")  # type: ignore[union-attr]
    await state.update_data(last_bot_message=callback.message.message_id)  # type: ignore[union-attr]


# ── Step 1: Photo ───────────────────────────────────────


@router.message(FoundItemForm.photo, lambda message: not (message.text and message.text.startswith("/")))
async def receive_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.photo:
        await message.answer("Please send a valid photo.")
        return

    await state.update_data(photo=message.photo[-1].file_id)
    data = await state.get_data()

    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)

    msg = await message.answer(
        "📂 Select a category:", reply_markup=category_select_keyboard()
    )
    await state.update_data(last_bot_message=msg.message_id)
    await state.set_state(FoundItemForm.category)


# ── Step 2: Category (via inline query) ─────────────────

# The inline query handler for category selection is shared between
# /found and /lost and lives in lost_item.py — it uses SELECTED_CATEGORY:
# for found items and FILTER_CATEGORY: for lost-item searches.


@router.callback_query(FoundItemForm.category, lambda c: c.data and c.data.startswith("SELECTED_CATEGORY:"))
async def handle_category_selection(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    raw = callback.data.replace("SELECTED_CATEGORY:", "").strip()  # type: ignore[union-attr]
    category_name = CATEGORIES.get(raw, "Unknown")

    await state.update_data(category=category_name)
    data = await state.get_data()

    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    await _delete_msg(bot, chat_id, data.get("last_bot_message"))
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]

    await _show_summary(callback.message, data, state, bot)  # type: ignore[union-attr]
    await callback.answer()


# ── Editing ─────────────────────────────────────────────


@router.callback_query(lambda c: c.data is not None and c.data.startswith("edit_"))
async def handle_edit(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    action = callback.data.replace("edit_", "")  # type: ignore[union-attr]
    chat_id = callback.message.chat.id  # type: ignore[union-attr]

    if action == "photo":
        msg = await callback.message.answer("📸 Please send a new photo.")  # type: ignore[union-attr]
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(EditingForm.photo)
    elif action == "category":
        msg = await callback.message.answer(  # type: ignore[union-attr]
            "📂 Select a category:", reply_markup=category_select_keyboard()
        )
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(EditingForm.category)
    elif action == "location":
        msg = await callback.message.answer(  # type: ignore[union-attr]
            'Where was it found? (Type "-" to skip)'
        )
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(EditingForm.location)
    elif action == "comments":
        msg = await callback.message.answer(  # type: ignore[union-attr]
            'Add or edit your comments: (Type "-" to skip)'
        )
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(EditingForm.comments)

    data = await state.get_data()
    await _delete_msg(bot, chat_id, data.get("summary_message"))
    await _delete_msg(bot, chat_id, data.get("buttons_message"))
    await callback.answer()


@router.message(EditingForm.photo, lambda message: not (message.text and message.text.startswith("/")))
async def update_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.photo:
        await message.answer("Please send a valid photo.")
        return

    await state.update_data(photo=message.photo[-1].file_id)
    data = await state.get_data()
    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)
    await _show_summary(message, data, state, bot)


@router.callback_query(EditingForm.category, lambda c: c.data and c.data.startswith("SELECTED_CATEGORY:"))
async def update_category(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    raw = callback.data.replace("SELECTED_CATEGORY:", "").strip()  # type: ignore[union-attr]
    category_name = CATEGORIES.get(raw, "Unknown")
    await state.update_data(category=category_name)
    data = await state.get_data()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    await _delete_msg(bot, chat_id, data.get("last_bot_message"))
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]
    await _show_summary(callback.message, data, state, bot)  # type: ignore[union-attr]
    await callback.answer()


@router.message(EditingForm.location, lambda message: not (message.text and message.text.startswith("/")))
async def update_location(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.strip() != "-":
        await state.update_data(location=message.text)
    data = await state.get_data()
    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)
    await _show_summary(message, data, state, bot)


@router.message(EditingForm.comments, lambda message: not (message.text and message.text.startswith("/")))
async def update_comments(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.strip() != "-":
        await state.update_data(comments=message.text)
    data = await state.get_data()
    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)
    await _show_summary(message, data, state, bot)


# ── Confirm & Submit ────────────────────────────────────


@router.callback_query(lambda c: c.data == "confirm_submit")
async def confirm_submission(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]

    # Resolve category key from display name
    category_key = next(
        (k for k, v in CATEGORIES.items() if v == data.get("category")), "other"
    )

    summary_for_channel = (
        f"Location: {data.get('location', '-')}\n"
        f"Comments: {data.get('comments', '-')}\n"
        f"Date: {datetime.now().date()}"
    )

    try:
        # Post to the shared channel
        sent_msg = await bot.send_photo(
            chat_id=settings.channel_username,
            photo=data["photo"],
            caption=summary_for_channel,
        )

        # Add the "Mark as Found" button (needs message_id from sent_msg)
        await bot.edit_message_reply_markup(
            chat_id=settings.channel_username,
            message_id=sent_msg.message_id,
            reply_markup=channel_found_keyboard(sent_msg.message_id),
        )

        # Save to DB
        await db.add_found_item(category_key, sent_msg.message_id)

        # Notify subscribers
        subscribers = await db.get_subscribers(category_key)
        for user_id in subscribers:
            try:
                notification_msg = await bot.send_photo(
                    chat_id=user_id,
                    photo=data["photo"],
                    caption=(
                        f"🔔 New item found in {data.get('category')}:\n\n"
                        f"{summary_for_channel}"
                    ),
                )
                await bot.send_message(
                    chat_id=user_id,
                    text="Tap below to delete this notification",
                    reply_markup=notification_delete_keyboard(notification_msg.message_id),
                )
            except Exception as exc:
                logger.warning("Failed to notify user %s: %s", user_id, exc)

        # Clean up UI
        success_msg = await callback.message.answer("✅ Form submitted successfully!")  # type: ignore[union-attr]
        await _delete_msg(bot, chat_id, data.get("summary_message"))
        await _delete_msg(bot, chat_id, data.get("buttons_message"))

        asyncio.create_task(
            _delete_after_delay(bot, chat_id, success_msg.message_id, delay=15)
        )

    except Exception as exc:
        await callback.message.answer("⚠️ Failed to submit form")  # type: ignore[union-attr]
        logger.error("Submission error: %s", exc)

    await state.clear()
    await callback.answer()


# ── Notification Delete ─────────────────────────────────


@router.callback_query(lambda c: c.data is not None and c.data.startswith("notif_delete_"))
async def handle_notification_delete(callback: CallbackQuery, bot: Bot) -> None:
    msg_id = int(callback.data.split("_")[-1])  # type: ignore[union-attr]
    try:
        await bot.delete_message(callback.message.chat.id, msg_id)  # type: ignore[union-attr]
        await callback.message.delete()  # type: ignore[union-attr]
    except Exception as exc:
        logger.error("Error deleting notification: %s", exc)
    await callback.answer("Notification deleted")
