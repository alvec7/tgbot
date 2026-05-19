from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update
from aiohttp import web
from dotenv import load_dotenv

from src.bot.config import Settings
from src.bot.db import Database
from src.bot.handlers import register_handlers
from src.bot.openai_client import OpenAIService
from src.bot.task_manager import TaskManager


async def run_polling(bot: Bot, dp: Dispatcher, task_manager: TaskManager) -> None:
    await task_manager.start()
    try:
        await dp.start_polling(bot)
    finally:
        await task_manager.stop()


async def run_webhook(
    bot: Bot,
    dp: Dispatcher,
    task_manager: TaskManager,
    settings: Settings,
) -> None:
    await task_manager.start()

    webhook_path = "/telegram/webhook"
    webhook_url = f"{settings.bot_public_url}{webhook_path}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.bot_webhook_secret,
        drop_pending_updates=True,
    )

    async def handle(request: web.Request) -> web.Response:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != settings.bot_webhook_secret:
            return web.Response(status=403, text="forbidden")
        update = Update.model_validate(await request.json())
        await dp.feed_webhook_update(bot, update)
        return web.Response(text="ok")

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_post(webhook_path, handle)
    app.router.add_get("/healthz", health)
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()

    try:
        await asyncio.Event().wait()
    finally:
        await bot.delete_webhook()
        await task_manager.stop()
        await runner.cleanup()


async def async_main() -> None:
    logging.basicConfig(level=logging.INFO)
    load_dotenv()

    settings = Settings.from_env()
    db = Database(settings.database_path)
    await db.connect()

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()
    openai_service = OpenAIService(settings)
    task_manager = TaskManager(
        settings=settings,
        db=db,
        bot=bot,
        openai_service=openai_service,
    )

    register_handlers(dp, settings=settings, db=db, task_manager=task_manager)

    if settings.bot_mode == "webhook":
        await run_webhook(bot, dp, task_manager, settings)
    else:
        await run_polling(bot, dp, task_manager)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
