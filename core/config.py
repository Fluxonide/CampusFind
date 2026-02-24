"""
Centralised configuration loaded from .env via pydantic-settings.

Required variables:
    BOT_TOKEN       – Telegram Bot API token
    ADMIN_IDS       – Comma-separated list of admin Telegram user IDs
    CHANNEL_USERNAME – Public channel username (with @) for posting found items

Optional:
    DB_PATH   – SQLite database file path  (default: bot.db)
    LOG_LEVEL – Logging verbosity           (default: INFO)
"""

from __future__ import annotations

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: SecretStr
    admin_ids: str | list[int] = []
    channel_username: str = "@help_channel_name"
    db_path: str = "bot.db"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Accept comma-separated ADMIN_IDS like "123,456"
    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: str | list[int] | list[str]) -> list[int]:
        if isinstance(value, str):
            return [int(v.strip()) for v in value.split(",") if v.strip()]
        if isinstance(value, list):
            return [int(v) for v in value]
        return value


settings = Settings()
