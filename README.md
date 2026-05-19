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

## Рекомендации по деплою

### 1. Render

Подходит лучше всего для первого деплоя.

Шаги:

1. Создай GitHub-репозиторий и загрузи туда этот проект.
2. В Render создай новый `Web Service` из репозитория.
3. Добавь env-переменные:
   - `OPENAI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `BOT_MODE=webhook`
   - `BOT_PUBLIC_URL=https://<your-service>.onrender.com`
   - `BOT_WEBHOOK_SECRET=<long-random-string>`
4. Render поднимет контейнер из `Dockerfile`.

Почему `web` service, а не worker:
- Telegram webhook требует HTTP endpoint.

### 2. Railway

Хороший DX, но бесплатные условия меняются чаще. Конфиг тот же:

- `BOT_MODE=webhook`
- `BOT_PUBLIC_URL=https://<railway-app-domain>`
- `BOT_WEBHOOK_SECRET=...`

### 3. Fly.io

Подойдет, если хочешь больше контроля над инфраструктурой. Тоже лучше запускать в `webhook`-режиме.

## Можно ли задеплоить бесплатно на GitHub?

Для нормального Telegram-бота ответ практически `нет`.

Почему:

- `GitHub Pages` умеет только статический хостинг
- `GitHub Actions` не предназначен для постоянного процесса `24/7`
- polling-бот на Actions будет нестабилен и быстро упрется в лимиты
- webhook-боту нужен постоянно доступный HTTP endpoint, чего GitHub сам по себе не дает

То есть GitHub подходит как место для кода, CI и хранения проекта, но не как нормальная бесплатная платформа для always-on Telegram-бота.

## Что я рекомендую для продакшена

- код хранить на GitHub
- деплой сделать на Render или Railway
- если бот только для тебя, заполнять `ALLOWED_USER_IDS`
- если нужны долгие фоновые задачи, дальше можно вынести очередь в Redis/Postgres

## Идеи следующего шага

- добавить голосовые сообщения и распознавание аудио
- добавить документы и изображения
- добавить админ-команды
- вынести очередь из памяти в Redis
- подключить функции и внешние инструменты
