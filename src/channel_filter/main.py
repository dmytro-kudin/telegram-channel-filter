"""Startup wiring: open DB, build automaton, run Telethon and aiogram concurrently."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable

import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from channel_filter import bot as bot_module
from channel_filter import db
from channel_filter.config import load_config
from channel_filter.listener import run_listener_forever
from channel_filter.matcher import AutomatonManager
from channel_filter.notifier import Notifier
from channel_filter.pipeline import Stage, jar_link_stage, keyword_match_stage, pure_number_stage

RESTART_DELAY = 2.0

SUBSCRIBER_COMMANDS = [
    BotCommand(command="start", description="Почати або відновити сповіщення"),
    BotCommand(command="add", description="Додати ключове слово"),
    BotCommand(command="remove", description="Видалити ключове слово"),
    BotCommand(command="list", description="Показати ключові слова"),
    BotCommand(command="stop", description="Призупинити сповіщення"),
    BotCommand(command="deleteme", description="Видалити акаунт і ключові слова"),
    BotCommand(command="help", description="Показати довідку"),
]


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger().setLevel(logging.INFO)


async def supervise(name: str, coro_factory: Callable[[], Awaitable[None]]) -> None:
    """Run coro_factory() forever, restarting it after RESTART_DELAY on any failure."""
    while True:
        try:
            await coro_factory()
        except Exception:
            logging.exception("%s crashed, restarting in %ss", name, RESTART_DELAY)
        else:
            logging.warning("%s exited cleanly, restarting in %ss", name, RESTART_DELAY)
        await asyncio.sleep(RESTART_DELAY)


def build_supervised_tasks(
    *,
    api_id: int,
    api_hash: str,
    source_channel: str,
    stages: list[Stage],
    conn: aiosqlite.Connection,
    notifier: Notifier,
    channel_username: str,
    dp: Dispatcher,
    aiogram_bot: Bot,
) -> list[Awaitable[None]]:
    """Wrap the three long-running components in independent supervise() loops."""
    return [
        supervise(
            "telethon-listener",
            lambda: run_listener_forever(
                api_id=api_id,
                api_hash=api_hash,
                source_channel=source_channel,
                stages=stages,
                conn=conn,
                notifier=notifier,
                channel_username=channel_username,
            ),
        ),
        supervise("bot-polling", lambda: dp.start_polling(aiogram_bot)),
        supervise("notifier", lambda: notifier.run(aiogram_bot)),
    ]


async def main() -> None:
    configure_logging()
    config = load_config()

    conn = await db.connect(config.db_path)
    matcher = AutomatonManager(conn)
    await matcher.build()

    stages = [jar_link_stage, pure_number_stage, keyword_match_stage(matcher)]
    channel_username = config.source_channel.lstrip("@")
    notifier = Notifier(conn=conn, channel_username=channel_username)

    aiogram_bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp.include_router(bot_module.build_router())
    dp["conn"] = conn
    dp["matcher"] = matcher
    dp["admin_chat_id"] = config.admin_chat_id
    dp["notifier"] = notifier

    await aiogram_bot.set_my_commands(SUBSCRIBER_COMMANDS)

    await asyncio.gather(
        *build_supervised_tasks(
            api_id=config.api_id,
            api_hash=config.api_hash,
            source_channel=config.source_channel,
            stages=stages,
            conn=conn,
            notifier=notifier,
            channel_username=channel_username,
            dp=dp,
            aiogram_bot=aiogram_bot,
        )
    )


def run() -> None:
    try:
        asyncio.run(main())
    except Exception:
        logging.critical("unrecoverable failure escaped all supervisors", exc_info=True)
        logging.shutdown()
        os._exit(1)


if __name__ == "__main__":
    run()
