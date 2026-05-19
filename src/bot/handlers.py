from __future__ import annotations

from aiogram import Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from src.bot.config import Settings
from src.bot.db import Database
from src.bot.task_manager import TaskManager


def _is_allowed(settings: Settings, user_id: int) -> bool:
    return not settings.allowed_user_ids or user_id in settings.allowed_user_ids


def register_handlers(
    dp: Dispatcher,
    *,
    settings: Settings,
    db: Database,
    task_manager: TaskManager,
) -> None:
    @dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        if message.from_user is None:
            return
        if not _is_allowed(settings, message.from_user.id):
            await message.answer("У тебя нет доступа к этому боту.")
            return

        await db.upsert_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        await message.answer(
            "Я готов принимать задачи через Telegram.\n\n"
            "Команды:\n"
            "/help - показать помощь\n"
            "/new - очистить контекст диалога\n"
            "/tasks - показать последние задачи\n"
            "/status <id> - показать статус задачи\n"
            "/cancel - подсказать, как отменять задачи\n\n"
            "Просто пришли задачу обычным сообщением."
        )

    @dp.message(Command("help"))
    async def handle_help(message: Message) -> None:
        await message.answer(
            "Как использовать бота:\n\n"
            "1. Пишешь задачу в чат.\n"
            "2. Бот ставит ее в очередь.\n"
            "3. Когда ответ готов, бот присылает результат отдельным сообщением.\n\n"
            "Лучше всего подходят:\n"
            "- анализ текста\n"
            "- генерация контента\n"
            "- черновики писем, постов, планов\n"
            "- краткие исследования\n\n"
            "Для приватного режима задай ALLOWED_USER_IDS в .env."
        )

    @dp.message(Command("new"))
    async def handle_new(message: Message) -> None:
        if message.from_user is None:
            return
        await db.clear_messages(message.from_user.id)
        await message.answer("Контекст диалога очищен.")

    @dp.message(Command("tasks"))
    async def handle_tasks(message: Message) -> None:
        if message.from_user is None:
            return
        tasks = await db.list_recent_tasks(message.from_user.id)
        if not tasks:
            await message.answer("Пока нет задач.")
            return

        lines = ["Последние задачи:"]
        for task in tasks:
            preview = task.request_text.replace("\n", " ").strip()
            if len(preview) > 60:
                preview = preview[:57] + "..."
            lines.append(f"#{task.id} [{task.status}] {preview}")
        await message.answer("\n".join(lines))

    @dp.message(Command("status"))
    async def handle_status(message: Message, command: CommandObject) -> None:
        if not command.args or not command.args.strip().isdigit():
            await message.answer("Использование: /status <id>")
            return

        task_id = int(command.args.strip())
        task = await db.get_task(task_id)
        if task is None:
            await message.answer("Задача не найдена.")
            return
        if message.from_user is None or task.user_id != message.from_user.id:
            await message.answer("Эта задача тебе недоступна.")
            return

        text = [
            f"Задача #{task.id}",
            f"Статус: {task.status}",
            f"Создана: {task.created_at}",
            f"Обновлена: {task.updated_at}",
            "",
            f"Запрос: {task.request_text}",
        ]
        if task.result_text:
            text.extend(["", "Результат:", task.result_text[:1500]])
        if task.error_text:
            text.extend(["", "Ошибка:", task.error_text[:1500]])
        await message.answer("\n".join(text))

    @dp.message(Command("cancel"))
    async def handle_cancel(message: Message, command: CommandObject) -> None:
        if message.from_user is None:
            return

        args = (command.args or "").strip().lower()
        if not args:
            await message.answer(
                "Использование:\n"
                "/cancel <id> - отменить задачу из очереди\n"
                "/cancel all - отменить все задачи в очереди\n\n"
                "Уже запущенную задачу безопасно прервать на стороне OpenAI нельзя."
            )
            return

        if args == "all":
            cancelled = await db.cancel_all_queued_tasks(message.from_user.id)
            await message.answer(f"Отменено задач из очереди: {cancelled}.")
            return

        if not args.isdigit():
            await message.answer("Использование: /cancel <id> или /cancel all")
            return

        cancelled = await db.cancel_task(int(args), message.from_user.id)
        if cancelled:
            await message.answer("Задача отменена, если она еще не начала выполняться.")
        else:
            await message.answer(
                "Не удалось отменить задачу. Возможно, она уже выполняется, завершена или не существует."
            )

    @dp.message(F.text)
    async def handle_text(message: Message) -> None:
        if message.from_user is None or message.text is None:
            return
        if not _is_allowed(settings, message.from_user.id):
            await message.answer("У тебя нет доступа к этому боту.")
            return

        await db.upsert_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )

        active_tasks = await db.count_active_tasks(message.from_user.id)
        if active_tasks >= settings.max_concurrent_user_tasks:
            await message.answer(
                "У тебя уже есть активная задача. Дождись результата или увеличь "
                "MAX_CONCURRENT_USER_TASKS в конфиге."
            )
            return

        task_id = await task_manager.enqueue(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            text=message.text.strip(),
        )
        await message.answer(
            f"Принял задачу #{task_id}. "
            "Когда закончу обработку, пришлю результат отдельным сообщением."
        )
