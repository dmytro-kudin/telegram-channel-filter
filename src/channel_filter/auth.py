"""Cross-cutting authorization decorators (FR-017/FR-018, FR-021)."""

from __future__ import annotations

import functools
import inspect
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
    inner handler's signature instead) is deliberately dropped. Because the
    wrapper accepts **kwargs, aiogram injects its whole context dict (bot,
    dispatcher, state, ...); only forward the subset the inner handler
    actually declares, or it chokes on the extras.
    """
    handler_params = inspect.signature(handler).parameters

    @functools.wraps(handler)
    async def wrapper(message: Message, *, admin_chat_id: int, **kwargs: Any) -> None:
        if message.chat.id != admin_chat_id:
            await message.answer(NOT_AUTHORIZED)
            return
        await handler(message, **{k: v for k, v in kwargs.items() if k in handler_params})

    del wrapper.__wrapped__
    return wrapper


def refuse_if_blocked(handler: Handler) -> Handler:
    """Wraps a subscriber handler so a blocked subscriber gets refused.

    Same __wrapped__ and kwargs-filtering caveats as require_operator apply
    here.
    """
    handler_params = inspect.signature(handler).parameters

    @functools.wraps(handler)
    async def wrapper(message: Message, *, conn: aiosqlite.Connection, **kwargs: Any) -> None:
        subscriber = await db.get_or_create_subscriber(conn, message.chat.id)
        if subscriber.blocked:
            await message.answer(BLOCKED)
            return
        filtered = {k: v for k, v in kwargs.items() if k in handler_params}
        await handler(message, conn=conn, **filtered)

    del wrapper.__wrapped__
    return wrapper


def inject_admin_chat_id(handler: Handler) -> Handler:
    """Wraps a handler to inject admin_chat_id from dispatcher context.

    For handlers that need admin_chat_id but don't restrict access (unlike
    require_operator). Same __wrapped__ and kwargs-filtering caveats apply.
    """
    handler_params = inspect.signature(handler).parameters

    @functools.wraps(handler)
    async def wrapper(message: Message, *, admin_chat_id: int, **kwargs: Any) -> None:
        filtered = {k: v for k, v in kwargs.items() if k in handler_params}
        await handler(message, admin_chat_id=admin_chat_id, **filtered)

    del wrapper.__wrapped__
    return wrapper
