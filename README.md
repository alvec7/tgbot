# Telegram OpenAI Bot

Расширенный Telegram-бот для постановки задач через чат и получения результата отдельным сообщением.

## Что умеет

- принимает задачи обычными сообщениями
- ставит их в очередь
- хранит историю диалога в `SQLite`
- ограничивает количество одновременных задач на пользователя
- поддерживает `polling` и `webhook`
- умеет работать как приватный бот по списку `ALLOWED_USER_IDS`
- показывает статусы и историю задач командами `/status` и `/tasks`

## Стек

- `Python 3.12`
- `aiogram`
- официальный `openai` SDK
- `SQLite`
- `aiohttp`

## Быстрый старт локально

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.bot.main
```

Перед запуском заполни `.env`:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`

Для локального старта проще всего оставить:

```env
BOT_MODE=polling
```

## Команды

- `/start` - регистрация и приветствие
- `/help` - краткая справка
- `/new` - очистить контекст диалога
- `/tasks` - последние задачи
- `/status 12` - статус конкретной задачи
- `/cancel 12` - отменить задачу, если она еще в очереди
- `/cancel all` - отменить все queued-задачи

## Структура

```text
src/bot/config.py         настройки из env
src/bot/db.py             SQLite и модели задач
src/bot/openai_client.py  вызов OpenAI Responses API
src/bot/task_manager.py   очередь и фоновые задачи
src/bot/handlers.py       Telegram-команды и сообщения
src/bot/main.py           запуск в polling/webhook
```
