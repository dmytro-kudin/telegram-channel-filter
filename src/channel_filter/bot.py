"""aiogram routers: subscriber commands (+ admin commands, added in later phases)."""

from __future__ import annotations

import aiosqlite
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from channel_filter import db, keyboards
from channel_filter import messages as msg
from channel_filter.auth import refuse_if_blocked, require_operator
from channel_filter.matcher import AutomatonManager
from channel_filter.notifier import NotificationJob, Notifier
from channel_filter.types import (
    Added,
    AddKeywordOutcome,
    AlreadyExists,
    Keyword,
    LimitReached,
    Removed,
    TooShort,
)

ELIGIBLE_SUBSCRIBERS_QUERY = "SELECT chat_id FROM subscribers WHERE active = 1 AND blocked = 0"


class AddKeywords(StatesGroup):
    """Guided add-keyword flow state (contracts/add-flow.md)."""

    waiting = State()


async def _answer_with_menu(message: Message, conn: aiosqlite.Connection, text: str) -> None:
    """Reply with `text` and the persistent subscriber menu reflecting current active state."""
    subscriber = await db.get_or_create_subscriber(conn, message.chat.id)
    await message.answer(text, reply_markup=keyboards.subscriber_menu(subscriber.active))


def _parse_keyword_batch(raw: str) -> list[str]:
    """Split comma-separated input into words; blank/comma-only input yields one empty entry."""
    pieces = [piece.strip() for piece in raw.split(",")]
    non_empty = [piece for piece in pieces if piece]
    return non_empty or [""]


def _add_outcome_message(keyword: str, outcome: AddKeywordOutcome) -> str:
    match outcome:
        case Added():
            return msg.add_success(keyword.lower())
        case AlreadyExists():
            return msg.ADD_ALREADY_EXISTS
        case TooShort():
            return msg.ADD_TOO_SHORT
        case LimitReached():
            return msg.ADD_LIMIT_REACHED


async def _add_keywords_batch(
    conn: aiosqlite.Connection, chat_id: int, raw: str
) -> tuple[str, bool]:
    """Add each comma-separated word independently; return (reply text, whether any succeeded)."""
    words = _parse_keyword_batch(raw)
    lines = []
    any_added = False
    for word in words:
        outcome = await db.add_keyword(conn, chat_id, word)
        if isinstance(outcome, Added):
            any_added = True
        lines.append(_add_outcome_message(word, outcome))
    return "\n".join(lines), any_added


@refuse_if_blocked
async def start_handler(
    message: Message, conn: aiosqlite.Connection, matcher: AutomatonManager
) -> None:
    await db.get_or_create_subscriber(conn, message.chat.id)
    await db.set_active(conn, message.chat.id, True)
    await matcher.rebuild()
    await _answer_with_menu(message, conn, msg.WELCOME)


@refuse_if_blocked
async def add_handler(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    matcher: AutomatonManager,
) -> None:
    await db.get_or_create_subscriber(conn, message.chat.id)

    reply_text, any_added = await _add_keywords_batch(conn, message.chat.id, command.args or "")
    if any_added:
        await matcher.rebuild()
    await _answer_with_menu(message, conn, reply_text)


@refuse_if_blocked
async def add_prompt_handler(message: Message, conn: aiosqlite.Connection, state: FSMContext) -> None:
    await _answer_with_menu(message, conn, msg.ADD_PROMPT)
    await state.set_state(AddKeywords.waiting)


async def guided_add_input_handler(
    message: Message,
    conn: aiosqlite.Connection,
    matcher: AutomatonManager,
    state: FSMContext,
) -> None:
    await db.get_or_create_subscriber(conn, message.chat.id)
    reply_text, any_added = await _add_keywords_batch(conn, message.chat.id, message.text or "")
    if any_added:
        await matcher.rebuild()
    await _answer_with_menu(message, conn, reply_text)
    await state.clear()


async def my_keywords_button_handler(
    message: Message, conn: aiosqlite.Connection, state: FSMContext
) -> None:
    await state.clear()
    await list_handler(message, conn=conn)


async def help_button_handler(
    message: Message, conn: aiosqlite.Connection, state: FSMContext, admin_chat_id: int
) -> None:
    await state.clear()
    await help_handler(message, conn=conn, admin_chat_id=admin_chat_id)


async def pause_button_handler(
    message: Message, conn: aiosqlite.Connection, matcher: AutomatonManager, state: FSMContext
) -> None:
    await state.clear()
    await stop_handler(message, conn=conn, matcher=matcher)


async def resume_button_handler(
    message: Message, conn: aiosqlite.Connection, matcher: AutomatonManager, state: FSMContext
) -> None:
    await state.clear()
    await start_handler(message, conn=conn, matcher=matcher)


@refuse_if_blocked
async def list_handler(message: Message, conn: aiosqlite.Connection) -> None:
    keywords = await db.list_keywords(conn, message.chat.id)
    if keywords:
        await message.answer(msg.LIST_HEADER, reply_markup=keyboards.keyword_list_keyboard(keywords))
    else:
        await _answer_with_menu(message, conn, msg.LIST_EMPTY)


