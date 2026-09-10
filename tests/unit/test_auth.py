from channel_filter import db
from channel_filter import messages as msg
from channel_filter.auth import refuse_if_blocked, require_operator

from .doubles import make_message

ADMIN_CHAT_ID = 999


@require_operator
async def _admin_handler(message, conn) -> None:
    await message.answer("handled")


@refuse_if_blocked
async def _subscriber_handler(message, conn) -> None:
    await message.answer("handled")


async def test_require_operator_accepts_configured_admin(conn):
    message = make_message(ADMIN_CHAT_ID)

    await _admin_handler(message, conn=conn, admin_chat_id=ADMIN_CHAT_ID)

    assert message.sent == ["handled"]


async def test_require_operator_refuses_everyone_else(conn):
    message = make_message(1)

    await _admin_handler(message, conn=conn, admin_chat_id=ADMIN_CHAT_ID)

    assert message.sent == [msg.NOT_AUTHORIZED]


async def test_refuse_if_blocked_allows_non_blocked_subscriber(conn):
    await db.get_or_create_subscriber(conn, 1)
    message = make_message(1)

    await _subscriber_handler(message, conn=conn)

    assert message.sent == ["handled"]


async def test_refuse_if_blocked_refuses_blocked_subscriber(conn):
    await db.get_or_create_subscriber(conn, 1)
    await conn.execute("UPDATE subscribers SET blocked = 1 WHERE chat_id = 1")
    await conn.commit()
    message = make_message(1)

    await _subscriber_handler(message, conn=conn)

    assert message.sent == [msg.BLOCKED]
