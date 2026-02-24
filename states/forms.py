"""
All FSM StatesGroup definitions used across the bot.
"""

from aiogram.fsm.state import State, StatesGroup


class FoundItemForm(StatesGroup):
    """Multi-step form for reporting a found item (/found)."""
    photo = State()
    category = State()
    location = State()
    comments = State()


class EditingForm(StatesGroup):
    """Editing individual fields of a found-item form."""
    photo = State()
    category = State()
    location = State()
    comments = State()


class FilterForm(StatesGroup):
    """Search / filter flow for /lost."""
    category = State()
    days = State()


class SearchState(StatesGroup):
    """Active viewing state after search results are shown."""
    viewing = State()


class NotificationForm(StatesGroup):
    """Subscribe / unsubscribe flow for /notification."""
    action = State()
    subscribe = State()
    unsubscribe = State()


class AdminForm(StatesGroup):
    """Admin broadcast message flow (/sendall)."""
    broadcast = State()


class CalendarForm(StatesGroup):
    """Calendar date-picker state (/calendar)."""
    viewing = State()
