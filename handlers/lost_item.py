"""
/lost — Search for found items OR report a lost item.

When the user types /lost, they get two options:
  1. Search found items (existing flow)
  2. Report a lost item (new flow: photo → category → summary → confirm → post to channel)
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import Bot, Router
from aiogram.types import (
    CallbackQuery,
    Message,
)
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from core.config import settings
from core.logger import get_logger
from database import services as db
from keyboards.inline import (
    CATEGORIES,
    category_filter_keyboard,
    channel_found_keyboard,
    hide_orders_keyboard,
    lost_action_keyboard,
    lost_category_select_keyboard,
    lost_confirm_edit_keyboard,
    lost_skip_photo_keyboard,
)
from states.forms import FilterForm, LostEditingForm, LostItemForm, SearchState

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


async def _delete_after_delay(bot: Bot, chat_id: int, message_id: int, delay: int = 15) -> None:
    await asyncio.sleep(delay)
    await _delete_msg(bot, chat_id, message_id)


async def _show_lost_summary(message: Message, data: dict, state: FSMContext, bot: Bot) -> None:
    """Display (or re-display) the lost item form summary with edit/confirm buttons."""
    await _delete_msg(bot, message.chat.id, data.get("summary_message"))
    await _delete_msg(bot, message.chat.id, data.get("buttons_message"))

    summary = (
        f"📄 <b>Review Your Lost Item Report:</b>\n"
        f"<b>Category:</b> {data.get('category', '-')}\n"
        f"<b>Location:</b> {data.get('location', '-')}\n"
        f"<b>Contact:</b> {data.get('contact', '-')}\n"
        f"<b>Comments:</b> {data.get('comments', '-')}"
    )

    if data.get("photo"):
        new_summary_msg = await message.answer_photo(
            photo=data["photo"], caption=summary, parse_mode=ParseMode.HTML
        )
    else:
        new_summary_msg = await message.answer(summary, parse_mode=ParseMode.HTML)

    new_buttons_msg = await message.answer(
        "Is everything correct?", reply_markup=lost_confirm_edit_keyboard(data)
    )

    await state.update_data(
        summary_message=new_summary_msg.message_id,
        buttons_message=new_buttons_msg.message_id,
    )


# ── /lost Entry ─────────────────────────────────────────


@router.message(lambda message: message.text == "/lost")
async def cmd_lost(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "What would you like to do?",
        reply_markup=lost_action_keyboard(),
    )


# ── Action: Search ──────────────────────────────────────


@router.callback_query(lambda c: c.data == "lost_search")
async def handle_lost_search(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]

    prompt_msg = await callback.message.answer("🔍 Which category would you like to search?")  # type: ignore[union-attr]
    await state.update_data(last_bot_message=prompt_msg.message_id)

    search_msg = await callback.message.answer(  # type: ignore[union-attr]
        "📂 Select a category:", reply_markup=category_filter_keyboard()
    )
    await state.update_data(search_prompt_message=search_msg.message_id)
    await state.set_state(FilterForm.category)
    await callback.answer()


# ── Search Step 1: Category Selected ────────────────────


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


# ── Search Step 2: Days ─────────────────────────────────


@router.message(FilterForm.days, lambda message: not (message.text and message.text.startswith("/")))
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


# ══════════════════════════════════════════════════════════
# ── Action: Report Lost Item ─────────────────────────────
# ══════════════════════════════════════════════════════════


@router.callback_query(lambda c: c.data == "lost_report")
async def handle_lost_report(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]

    msg = await callback.message.answer(  # type: ignore[union-attr]
        "📸 Please send a photo of the item you lost, or skip:",
        reply_markup=lost_skip_photo_keyboard(),
    )
    await state.update_data(last_bot_message=msg.message_id)
    await state.set_state(LostItemForm.photo)
    await callback.answer()


# ── Report Step 1: Photo ────────────────────────────────


@router.callback_query(LostItemForm.photo, lambda c: c.data == "lost_skip_photo")
async def lost_skip_photo(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """User chose to skip the photo step."""
    data = await state.get_data()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    await _delete_msg(bot, chat_id, data.get("last_bot_message"))
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]

    msg = await callback.message.answer(  # type: ignore[union-attr]
        "📂 Select a category:", reply_markup=lost_category_select_keyboard()
    )
    await state.update_data(last_bot_message=msg.message_id)
    await state.set_state(LostItemForm.category)
    await callback.answer()


@router.message(LostItemForm.photo, lambda message: not (message.text and message.text.startswith("/")))
async def lost_receive_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.photo:
        await message.answer("Please send a valid photo or tap ⏭ Skip Photo.")
        return

    await state.update_data(photo=message.photo[-1].file_id)
    data = await state.get_data()

    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)

    msg = await message.answer(
        "📂 Select a category:", reply_markup=lost_category_select_keyboard()
    )
    await state.update_data(last_bot_message=msg.message_id)
    await state.set_state(LostItemForm.category)


# ── Report Step 2: Category ─────────────────────────────


@router.callback_query(LostItemForm.category, lambda c: c.data and c.data.startswith("LOST_CATEGORY:"))
async def lost_handle_category(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    raw = callback.data.replace("LOST_CATEGORY:", "").strip()  # type: ignore[union-attr]
    category_name = CATEGORIES.get(raw, "Unknown")

    await state.update_data(category=category_name)
    data = await state.get_data()

    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    await _delete_msg(bot, chat_id, data.get("last_bot_message"))
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]

    await _show_lost_summary(callback.message, data, state, bot)  # type: ignore[union-attr]
    await callback.answer()


# ── Editing ─────────────────────────────────────────────


@router.callback_query(lambda c: c.data is not None and c.data.startswith("lost_edit_"))
async def handle_lost_edit(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    action = callback.data.replace("lost_edit_", "")  # type: ignore[union-attr]
    chat_id = callback.message.chat.id  # type: ignore[union-attr]

    if action == "photo":
        msg = await callback.message.answer(  # type: ignore[union-attr]
            "📸 Please send a new photo, or skip:",
            reply_markup=lost_skip_photo_keyboard(),
        )
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(LostEditingForm.photo)
    elif action == "category":
        msg = await callback.message.answer(  # type: ignore[union-attr]
            "📂 Select a category:", reply_markup=lost_category_select_keyboard()
        )
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(LostEditingForm.category)
    elif action == "location":
        msg = await callback.message.answer(  # type: ignore[union-attr]
            'Where did you lose it? (Type "-" to skip)'
        )
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(LostEditingForm.location)
    elif action == "contact":
        msg = await callback.message.answer(  # type: ignore[union-attr]
            'Enter your contact number: (Type "-" to skip)'
        )
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(LostEditingForm.contact)
    elif action == "comments":
        msg = await callback.message.answer(  # type: ignore[union-attr]
            'Add or edit your comments: (Type "-" to skip)'
        )
        await state.update_data(last_bot_message=msg.message_id)
        await state.set_state(LostEditingForm.comments)

    data = await state.get_data()
    await _delete_msg(bot, chat_id, data.get("summary_message"))
    await _delete_msg(bot, chat_id, data.get("buttons_message"))
    await callback.answer()


@router.callback_query(LostEditingForm.photo, lambda c: c.data == "lost_skip_photo")
async def lost_edit_skip_photo(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """User chose to remove/skip the photo during editing."""
    await state.update_data(photo=None)
    data = await state.get_data()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    await _delete_msg(bot, chat_id, data.get("last_bot_message"))
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]
    await _show_lost_summary(callback.message, data, state, bot)  # type: ignore[union-attr]
    await callback.answer()


@router.message(LostEditingForm.photo, lambda message: not (message.text and message.text.startswith("/")))
async def lost_update_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.photo:
        await message.answer("Please send a valid photo.")
        return
    await state.update_data(photo=message.photo[-1].file_id)
    data = await state.get_data()
    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)
    await _show_lost_summary(message, data, state, bot)


@router.callback_query(LostEditingForm.category, lambda c: c.data and c.data.startswith("LOST_CATEGORY:"))
async def lost_update_category(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    raw = callback.data.replace("LOST_CATEGORY:", "").strip()  # type: ignore[union-attr]
    category_name = CATEGORIES.get(raw, "Unknown")
    await state.update_data(category=category_name)
    data = await state.get_data()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    await _delete_msg(bot, chat_id, data.get("last_bot_message"))
    await _delete_msg(bot, chat_id, callback.message.message_id)  # type: ignore[union-attr]
    await _show_lost_summary(callback.message, data, state, bot)  # type: ignore[union-attr]
    await callback.answer()


@router.message(LostEditingForm.location, lambda message: not (message.text and message.text.startswith("/")))
async def lost_update_location(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.strip() != "-":
        await state.update_data(location=message.text)
    data = await state.get_data()
    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)
    await _show_lost_summary(message, data, state, bot)


@router.message(LostEditingForm.contact, lambda message: not (message.text and message.text.startswith("/")))
async def lost_update_contact(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.strip() != "-":
        await state.update_data(contact=message.text)
    data = await state.get_data()
    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)
    await _show_lost_summary(message, data, state, bot)


@router.message(LostEditingForm.comments, lambda message: not (message.text and message.text.startswith("/")))
async def lost_update_comments(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.strip() != "-":
        await state.update_data(comments=message.text)
    data = await state.get_data()
    await _delete_msg(bot, message.chat.id, data.get("last_bot_message"))
    await _delete_msg(bot, message.chat.id, message.message_id)
    await _show_lost_summary(message, data, state, bot)


# ── Confirm & Submit Lost Item ──────────────────────────


@router.callback_query(lambda c: c.data == "lost_confirm_submit")
async def lost_confirm_submission(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]

    category_key = next(
        (k for k, v in CATEGORIES.items() if v == data.get("category")), "other"
    )

    summary_for_channel = (
        f"🔎 Lost Item\n\n"
        f"Location: {data.get('location', '-')}\n"
        f"Contact: {data.get('contact', '-')}\n"
        f"Comments: {data.get('comments', '-')}\n"
        f"Date: {datetime.now().date()}"
    )

    try:
        if data.get("photo"):
            sent_msg = await bot.send_photo(
                chat_id=settings.channel_username,
                photo=data["photo"],
                caption=summary_for_channel,
            )
        else:
            sent_msg = await bot.send_message(
                chat_id=settings.channel_username,
                text=summary_for_channel,
            )

        # Add "Mark as Claimed" button
        await bot.edit_message_reply_markup(
            chat_id=settings.channel_username,
            message_id=sent_msg.message_id,
            reply_markup=channel_found_keyboard(sent_msg.message_id),
        )

        # Save to DB
        await db.add_lost_item(category_key, sent_msg.message_id)

        # Clean up UI
        success_msg = await callback.message.answer("✅ Lost item report submitted successfully!")  # type: ignore[union-attr]
        await _delete_msg(bot, chat_id, data.get("summary_message"))
        await _delete_msg(bot, chat_id, data.get("buttons_message"))

        asyncio.create_task(
            _delete_after_delay(bot, chat_id, success_msg.message_id, delay=15)
        )

    except Exception as exc:
        await callback.message.answer("⚠️ Failed to submit lost item report")  # type: ignore[union-attr]
        logger.error("Lost item submission error: %s", exc)

    await state.clear()
    await callback.answer()
