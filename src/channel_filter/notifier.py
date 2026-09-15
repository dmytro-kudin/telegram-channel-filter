"""Delivery queue: NotificationJob, asyncio.Queue, and a rate-limited sender."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.utils.keyboard import InlineKeyboardBuilder

from channel_filter import db
from channel_filter.messages import VIEW_ORIGINAL

MESSAGES_PER_SECOND = 25.0


@dataclass(frozen=True)
class NotificationJob:
    chat_id: int
    text: str
    message_id: int | None = None


class Notifier:
    """Single global queue feeding one sender task with a token-bucket throttle."""

    def __init__(self, conn: aiosqlite.Connection, channel_username: str | None = None) -> None:
        self._queue: asyncio.Queue[NotificationJob] = asyncio.Queue()
        self._conn = conn
        self._channel_username = channel_username
        self._min_interval = 1.0 / MESSAGES_PER_SECOND
        self._last_sent = 0.0

    async def enqueue(self, job: NotificationJob) -> None:
        await self._queue.put(job)

    async def run(self, bot: Bot) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._send(bot, job)
            except Exception:
                logging.exception(
                    "unexpected error handling notification job for %s", job.chat_id
                )

    async def _send(self, bot: Bot, job: NotificationJob) -> None:
        now = time.monotonic()
        wait = self._min_interval - (now - self._last_sent)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_sent = time.monotonic()

        markup = None
        if job.message_id is not None and self._channel_username is not None:
            builder = InlineKeyboardBuilder()
            link = f"https://t.me/{self._channel_username}/{job.message_id}"
            builder.button(text=VIEW_ORIGINAL, url=link)
            markup = builder.as_markup()

        try:
            await bot.send_message(job.chat_id, job.text, reply_markup=markup)
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            await self._queue.put(job)
        except TelegramForbiddenError:
            await db.set_blocked(self._conn, job.chat_id, True)
            logging.info("subscriber %s blocked the bot; marked blocked", job.chat_id)
        except Exception:
            logging.exception("failed to deliver notification to %s", job.chat_id)
