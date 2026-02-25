"""
Reusable inline keyboard builders.

Every function returns an InlineKeyboardMarkup ready to attach to a message.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# ── Categories ──────────────────────────────────────────

CATEGORIES: dict[str, str] = {
    "pants": "👖 Pants",
    "jackets": "🧥 Jackets",
    "sweaters": "🧣 Sweaters",
    "shoes": "👟 Shoes",
    "bags": "🎒 Bags",
    "hats": "🎩 Hats & Caps",
    "badges": "🎖️ Badges & IDs",
    "chargers_electronics": "🔌 Chargers",
    "electronics_devices": "💻 Electronics",
    "accessories": "🕶️ Accessories",
    "sports_gear": "🎾 Sports Gear",
    "money_cards": "💰 Money & Cards",
    "other": "📦 Other",
}

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "pants": "jeans / sweatpants / shorts",
    "jackets": "",
    "sweaters": "hoodies / zip-ups / t-shirts",
    "shoes": "athletic / casual",
    "bags": "",
    "hats": "beanies / caps",
    "badges": "",
    "chargers_electronics": "",
    "electronics_devices": "laptops / phones / earbuds",
    "accessories": "glasses, rings, jewellery, etc.",
    "sports_gear": "balls, rackets, dumbbells, etc.",
    "money_cards": "",
    "other": "",
}


# ── Help ────────────────────────────────────────────────


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 /lost", callback_data="help_lost"),
                InlineKeyboardButton(text="📦 /found", callback_data="help_found"),
                InlineKeyboardButton(text="🔔 /notification", callback_data="help_notifications"),
            ],
            [InlineKeyboardButton(text="📚 All Commands", callback_data="all_commands")],
        ]
    )


# ── Skip Photo ──────────────────────────────────────────


def found_skip_photo_keyboard() -> InlineKeyboardMarkup:
    """Skip button shown during /found photo step."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Skip Photo", callback_data="found_skip_photo")]
        ]
    )


def lost_skip_photo_keyboard() -> InlineKeyboardMarkup:
    """Skip button shown during /lost report photo step."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Skip Photo", callback_data="lost_skip_photo")]
        ]
    )


# ── Category Search ─────────────────────────────────────


def category_select_keyboard() -> InlineKeyboardMarkup:
    """Grid of category buttons for /found — sends SELECTED_CATEGORY:<key> as callback."""
    buttons: list[list[InlineKeyboardButton]] = []
    items = list(CATEGORIES.items())
    for i in range(0, len(items), 2):
        row = items[i : i + 2]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"SELECTED_CATEGORY:{key}",
                )
                for key, title in row
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def lost_action_keyboard() -> InlineKeyboardMarkup:
    """Two options when user types /lost: search or report."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Search Found Items", callback_data="lost_search")],
            [InlineKeyboardButton(text="📝 Report Lost Item", callback_data="lost_report")],
        ]
    )


