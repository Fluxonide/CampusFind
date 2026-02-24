"""
Admin handlers: /showall, /sendall, deletion, and cleanup.

All handlers are guarded by the IsAdmin filter.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot, Router
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from core.config import settings
from core.logger import get_logger
from database import services as db
from keyboards.inline import (
    CATEGORIES,
    admin_cleanup_keyboard,
    admin_delete_keyboard,
    channel_found_keyboard,
    channel_undo_keyboard,
)
from states.forms import AdminForm
from utils.filters import IsAdmin

logger = get_logger(__name__)

router = Router(name="admin")

ADMIN_EMOJI = "👮‍♂️"


# ── Helpers ─────────────────────────────────────────────


async def _delete_msg(bot: Bot, chat_id: int, msg_id: int | None) -> None:
    if msg_id is None:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass


async def _delete_after_delay(bot: Bot, chat_id: int, message_id: int, delay: int = 5) -> None:
    await asyncio.sleep(delay)
    await _delete_msg(bot, chat_id, message_id)


# ── /showall ────────────────────────────────────────────


@router.message(IsAdmin(), lambda message: message.text == "/showall")
async def cmd_showall(message: Message, state: FSMContext, bot: Bot) -> None:
    items = await db.get_all_items()

    if not items:
        await message.answer("No items found in database.")
        return

    sent_messages: list[int] = []
    for item in items:
        msg_id = item["message_id"]
        category = item["category"]
        date = item["date"]

        try:
            temp_msg = await bot.forward_message(
                chat_id=message.chat.id,
                from_chat_id=settings.channel_username,
                message_id=int(msg_id),
            )

            # Extract location / comments from caption
            caption = temp_msg.caption or ""
            location = "-"
            comments = "-"
            for line in caption.split("\n"):
                if line.startswith("Location:"):
                    location = line.replace("Location:", "").strip()
                elif line.startswith("Comments:"):
                    comments = line.replace("Comments:", "").strip()

            sent_msg = await message.answer_photo(
                photo=temp_msg.photo[-1].file_id if temp_msg.photo else None,
                caption=(
                    f"Category: {CATEGORIES.get(category, category)}\n"
                    f"Location: {location}\n"
                    f"Comments: {comments}\n"
                    f"Date: {date}"
                ),
                reply_markup=admin_delete_keyboard(msg_id),
            )
            sent_messages.append(sent_msg.message_id)

            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id,
            )

        except Exception as exc:
            logger.error("Error showing message %s: %s", msg_id, exc)

    end_list = await message.answer("End of list", reply_markup=admin_cleanup_keyboard())
    await state.update_data(
        sent_messages=sent_messages,
        end_list_message=end_list.message_id,
    )


# ── Admin Delete ────────────────────────────────────────


@router.callback_query(IsAdmin(), lambda c: c.data is not None and c.data.startswith("admin_delete_"))
async def handle_admin_delete(callback: CallbackQuery, bot: Bot) -> None:
    msg_id = callback.data.split("_")[2]  # type: ignore[union-attr]

    try:
        await db.delete_item(msg_id)

        await _delete_msg(
            bot,
            callback.message.chat.id,  # type: ignore[union-attr]
            callback.message.message_id,  # type: ignore[union-attr]
        )

        success_msg = await callback.message.answer(  # type: ignore[union-attr]
            f"🗑️ Message {msg_id} deleted from database"
        )
        asyncio.create_task(
            _delete_after_delay(bot, success_msg.chat.id, success_msg.message_id)
        )
    except Exception as exc:
        await callback.answer(f"❌ Error: {exc}")
        logger.error("Admin deletion error: %s", exc)


# ── Admin Mark as Found ─────────────────────────────────


@router.callback_query(IsAdmin(), lambda c: c.data is not None and c.data.startswith("admin_found_"))
async def handle_admin_found(callback: CallbackQuery, bot: Bot) -> None:
    msg_id = callback.data.split("_")[2]  # type: ignore[union-attr]

    try:
        # Fetch the channel message to get current caption
        try:
            chat_msg = await bot.forward_message(
                chat_id=callback.message.chat.id,  # type: ignore[union-attr]
                from_chat_id=settings.channel_username,
                message_id=int(msg_id),
            )
            old_caption = chat_msg.caption or ""
            # Delete the forwarded copy
            await _delete_msg(bot, callback.message.chat.id, chat_msg.message_id)  # type: ignore[union-attr]
        except Exception:
            old_caption = ""

        # Edit the channel message caption with a "CLAIMED" banner
        new_caption = f"✅ ITEM HAS BEEN CLAIMED ✅\n\n{old_caption}"
        try:
            await bot.edit_message_caption(
                chat_id=settings.channel_username,
                message_id=int(msg_id),
                caption=new_caption,
            )
        except TelegramBadRequest as exc:
            logger.warning("Could not edit channel message %s: %s", msg_id, exc)

        # Remove from database
        await db.delete_item(msg_id)

        # Remove the admin card from chat
        await _delete_msg(
            bot,
            callback.message.chat.id,  # type: ignore[union-attr]
            callback.message.message_id,  # type: ignore[union-attr]
        )

        success_msg = await callback.message.answer(  # type: ignore[union-attr]
            f"✅ Message {msg_id} marked as found & updated in channel"
        )
        asyncio.create_task(
            _delete_after_delay(bot, success_msg.chat.id, success_msg.message_id)
        )
    except Exception as exc:
        await callback.answer(f"❌ Error: {exc}")
        logger.error("Admin mark-found error: %s", exc)


# ── Channel "Mark as Claimed" Button ─────────────────────


@router.callback_query(lambda c: c.data is not None and c.data.startswith("ch_found_"))
async def handle_channel_found(callback: CallbackQuery, bot: Bot) -> None:
    # Only admins can use this button
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer("⛔ Only admins can mark items as claimed.", show_alert=True)
        return

    msg_id = callback.data.split("_")[2]  # type: ignore[union-attr]

    try:
        # Get category before deleting (for undo)
        category = await db.get_item_category(msg_id) or "other"

        # Get the current caption
        old_caption = ""
        if callback.message and hasattr(callback.message, "caption"):
            old_caption = callback.message.caption or ""  # type: ignore[union-attr]

        # Edit caption with "CLAIMED" banner and show undo button
        new_caption = f"✅ ITEM HAS BEEN CLAIMED ✅\n\n{old_caption}"
        await bot.edit_message_caption(
            chat_id=callback.message.chat.id,  # type: ignore[union-attr]
            message_id=int(msg_id),
            caption=new_caption,
            reply_markup=channel_undo_keyboard(int(msg_id), category),
        )

        # Remove from database
        await db.delete_item(msg_id)

        await callback.answer("✅ Marked as claimed!")
    except Exception as exc:
        await callback.answer(f"❌ Error: {exc}", show_alert=True)
        logger.error("Channel mark-claimed error: %s", exc)


# ── Channel Undo Button ─────────────────────────────────


@router.callback_query(lambda c: c.data is not None and c.data.startswith("ch_undo_"))
async def handle_channel_undo(callback: CallbackQuery, bot: Bot) -> None:
    # Only admins can undo
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer("⛔ Only admins can undo.", show_alert=True)
        return

    parts = callback.data.split("_")  # type: ignore[union-attr]
    # ch_undo_<msg_id>_<category>
    msg_id = parts[2]
    category = parts[3] if len(parts) > 3 else "other"

    try:
        # Get current caption and strip the CLAIMED banner
        old_caption = ""
        if callback.message and hasattr(callback.message, "caption"):
            old_caption = callback.message.caption or ""  # type: ignore[union-attr]

        # Remove the "CLAIMED" banner
        restored_caption = old_caption.replace("✅ ITEM HAS BEEN CLAIMED ✅\n\n", "")

        # Restore original caption with "Mark as Claimed" button
        await bot.edit_message_caption(
            chat_id=callback.message.chat.id,  # type: ignore[union-attr]
            message_id=int(msg_id),
            caption=restored_caption,
            reply_markup=channel_found_keyboard(int(msg_id)),
        )

        # Re-add to database
        await db.add_found_item(category, int(msg_id))

        await callback.answer("↩️ Undo successful — item restored!")
    except Exception as exc:
        await callback.answer(f"❌ Error: {exc}", show_alert=True)
        logger.error("Channel undo error: %s", exc)


# ── Admin Cleanup ───────────────────────────────────────


@router.callback_query(IsAdmin(), lambda c: c.data == "admin_cleanup")
async def handle_admin_cleanup(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    chat_id = callback.message.chat.id  # type: ignore[union-attr]

    for msg_id in data.get("sent_messages", []):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except TelegramBadRequest as exc:
            if "message to delete not found" not in str(exc):
                logger.warning("Failed to delete message %s: %s", msg_id, exc)

    await _delete_msg(bot, chat_id, data.get("end_list_message"))
    await callback.answer("Cleanup completed")


# ── /sendall ────────────────────────────────────────────


@router.message(IsAdmin(), lambda message: message.text == "/sendall")
async def cmd_sendall(message: Message, state: FSMContext) -> None:
    await message.answer("Send the message you want to broadcast to all users:")
    await state.set_state(AdminForm.broadcast)


@router.message(AdminForm.broadcast, lambda message: not (message.text and message.text.startswith("/")))
async def process_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    users = await db.get_all_user_ids()
    success = 0
    failed = 0

    admin_badge = f"{ADMIN_EMOJI} *Broadcast from administrator:*\n\n"

    if message.text:
        full_text = admin_badge + message.text
        for user_id in users:
            try:
                await bot.send_message(
                    chat_id=user_id, text=full_text, parse_mode=ParseMode.MARKDOWN
                )
                success += 1
            except Exception:
                failed += 1

    elif message.photo:
        photo_file_id = message.photo[-1].file_id
        caption = message.caption or ""
        full_caption = admin_badge + caption
        for user_id in users:
            try:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=photo_file_id,
                    caption=full_caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
                success += 1
            except Exception:
                failed += 1

    else:
        await message.answer("Unsupported message type for broadcast.")
        await state.clear()
        return

    stats = (
        f"{ADMIN_EMOJI} Broadcast completed:\n"
        f"✅ Delivered: {success}\n"
        f"❌ Failed: {failed}"
    )
    await message.answer(stats)
    await state.clear()
