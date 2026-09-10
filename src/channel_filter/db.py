"""aiosqlite wrapper: connection helper, schema, and subscriber/keyword CRUD."""

from __future__ import annotations

import aiosqlite

from channel_filter.messages import MAX_KEYWORDS_PER_SUBSCRIBER, MIN_KEYWORD_LENGTH
from channel_filter.types import (
    Added,
    AddKeywordOutcome,
    AlreadyExists,
    LimitReached,
    NotFound,
    Removed,
    RemoveKeywordOutcome,
    Subscriber,
    SubscriberStats,
    TooShort,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    chat_id INTEGER PRIMARY KEY,
    active  INTEGER NOT NULL DEFAULT 1,
    blocked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS keywords (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER NOT NULL REFERENCES subscribers(chat_id) ON DELETE CASCADE,
    substring TEXT NOT NULL,
    UNIQUE(chat_id, substring)
);
"""


async def connect(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.executescript(SCHEMA)
    await conn.commit()
    return conn


async def get_or_create_subscriber(conn: aiosqlite.Connection, chat_id: int) -> Subscriber:
    await conn.execute(
        "INSERT INTO subscribers (chat_id) VALUES (?) ON CONFLICT(chat_id) DO NOTHING",
        (chat_id,),
    )
    await conn.commit()
    cursor = await conn.execute(
        "SELECT chat_id, active, blocked FROM subscribers WHERE chat_id = ?",
        (chat_id,),
    )
    row = await cursor.fetchone()
    return Subscriber(chat_id=row[0], active=bool(row[1]), blocked=bool(row[2]))


async def add_keyword(conn: aiosqlite.Connection, chat_id: int, substring: str) -> AddKeywordOutcome:
    normalized = substring.strip().lower()
    if len(normalized) < MIN_KEYWORD_LENGTH:
        return TooShort()

    cursor = await conn.execute(
        "SELECT 1 FROM keywords WHERE chat_id = ? AND substring = ?",
        (chat_id, normalized),
    )
    if await cursor.fetchone() is not None:
        return AlreadyExists()

    cursor = await conn.execute(
        "SELECT COUNT(*) FROM keywords WHERE chat_id = ?", (chat_id,)
    )
    (count,) = await cursor.fetchone()
    if count >= MAX_KEYWORDS_PER_SUBSCRIBER:
        return LimitReached()

    await conn.execute(
        "INSERT INTO keywords (chat_id, substring) VALUES (?, ?)",
        (chat_id, normalized),
    )
    await conn.commit()
    return Added()


async def set_blocked(conn: aiosqlite.Connection, chat_id: int, blocked: bool) -> bool:
    if blocked:
        cursor = await conn.execute(
            "UPDATE subscribers SET blocked = 1 WHERE chat_id = ?", (chat_id,)
        )
    else:
        cursor = await conn.execute(
            "UPDATE subscribers SET blocked = 0 WHERE chat_id = ? AND blocked = 1", (chat_id,)
        )
    await conn.commit()
    return cursor.rowcount > 0


async def get_subscriber_stats(conn: aiosqlite.Connection) -> SubscriberStats:
    cursor = await conn.execute(
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN blocked = 0 AND active = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN blocked = 0 AND active = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END)
        FROM subscribers
        """
    )
    total, active, paused, blocked = await cursor.fetchone()
    return SubscriberStats(
        total=total, active=active or 0, paused=paused or 0, blocked=blocked or 0
    )


async def delete_subscriber(conn: aiosqlite.Connection, chat_id: int) -> None:
    await conn.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))
    await conn.commit()


async def set_active(conn: aiosqlite.Connection, chat_id: int, active: bool) -> None:
    await conn.execute(
        "UPDATE subscribers SET active = ? WHERE chat_id = ?", (int(active), chat_id)
    )
    await conn.commit()


async def list_keywords(conn: aiosqlite.Connection, chat_id: int) -> list[str]:
    cursor = await conn.execute(
        "SELECT substring FROM keywords WHERE chat_id = ? ORDER BY id", (chat_id,)
    )
    rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def remove_keyword(conn: aiosqlite.Connection, chat_id: int, substring: str) -> RemoveKeywordOutcome:
    normalized = substring.strip().lower()
    cursor = await conn.execute(
        "DELETE FROM keywords WHERE chat_id = ? AND substring = ?",
        (chat_id, normalized),
    )
    await conn.commit()
    if cursor.rowcount == 0:
        return NotFound()
    return Removed()
