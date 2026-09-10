"""aiogram routers: subscriber commands (+ admin commands, added in later phases)."""

from __future__ import annotations

import aiosqlite
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from channel_filter import db
from channel_filter import messages as msg
from channel_filter.auth import refuse_if_blocked, require_operator
from channel_filter.matcher import AutomatonManager
from channel_filter.notifier import NotificationJob, Notifier
from channel_filter.types import Added, AlreadyExists, LimitReached, Removed, TooShort

ELIGIBLE_SUBSCRIBERS_QUERY = "SELECT chat_id FROM subscribers WHERE active = 1 AND blocked = 0"


@refuse_if_blocked
async def start_handler(
    message: Message, conn: aiosqlite.Connection, matcher: AutomatonManager
) -> None:
    await db.get_or_create_subscriber(conn, message.chat.id)
    await db.set_active(conn, message.chat.id, True)
    await matcher.rebuild()
    await message.answer(msg.WELCOME)


@refuse_if_blocked
async def add_handler(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    matcher: AutomatonManager,
) -> None:
    await db.get_or_create_subscriber(conn, message.chat.id)

    keyword = (command.args or "").strip()
    outcome = await db.add_keyword(conn, message.chat.id, keyword)

    match outcome:
        case Added():
            await matcher.rebuild()
            await message.answer(msg.add_success(keyword.lower()))
        case AlreadyExists():
            await message.answer(msg.ADD_ALREADY_EXISTS)
        case TooShort():
            await message.answer(msg.ADD_TOO_SHORT)
        case LimitReached():
            await message.answer(msg.ADD_LIMIT_REACHED)


@refuse_if_blocked
async def list_handler(message: Message, conn: aiosqlite.Connection) -> None:
    keywords = await db.list_keywords(conn, message.chat.id)
    if keywords:
        await message.answer(msg.list_keywords(sorted(keywords)))
    else:
        await message.answer(msg.LIST_EMPTY)


@refuse_if_blocked
async def remove_handler(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    matcher: AutomatonManager,
) -> None:
    keyword = (command.args or "").strip()
    outcome = await db.remove_keyword(conn, message.chat.id, keyword)

    match outcome:
        case Removed():
            await matcher.rebuild()
            await message.answer(msg.remove_success(keyword.lower()))
        case _:
            await message.answer(msg.REMOVE_NOT_FOUND)


@refuse_if_blocked
async def stop_handler(
    message: Message, conn: aiosqlite.Connection, matcher: AutomatonManager
) -> None:
    await db.set_active(conn, message.chat.id, False)
    await matcher.rebuild()
    await message.answer(msg.STOP_CONFIRMATION)


async def deleteme_handler(
    message: Message, conn: aiosqlite.Connection, matcher: AutomatonManager
) -> None:
    await db.delete_subscriber(conn, message.chat.id)
    await matcher.rebuild()
    await message.answer(msg.DELETE_CONFIRMATION)


@require_operator
async def block_handler(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    matcher: AutomatonManager,
) -> None:
    try:
        target_chat_id = int((command.args or "").strip())
    except ValueError:
        await message.answer(msg.BLOCK_NOT_FOUND)
        return

    if await db.set_blocked(conn, target_chat_id, True):
        await matcher.rebuild()
        await message.answer(msg.block_success(target_chat_id))
    else:
        await message.answer(msg.BLOCK_NOT_FOUND)


@require_operator
async def unblock_handler(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    matcher: AutomatonManager,
) -> None:
    try:
        target_chat_id = int((command.args or "").strip())
    except ValueError:
        await message.answer(msg.UNBLOCK_NOT_FOUND)
        return

    if await db.set_blocked(conn, target_chat_id, False):
        await matcher.rebuild()
        await message.answer(msg.unblock_success(target_chat_id))
    else:
        await message.answer(msg.UNBLOCK_NOT_FOUND)


@require_operator
async def broadcast_handler(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    notifier: Notifier,
) -> None:
    text = (command.args or "").strip()
    cursor = await conn.execute(ELIGIBLE_SUBSCRIBERS_QUERY)
    rows = await cursor.fetchall()
    for (chat_id,) in rows:
        await notifier.enqueue(NotificationJob(chat_id=chat_id, text=text, message_id=None))
    await message.answer(msg.broadcast_queued(len(rows)))


@require_operator
async def stats_handler(message: Message, conn: aiosqlite.Connection) -> None:
    stats = await db.get_subscriber_stats(conn)
    await message.answer(
        msg.stats(total=stats.total, active=stats.active, paused=stats.paused, blocked=stats.blocked)
    )


async def help_handler(message: Message) -> None:
    await message.answer(msg.HELP)


def build_router() -> Router:
    router = Router()
    router.message.register(start_handler, Command("start"))
    router.message.register(add_handler, Command("add"))
    router.message.register(list_handler, Command("list"))
    router.message.register(remove_handler, Command("remove"))
    router.message.register(stop_handler, Command("stop"))
    router.message.register(deleteme_handler, Command("deleteme"))
    router.message.register(help_handler, Command("help"))
    router.message.register(block_handler, Command("block"))
    router.message.register(unblock_handler, Command("unblock"))
    router.message.register(broadcast_handler, Command("broadcast"))
    router.message.register(stats_handler, Command("stats"))
    return router
