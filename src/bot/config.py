from __future__ import annotations

import os
from dataclasses import dataclass


def _split_csv(raw_value: str) -> list[str]:
    if not raw_value.strip():
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    openai_api_key: str
    telegram_bot_token: str
    bot_mode: str = "polling"
    bot_public_url: str = ""
    bot_webhook_secret: str = ""
    openai_model: str = "gpt-5-mini"
    openai_fallback_model: str = "gpt-5"
    system_prompt: str = (
        "You are a helpful Telegram assistant. Be concise, accurate, and action-oriented."
    )
    allowed_user_ids: tuple[int, ...] = ()
    database_path: str = "data/bot.sqlite3"
    max_context_messages: int = 16
    max_concurrent_user_tasks: int = 1
    long_task_threshold_seconds: int = 8

    @classmethod
    def from_env(cls) -> "Settings":
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        if not telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

        allowed_user_ids = tuple(
            int(value) for value in _split_csv(os.getenv("ALLOWED_USER_IDS", ""))
        )

        settings = cls(
            openai_api_key=openai_api_key,
            telegram_bot_token=telegram_bot_token,
            bot_mode=os.getenv("BOT_MODE", "polling").strip().lower(),
            bot_public_url=os.getenv("BOT_PUBLIC_URL", "").strip().rstrip("/"),
            bot_webhook_secret=os.getenv("BOT_WEBHOOK_SECRET", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip(),
            openai_fallback_model=os.getenv("OPENAI_FALLBACK_MODEL", "gpt-5").strip(),
            system_prompt=os.getenv(
                "SYSTEM_PROMPT",
                "You are a helpful Telegram assistant. Be concise, accurate, and action-oriented.",
            ).strip(),
            allowed_user_ids=allowed_user_ids,
            database_path=os.getenv("DATABASE_PATH", "data/bot.sqlite3").strip(),
            max_context_messages=int(os.getenv("MAX_CONTEXT_MESSAGES", "16")),
            max_concurrent_user_tasks=int(os.getenv("MAX_CONCURRENT_USER_TASKS", "1")),
            long_task_threshold_seconds=int(
                os.getenv("LONG_TASK_THRESHOLD_SECONDS", "8")
            ),
        )

        if settings.bot_mode not in {"polling", "webhook"}:
            raise RuntimeError("BOT_MODE must be either 'polling' or 'webhook'")

        if settings.bot_mode == "webhook":
            if not settings.bot_public_url:
                raise RuntimeError("BOT_PUBLIC_URL is required in webhook mode")
            if not settings.bot_webhook_secret:
                raise RuntimeError("BOT_WEBHOOK_SECRET is required in webhook mode")

        return settings
