"""Cross-cutting authorization decorators (FR-017/FR-018, FR-021)."""

from __future__ import annotations

import functools
from typing import Any, Awaitable, Callable

import aiosqlite
from aiogram.types import Message

from channel_filter import db
from channel_filter.messages import BLOCKED, NOT_AUTHORIZED

Handler = Callable[..., Awaitable[None]]


def require_operator(handler: Handler) -> Handler:
    """Wraps an admin handler so only the configured operator can invoke it.

    Declares its own real (message, *, admin_chat_id, **kwargs) signature —
    aiogram's DI inspects this to inject admin_chat_id/conn/etc. by name, so
    functools.wraps' __wrapped__ link (which would make inspection see the
    inner handler's signature instead) is deliberately dropped.
    """

    @functools.wraps(handler)
    async def wrapper(message: Message, *, admin_chat_id: int, **kwargs: Any) -> None:
        if message.chat.id != admin_chat_id:
            await message.answer(NOT_AUTHORIZED)
            return
        await handler(message, **kwargs)

    del wrapper.__wrapped__
    return wrapper


def refuse_if_blocked(handler: Handler) -> Handler:
    """Wraps a subscriber handler so a blocked subscriber gets refused.

    Same __wrapped__ caveat as require_operator applies here.
    """

    @functools.wraps(handler)
    async def wrapper(message: Message, *, conn: aiosqlite.Connection, **kwargs: Any) -> None:
        subscriber = await db.get_or_create_subscriber(conn, message.chat.id)
        if subscriber.blocked:
            await message.answer(BLOCKED)
            return
        await handler(message, conn=conn, **kwargs)

    del wrapper.__wrapped__
    return wrapper
