from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TaskRecord:
    id: int
    user_id: int
    chat_id: int
    request_text: str
    status: str
    created_at: str
    updated_at: str
    result_text: str | None
    error_text: str | None


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    request_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_text TEXT,
                    error_text TEXT
                );
                """
            )
            await db.commit()

    async def upsert_user(self, user_id: int, username: str | None, full_name: str) -> None:
        now = utcnow_iso()
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, username, full_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    updated_at = excluded.updated_at
                """,
                (user_id, username, full_name, now, now),
            )
            await db.commit()

    async def add_message(self, user_id: int, role: str, content: str) -> None:
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO messages (user_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, role, content, utcnow_iso()),
            )
            await db.commit()

    async def get_recent_messages(self, user_id: int, limit: int) -> list[dict[str, str]]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT role, content
                FROM messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cursor.fetchall()
        rows.reverse()
        return [{"role": role, "content": content} for role, content in rows]

    async def clear_messages(self, user_id: int) -> None:
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            await db.commit()

    async def create_task(self, user_id: int, chat_id: int, request_text: str) -> int:
        now = utcnow_iso()
        async with self._lock, aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                INSERT INTO tasks (
                    user_id, chat_id, request_text, status, created_at, updated_at
                )
                VALUES (?, ?, ?, 'queued', ?, ?)
                """,
                (user_id, chat_id, request_text, now, now),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def update_task_status(
        self,
        task_id: int,
        status: str,
        *,
        result_text: str | None = None,
        error_text: str | None = None,
    ) -> None:
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?, result_text = ?, error_text = ?
                WHERE id = ?
                """,
                (status, utcnow_iso(), result_text, error_text, task_id),
            )
            await db.commit()

    async def get_task(self, task_id: int) -> TaskRecord | None:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT id, user_id, chat_id, request_text, status, created_at, updated_at,
                       result_text, error_text
                FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return TaskRecord(*row)

    async def list_recent_tasks(self, user_id: int, limit: int = 10) -> list[TaskRecord]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT id, user_id, chat_id, request_text, status, created_at, updated_at,
                       result_text, error_text
                FROM tasks
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cursor.fetchall()
        return [TaskRecord(*row) for row in rows]

    async def count_active_tasks(self, user_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*)
                FROM tasks
                WHERE user_id = ? AND status IN ('queued', 'running')
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
        return int(row[0] if row else 0)

    async def cancel_task(self, task_id: int, user_id: int) -> bool:
        async with self._lock, aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                UPDATE tasks
                SET status = 'cancelled', updated_at = ?, error_text = 'Cancelled by user'
                WHERE id = ? AND user_id = ? AND status = 'queued'
                """,
                (utcnow_iso(), task_id, user_id),
            )
            await db.commit()
        return cursor.rowcount > 0

    async def cancel_all_queued_tasks(self, user_id: int) -> int:
        async with self._lock, aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                UPDATE tasks
                SET status = 'cancelled', updated_at = ?, error_text = 'Cancelled by user'
                WHERE user_id = ? AND status = 'queued'
                """,
                (utcnow_iso(), user_id),
            )
            await db.commit()
        return int(cursor.rowcount)
