"""Unit tests for Notifier resilience: blocked subscribers, unexpected errors, rate-limit retry."""

import asyncio
import contextlib
import logging

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage

from channel_filter import db
from channel_filter.notifier import NotificationJob, Notifier


class FakeBot:
    def __init__(self, fail_with: dict[int, Exception] | None = None) -> None:
        self._fail_with = dict(fail_with or {})
        self.sent: list[int] = []

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs) -> None:
        if chat_id in self._fail_with:
            exc = self._fail_with.pop(chat_id)
            raise exc
        self.sent.append(chat_id)


async def _run_and_settle(notifier: Notifier, bot, jobs: list[NotificationJob]) -> None:
    task = asyncio.create_task(notifier.run(bot))
    for job in jobs:
        await notifier.enqueue(job)
    await asyncio.sleep(0.2)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def _forbidden_error(chat_id: int) -> TelegramForbiddenError:
    method = SendMessage(chat_id=chat_id, text="x")
    return TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")


async def test_forbidden_error_marks_subscriber_blocked_and_continues_queue(conn, caplog):
    caplog.set_level(logging.INFO)
    await db.get_or_create_subscriber(conn, 1)
    await db.get_or_create_subscriber(conn, 2)
    bot = FakeBot(fail_with={1: _forbidden_error(1)})
    notifier = Notifier(channel_username=None, conn=conn)

    await _run_and_settle(
        notifier,
        bot,
        [NotificationJob(chat_id=1, text="hello"), NotificationJob(chat_id=2, text="world")],
    )

    subscriber = await db.get_or_create_subscriber(conn, 1)
    assert subscriber.blocked is True
    assert bot.sent == [2]
    assert any("1" in record.getMessage() for record in caplog.records)


async def test_unexpected_error_drops_job_and_continues_queue(conn, caplog):
    caplog.set_level(logging.INFO)
    await db.get_or_create_subscriber(conn, 1)
    await db.get_or_create_subscriber(conn, 2)
    bot = FakeBot(fail_with={1: RuntimeError("boom")})
    notifier = Notifier(channel_username=None, conn=conn)

    await _run_and_settle(
        notifier,
        bot,
        [NotificationJob(chat_id=1, text="hello"), NotificationJob(chat_id=2, text="world")],
    )

    subscriber = await db.get_or_create_subscriber(conn, 1)
    assert subscriber.blocked is False
    assert bot.sent == [2]
    assert any("1" in record.getMessage() for record in caplog.records)


async def test_retry_after_waits_then_requeues_and_eventually_delivers(conn):
    await db.get_or_create_subscriber(conn, 1)
    method = SendMessage(chat_id=1, text="x")
    retry_error = TelegramRetryAfter(method=method, message="Too Many Requests", retry_after=0)
    bot = FakeBot(fail_with={1: retry_error})
    notifier = Notifier(channel_username=None, conn=conn)

    await _run_and_settle(notifier, bot, [NotificationJob(chat_id=1, text="hello")])

    assert bot.sent == [1]