async def _find_keyword(conn: aiosqlite.Connection, chat_id: int, keyword_id: int) -> Keyword | None:
    keywords = await db.list_keywords(conn, chat_id)
    return next((kw for kw in keywords if kw.id == keyword_id), None)


async def _refresh_keyword_list(message: Message, keywords: list[Keyword]) -> None:
    if keywords:
        await message.edit_text(msg.LIST_HEADER, reply_markup=keyboards.keyword_list_keyboard(keywords))
    else:
        await message.edit_text(msg.LIST_EMPTY, reply_markup=None)


async def keyword_tap_handler(callback: CallbackQuery, conn: aiosqlite.Connection) -> None:
    _, id_str = callback.data.split(":")
    keyword_id = int(id_str)
    keyword = await _find_keyword(conn, callback.message.chat.id, keyword_id)
    if keyword is None:
        await callback.answer(msg.KEYWORD_ALREADY_REMOVED)
        await _refresh_keyword_list(
            callback.message, await db.list_keywords(conn, callback.message.chat.id)
        )
        return
    await callback.message.edit_text(
        msg.delete_confirm_prompt(keyword.substring),
        reply_markup=keyboards.delete_confirm_keyboard(keyword.id),
    )
    await callback.answer()


async def keyword_delete_confirm_handler(
    callback: CallbackQuery, conn: aiosqlite.Connection, matcher: AutomatonManager
) -> None:
    _, id_str, action = callback.data.split(":")
    keyword_id = int(id_str)
    chat_id = callback.message.chat.id

    if action == "n":
        await _refresh_keyword_list(callback.message, await db.list_keywords(conn, chat_id))
        await callback.answer()
        return

    keyword = await _find_keyword(conn, chat_id, keyword_id)
    if keyword is None:
        await callback.answer(msg.KEYWORD_ALREADY_REMOVED)
        await _refresh_keyword_list(callback.message, await db.list_keywords(conn, chat_id))
        return

    outcome = await db.remove_keyword_by_id(conn, chat_id, keyword_id)
    match outcome:
        case Removed():
            await matcher.rebuild()
            remaining = await db.list_keywords(conn, chat_id)
            if remaining:
                text = f"{msg.remove_success(keyword.substring)}\n\n{msg.LIST_HEADER}"
                await callback.message.edit_text(
                    text, reply_markup=keyboards.keyword_list_keyboard(remaining)
                )
            else:
                text = f"{msg.remove_success(keyword.substring)}\n\n{msg.LIST_EMPTY}"
                await callback.message.edit_text(text, reply_markup=None)
            await callback.answer()
        case _:
            await callback.answer(msg.KEYWORD_ALREADY_REMOVED)
            await _refresh_keyword_list(callback.message, await db.list_keywords(conn, chat_id))


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
            await _answer_with_menu(message, conn, msg.remove_success(keyword.lower()))
        case _:
            await _answer_with_menu(message, conn, msg.REMOVE_NOT_FOUND)


@refuse_if_blocked
async def stop_handler(
    message: Message, conn: aiosqlite.Connection, matcher: AutomatonManager
) -> None:
    await db.set_active(conn, message.chat.id, False)
    await matcher.rebuild()
    await _answer_with_menu(message, conn, msg.STOP_CONFIRMATION)


async def deleteme_handler(
    message: Message, conn: aiosqlite.Connection, matcher: AutomatonManager
) -> None:
    await db.delete_subscriber(conn, message.chat.id)
    await matcher.rebuild()
    # Deliberately not `_answer_with_menu`: re-fetching via get_or_create_subscriber
    # here would resurrect the just-deleted row. A future /start begins as a fresh,
    # active subscriber, so the "active" menu variant is the correct default.
    await message.answer(msg.DELETE_CONFIRMATION, reply_markup=keyboards.subscriber_menu(active=True))


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


async def help_handler(message: Message, conn: aiosqlite.Connection, admin_chat_id: int) -> None:
    text = msg.HELP
    if message.chat.id == admin_chat_id:
        text = f"{msg.HELP}\n\n{msg.ADMIN_HELP_SECTION}"
    await _answer_with_menu(message, conn, text)


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

    # Button-text handlers (registered before the guided-input state catch-all below,
    # so tapping a different button always wins over "treat this as keyword input").
    router.message.register(add_prompt_handler, F.text == keyboards.ADD_KEYWORD)
    router.message.register(my_keywords_button_handler, F.text == keyboards.MY_KEYWORDS)
    router.message.register(help_button_handler, F.text == keyboards.HELP)
    router.message.register(pause_button_handler, F.text == keyboards.PAUSE)
    router.message.register(resume_button_handler, F.text == keyboards.RESUME)

    router.message.register(guided_add_input_handler, AddKeywords.waiting)

    router.callback_query.register(keyword_tap_handler, F.data.startswith("kw:"))
    router.callback_query.register(keyword_delete_confirm_handler, F.data.startswith("kwdel:"))
    return router
