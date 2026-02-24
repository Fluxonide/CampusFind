"""
Centralised logging configuration.

Usage:
    from core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Bot started")
"""

from __future__ import annotations

import logging
import sys

from core.config import settings

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_once() -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given *name*, configuring the root logger on first call."""
    _configure_once()
    return logging.getLogger(name)
