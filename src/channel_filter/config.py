"""Loads deployment configuration from a .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str
    source_channel: str
    admin_chat_id: int
    db_path: str


def load_config() -> Config:
    load_dotenv()
    return Config(
        api_id=int(os.environ["API_ID"]),
        api_hash=os.environ["API_HASH"],
        bot_token=os.environ["BOT_TOKEN"],
        source_channel=os.environ["SOURCE_CHANNEL"],
        admin_chat_id=int(os.environ["ADMIN_CHAT_ID"]),
        db_path=os.environ["DB_PATH"],
    )
