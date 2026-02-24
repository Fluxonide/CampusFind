"""
Inline calendar date-picker widget.

Provides a /calendar command that renders an interactive monthly calendar
where users can navigate between months and select a specific day.
"""

from __future__ import annotations

import calendar as cal
from datetime import datetime

from aiogram import Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.fsm.context import FSMContext

from states.forms import CalendarForm
from core.logger import get_logger

logger = get_logger(__name__)

router = Router(name="calendar")


# ── Calendar Generator ──────────────────────────────────


def generate_calendar_buttons(
    offset: int = 0,
) -> tuple[InlineKeyboardMarkup, int, int]:
    """Return (keyboard, year, month) for the month at *offset* from today."""
    today = datetime.now()
    year = today.year
    month = today.month + offset

    # normalise month overflow / underflow
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1

    month_calendar = cal.Calendar(firstweekday=0)
    month_days = month_calendar.monthdayscalendar(year, month)

    buttons: list[list[InlineKeyboardButton]] = []

    # Navigation header
    buttons.append(
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"cal_prev:{offset}"),
            InlineKeyboardButton(
                text=f"{cal.month_name[month]} {year}",
                callback_data="ignore",
            ),
            InlineKeyboardButton(text="➡️", callback_data=f"cal_next:{offset}"),
        ]
    )

    # Weekday header (English)
    week_days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    buttons.append(
        [InlineKeyboardButton(text=d, callback_data="ignore") for d in week_days]
    )

    # Day grid
    for week in month_days:
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                row.append(
                    InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"select_day:{year}-{month:02d}-{day:02d}",
                    )
                )
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons), year, month


# ── Handlers ────────────────────────────────────────────


@router.message(lambda message: message.text == "/calendar")
async def cmd_calendar(message: Message, state: FSMContext) -> None:
    keyboard, year, month = generate_calendar_buttons(offset=0)
    title = f"🗓 Pick a day in {cal.month_name[month]} {year}"
    msg = await message.answer(title, reply_markup=keyboard)
    await state.update_data(calendar_message=msg.message_id)
    await state.set_state(CalendarForm.viewing)


@router.callback_query(
    CalendarForm.viewing,
    lambda c: c.data is not None and c.data.startswith(("cal_prev", "cal_next")),
)
async def navigate_month(callback: CallbackQuery, state: FSMContext) -> None:
    offset = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    if "cal_prev" in callback.data:  # type: ignore[operator]
        offset -= 1
    else:
        offset += 1

    keyboard, year, month = generate_calendar_buttons(offset)
    title = f"🗓 Pick a day in {cal.month_name[month]} {year}"
    try:
        await callback.message.edit_text(title, reply_markup=keyboard)  # type: ignore[union-attr]
    except Exception as exc:
        logger.error("Failed to edit calendar: %s", exc)
    await callback.answer()


@router.callback_query(
    CalendarForm.viewing,
    lambda c: c.data is not None and c.data.startswith("select_day:"),
)
async def select_day_callback(callback: CallbackQuery, state: FSMContext) -> None:
    date_str = callback.data.replace("select_day:", "")  # type: ignore[union-attr]
    year, month, day = map(int, date_str.split("-"))
    month_title = cal.month_name[month]
    await callback.message.answer(f"📅 You selected: {day} {month_title}, {year}")  # type: ignore[union-attr]
    await callback.answer()
    await state.clear()
