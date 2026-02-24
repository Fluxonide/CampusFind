"""
Common handlers: /start and /help.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from database import services as db
from keyboards.inline import help_keyboard
from core.logger import get_logger

logger = get_logger(__name__)

router = Router(name="common")


# ── /start ──────────────────────────────────────────────


@router.message(lambda message: message.text == "/start")
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()  # Reset any stuck FSM flow
    await db.register_user(message.from_user.id)

    welcome = (
        "👋 Hello! Welcome to the Lost & Found bot.\n\n"
        "🔍 Lost something? Use /lost\n"
        "📦 Found someone's item? Use /found\n\n"
        "❗️ Please keep posts relevant — off-topic content "
        "may be removed by moderators.\n\n"
        "Learn more about the bot with /help"
    )

    try:
        await message.answer(welcome, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.error("Failed to send welcome: %s", exc)
        await message.answer(welcome)


# ── /help ───────────────────────────────────────────────


@router.message(lambda message: message.text == "/help")
async def help_command(message: Message) -> None:
    help_text = (
        "🔍 <b>How to use this bot</b>\n\n"
        "<b>1. /lost — Search for lost items</b>\n"
        "• Pick a category (pants, jackets, shoes, etc.)\n"
        "• Choose a time window (how many days back)\n"
        "• The bot shows all matching posts from the database\n"
        "• Each post includes: photo, description, and date\n\n"
        "<b>2. /found — Report a found item</b>\n"
        "• Send a photo of the item\n"
        "• Pick a category (e.g. bags, electronics, accessories)\n"
        "• Optionally add a location and comment\n"
        "• The post will appear in the shared channel\n"
        "• Subscribers will receive a notification\n\n"
        "<b>3. /notification — Manage notifications</b>\n"
        "• Subscribe to categories you care about\n"
        "• Get notified when a new item is found in those categories\n"
        "• Each notification has a 🗑️ delete button\n"
        "• Change your subscriptions any time\n\n"
        "<b>🎯 Tips</b>\n"
        "• Always attach a clear photo when creating a post\n"
        "• The more accurate your category and description, "
        "the higher the chances of finding the owner\n"
        "• Only subscribe to categories you need to avoid spam\n"
        "• Admins can broadcast messages to all users\n\n"
        "<b>❓ Getting started</b>\n"
        "• Use the menu commands\n"
        "• Or tap one of the buttons below"
    )

    try:
        await message.answer(
            help_text, reply_markup=help_keyboard(), parse_mode=ParseMode.HTML
        )
    except Exception:
        await message.answer(
            help_text.replace("<b>", "").replace("</b>", ""),
            reply_markup=help_keyboard(),
        )


# ── Help Section Callbacks ──────────────────────────────


@router.callback_query(
    lambda c: c.data in ("help_lost", "help_found", "help_notifications", "all_commands")
)
async def handle_help_sections(callback: CallbackQuery) -> None:
    section = callback.data.split("_")[1]  # type: ignore[union-attr]
    content = "❌ Unknown help section"

    if section == "lost":
        content = (
            "🔍 <b>How to use /lost</b>\n\n"
            "1. Type /lost\n"
            "2. Pick a category\n"
            "3. Enter a time window (e.g. 7 days)\n"
            "4. The bot shows all matching posts\n"
            "5. Tap 🗑️ to hide them\n\n"
            "💡 Tip: Use a shorter time window to see the freshest posts"
        )
    elif section == "found":
        content = (
            "📦 <b>How to use /found</b>\n\n"
            "1. Type /found\n"
            "2. Send a photo of the found item\n"
            "3. Pick a category\n"
            "4. Add a location and comment (optional)\n"
            "5. Confirm your submission\n\n"
            "✅ After confirmation the post goes to the shared channel\n"
            "🔔 Subscribers to that category will be notified"
        )
    elif section == "notifications":
        content = (
            "🔔 <b>Found-item notifications</b>\n\n"
            "1. Type /notification\n"
            "2. Tap '🔔 Subscribe'\n"
            "3. Search for a category\n"
            "4. To unsubscribe — tap '🔕 Unsubscribe' and pick categories\n"
            "5. Notifications arrive within 30 seconds of a new post\n\n"
            "🗑️ Each notification can be deleted with a button"
        )
    elif section == "commands":
        content = (
            "📚 <b>All commands</b>\n\n"
            "🔹 /start — Start the bot\n"
            "🔹 /help — Help & feature guide\n"
            "🔹 /lost — Search for a lost item\n"
            "🔹 /found — Report a found item\n"
            "🔹 /notification — Manage notifications\n\n"
            "🔐 <b>Admin commands:</b>\n"
            "🔹 /showall — View all posts\n"
            "🔹 /sendall — Broadcast to all users"
        )

    try:
        await callback.message.edit_text(content, parse_mode=ParseMode.HTML)  # type: ignore[union-attr]
        await callback.answer()
    except Exception as exc:
        logger.error("Error updating help text: %s", exc)
        await callback.answer("Failed to display help section")