def category_filter_keyboard() -> InlineKeyboardMarkup:
    """Grid of category buttons for /lost search — sends FILTER_CATEGORY:<key> as callback."""
    buttons: list[list[InlineKeyboardButton]] = []
    items = list(CATEGORIES.items())
    for i in range(0, len(items), 2):
        row = items[i : i + 2]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"FILTER_CATEGORY:{key}",
                )
                for key, title in row
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def lost_category_select_keyboard() -> InlineKeyboardMarkup:
    """Grid of category buttons for lost item report — sends LOST_CATEGORY:<key> as callback."""
    buttons: list[list[InlineKeyboardButton]] = []
    items = list(CATEGORIES.items())
    for i in range(0, len(items), 2):
        row = items[i : i + 2]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"LOST_CATEGORY:{key}",
                )
                for key, title in row
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def lost_confirm_edit_keyboard(data: dict) -> InlineKeyboardMarkup:
    """Summary / edit / confirm buttons for the lost item report form."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm & Submit", callback_data="lost_confirm_submit")],
            [
                InlineKeyboardButton(
                    text="📷 Edit Photo" if data.get("photo") else "📸 Add Photo",
                    callback_data="lost_edit_photo",
                ),
                InlineKeyboardButton(
                    text="🏷️ Edit Category" if data.get("category") else "🔍 Add Category",
                    callback_data="lost_edit_category",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Edit Location" if data.get("location") else "📍 Add Location",
                    callback_data="lost_edit_location",
                ),
                InlineKeyboardButton(
                    text="📞 Edit Contact" if data.get("contact") else "📞 Add Contact",
                    callback_data="lost_edit_contact",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Edit Comment" if data.get("comments") else "📝 Add Comment",
                    callback_data="lost_edit_comments",
                ),
            ],
        ]
    )


def notify_subscribe_keyboard() -> InlineKeyboardMarkup:
    """Grid of category buttons for notifications — sends SELECTED_SUB:<key> as callback."""
    buttons: list[list[InlineKeyboardButton]] = []
    items = list(CATEGORIES.items())
    for i in range(0, len(items), 2):
        row = items[i : i + 2]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"SELECTED_SUB:{key}",
                )
                for key, title in row
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Notification ────────────────────────────────────────


def notification_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Subscribe", callback_data="notify_subscribe")],
            [InlineKeyboardButton(text="🔕 Unsubscribe", callback_data="notify_unsubscribe")],
        ]
    )


def unsubscribe_keyboard(subscriptions: list[str]) -> InlineKeyboardMarkup:
    """Build a grid of ❌ buttons for current subscriptions plus a Finish button."""
    buttons: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(subscriptions), 2):
        row = subscriptions[i : i + 2]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"❌ {CATEGORIES.get(cat, cat)}",
                    callback_data=f"unsub_{cat}",
                )
                for cat in row
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text="✅ Finish", callback_data="unsub_finish")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Found-Item Form ─────────────────────────────────────


def confirm_edit_keyboard(data: dict) -> InlineKeyboardMarkup:
    """Summary / edit / confirm buttons for the /found form."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm & Submit", callback_data="confirm_submit")],
            [
                InlineKeyboardButton(
                    text="📷 Edit Photo" if data.get("photo") else "📸 Add Photo",
                    callback_data="edit_photo",
                ),
                InlineKeyboardButton(
                    text="🏷️ Edit Category" if data.get("category") else "🔍 Add Category",
                    callback_data="edit_category",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Edit Location" if data.get("location") else "📍 Add Location",
                    callback_data="edit_location",
                ),
                InlineKeyboardButton(
                    text="📞 Edit Contact" if data.get("contact") else "📞 Add Contact",
                    callback_data="edit_contact",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Edit Comment" if data.get("comments") else "📝 Add Comment",
                    callback_data="edit_comments",
                ),
            ],
        ]
    )


# ── Admin ───────────────────────────────────────────────


def admin_delete_keyboard(message_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑️ Delete from DB",
                    callback_data=f"admin_delete_{message_id}",
                ),
                InlineKeyboardButton(
                    text="✅ Item Found",
                    callback_data=f"admin_found_{message_id}",
                ),
            ]
        ]
    )


def admin_cleanup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Hide All", callback_data="admin_cleanup")]
        ]
    )


def channel_found_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """Button shown on channel posts — only admins can use it."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Mark as Claimed",
                    callback_data=f"ch_found_{message_id}",
                )
            ]
        ]
    )


def channel_undo_keyboard(message_id: int, category: str) -> InlineKeyboardMarkup:
    """Undo button shown after an item is marked as claimed."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ Undo",
                    callback_data=f"ch_undo_{message_id}_{category}",
                )
            ]
        ]
    )


def hide_orders_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Hide Orders", callback_data="hide_orders")]
        ]
    )


def notification_delete_keyboard(message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑️ Delete",
                    callback_data=f"notif_delete_{message_id}",
                )
            ]
        ]
    )
