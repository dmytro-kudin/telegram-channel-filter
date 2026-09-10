"""Telethon NewMessage listener: detect posts, run the pipeline, enqueue deliveries."""

from __future__ import annotations

import aiosqlite
from telethon import TelegramClient, events

from channel_filter.notifier import NotificationJob, Notifier
from channel_filter.pipeline import Stage, run_pipeline
from channel_filter.types import BroadcastAll, ChannelPost, MatchedUsers, Skip

ELIGIBLE_SUBSCRIBERS_QUERY = "SELECT chat_id FROM subscribers WHERE active = 1 AND blocked = 0"


async def process_channel_post(
    post: ChannelPost,
    stages: list[Stage],
    conn: aiosqlite.Connection,
    notifier: Notifier,
    channel_username: str,
) -> None:
    outcome = run_pipeline(stages, post)

    if isinstance(outcome, Skip):
        return

    if isinstance(outcome, MatchedUsers):
        for chat_id in outcome.chat_ids:
            await notifier.enqueue(
                NotificationJob(chat_id=chat_id, text=post.text, message_id=post.message_id)
            )
        return

    if isinstance(outcome, BroadcastAll):
        cursor = await conn.execute(ELIGIBLE_SUBSCRIBERS_QUERY)
        rows = await cursor.fetchall()
        for (chat_id,) in rows:
            await notifier.enqueue(
                NotificationJob(chat_id=chat_id, text=post.text, message_id=post.message_id)
            )
        return


def build_client(
    api_id: int,
    api_hash: str,
    source_channel: str,
    stages: list[Stage],
    conn: aiosqlite.Connection,
    notifier: Notifier,
    channel_username: str,
) -> TelegramClient:
    client = TelegramClient("channel_filter", api_id, api_hash)

    @client.on(events.NewMessage(chats=source_channel))
    async def _on_new_message(event: events.NewMessage.Event) -> None:
        post = ChannelPost(message_id=event.message.id, text=event.message.raw_text or "")
        await process_channel_post(post, stages, conn, notifier, channel_username)

    return client
