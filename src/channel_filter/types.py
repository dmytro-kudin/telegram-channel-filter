"""Core domain types (data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Subscriber:
    chat_id: int
    active: bool
    blocked: bool

    @property
    def eligible(self) -> bool:
        return self.active and not self.blocked


@dataclass(frozen=True)
class Keyword:
    id: int
    chat_id: int
    substring: str


@dataclass(frozen=True)
class ChannelPost:
    message_id: int
    text: str


@dataclass(frozen=True)
class Skip:
    pass


@dataclass(frozen=True)
class BroadcastAll:
    pass


@dataclass(frozen=True)
class MatchedUsers:
    chat_ids: frozenset[int]


@dataclass(frozen=True)
class Continue:
    pass


Outcome = Skip | BroadcastAll | MatchedUsers | Continue


@dataclass(frozen=True)
class Added:
    pass


@dataclass(frozen=True)
class AlreadyExists:
    pass


@dataclass(frozen=True)
class TooShort:
    pass


@dataclass(frozen=True)
class LimitReached:
    pass


AddKeywordOutcome = Added | AlreadyExists | TooShort | LimitReached


@dataclass(frozen=True)
class Removed:
    pass


@dataclass(frozen=True)
class NotFound:
    pass


RemoveKeywordOutcome = Removed | NotFound


@dataclass(frozen=True)
class SubscriberStats:
    total: int
    active: int
    paused: int
    blocked: int

