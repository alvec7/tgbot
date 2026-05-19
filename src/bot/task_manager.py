from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic

from aiogram import Bot
from aiogram.enums import ChatAction

from src.bot.config import Settings
from src.bot.db import Database
from src.bot.openai_client import OpenAIService


@dataclass(slots=True)
class EnqueuedTask:
    task_id: int
    user_id: int
    chat_id: int
    text: str


class TaskManager:
    def __init__(
        self,
        *,
        settings: Settings,
        db: Database,
        bot: Bot,
        openai_service: OpenAIService,
    ) -> None:
        self.settings = settings
        self.db = db
        self.bot = bot
        self.openai_service = openai_service
        self.queue: asyncio.Queue[EnqueuedTask] = asyncio.Queue()
        self.worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.worker_task = asyncio.create_task(self._worker(), name="task-worker")

    async def stop(self) -> None:
        if self.worker_task is None:
            return
        self.worker_task.cancel()
        try:
            await self.worker_task
        except asyncio.CancelledError:
            pass

    async def enqueue(self, user_id: int, chat_id: int, text: str) -> int:
        task_id = await self.db.create_task(user_id, chat_id, text)
        await self.queue.put(
            EnqueuedTask(task_id=task_id, user_id=user_id, chat_id=chat_id, text=text)
        )
        return task_id

    async def _worker(self) -> None:
        while True:
            item = await self.queue.get()
            try:
                await self._handle_task(item)
            finally:
                self.queue.task_done()

    async def _handle_task(self, item: EnqueuedTask) -> None:
        existing_task = await self.db.get_task(item.task_id)
        if existing_task is None or existing_task.status != "queued":
            return

        await self.db.update_task_status(item.task_id, "running")
        started_at = monotonic()
        typing_task = asyncio.create_task(self._typing_loop(item.chat_id))

        try:
            context = await self.db.get_recent_messages(
                item.user_id, self.settings.max_context_messages
            )
            result_text = await self.openai_service.generate_reply(item.text, context)
            if not result_text:
                result_text = "Не удалось сгенерировать ответ. Попробуй переформулировать задачу."

            await self.db.add_message(item.user_id, "user", item.text)
            await self.db.add_message(item.user_id, "assistant", result_text)
            await self.db.update_task_status(item.task_id, "done", result_text=result_text)

            elapsed = monotonic() - started_at
            header = f"Задача #{item.task_id} выполнена"
            if elapsed >= self.settings.long_task_threshold_seconds:
                header += f" за {elapsed:.1f} c"
            await self.bot.send_message(item.chat_id, f"{header}\n\n{result_text}")
        except Exception as exc:
            error_text = str(exc).strip() or "Unknown error"
            await self.db.update_task_status(item.task_id, "failed", error_text=error_text)
            await self.bot.send_message(
                item.chat_id,
                f"Задача #{item.task_id} завершилась с ошибкой.\n\n{error_text}",
            )
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

    async def _typing_loop(self, chat_id: int) -> None:
        while True:
            await self.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4)
