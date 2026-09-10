"""Ordered, short-circuiting content-handling rule pipeline (FR-016)."""

from __future__ import annotations

from typing import Callable, Protocol

from channel_filter.types import BroadcastAll, ChannelPost, Continue, MatchedUsers, Outcome, Skip

Stage = Callable[[ChannelPost], Outcome]

JAR_LINK_PATTERN = "send.monobank.ua/jar/"
NUMERIC_PUNCTUATION = set(" ,.")


class MatcherLike(Protocol):
    def find_matching_chat_ids(self, text: str) -> frozenset[int]: ...


def jar_link_stage(post: ChannelPost) -> Outcome:
    if JAR_LINK_PATTERN in post.text:
        return BroadcastAll()
    return Continue()


def pure_number_stage(post: ChannelPost) -> Outcome:
    stripped = post.text.strip()
    has_digit = any(char.isdigit() for char in stripped)
    is_only_numeric_chars = all(char.isdigit() or char in NUMERIC_PUNCTUATION for char in stripped)
    if has_digit and is_only_numeric_chars:
        return Skip()
    return Continue()


def keyword_match_stage(matcher: MatcherLike) -> Stage:
    def stage(post: ChannelPost) -> Outcome:
        return MatchedUsers(matcher.find_matching_chat_ids(post.text.lower()))

    return stage


def run_pipeline(stages: list[Stage], post: ChannelPost) -> Outcome:
    outcome: Outcome = Continue()
    for stage in stages:
        outcome = stage(post)
        if not isinstance(outcome, Continue):
            return outcome
    return outcome
