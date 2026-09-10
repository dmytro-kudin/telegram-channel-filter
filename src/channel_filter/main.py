"""Startup wiring: open DB, build automaton, run Telethon and aiogram concurrently."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from channel_filter import bot as bot_module
from channel_filter import db
from channel_filter.config import load_config
from channel_filter.listener import build_client
from channel_filter.matcher import AutomatonManager
from channel_filter.notifier import Notifier
from channel_filter.pipeline import jar_link_stage, keyword_match_stage, pure_number_stage

SUBSCRIBER_COMMANDS = [
    BotCommand(command="start", description="Почати або відновити сповіщення"),
    BotCommand(command="add", description="Додати ключове слово"),
    BotCommand(command="remove", description="Видалити ключове слово"),
    BotCommand(command="list", description="Показати ключові слова"),
    BotCommand(command="stop", description="Призупинити сповіщення"),
    BotCommand(command="deleteme", description="Видалити акаунт і ключові слова"),
    BotCommand(command="help", description="Показати довідку"),
]


async def main() -> None:
    config = load_config()

    conn = await db.connect(config.db_path)
    matcher = AutomatonManager(conn)
    await matcher.build()

    stages = [jar_link_stage, pure_number_stage, keyword_match_stage(matcher)]
    channel_username = config.source_channel.lstrip("@")
    notifier = Notifier(channel_username=channel_username)

    client = build_client(
        api_id=config.api_id,
        api_hash=config.api_hash,
        source_channel=config.source_channel,
        stages=stages,
        conn=conn,
        notifier=notifier,
        channel_username=channel_username,
    )

    aiogram_bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp.include_router(bot_module.build_router())
    dp["conn"] = conn
    dp["matcher"] = matcher
    dp["admin_chat_id"] = config.admin_chat_id
    dp["notifier"] = notifier

    await aiogram_bot.set_my_commands(SUBSCRIBER_COMMANDS)

    await client.start()

    await asyncio.gather(
        client.run_until_disconnected(),
        dp.start_polling(aiogram_bot),
        notifier.run(aiogram_bot),
    )


if __name__ == "__main__":
    asyncio.run(main())
