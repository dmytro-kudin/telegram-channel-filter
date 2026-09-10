from channel_filter.pipeline import (
    jar_link_stage,
    keyword_match_stage,
    pure_number_stage,
    run_pipeline,
)
from channel_filter.types import BroadcastAll, ChannelPost, Continue, MatchedUsers, Skip


class _StubAutomaton:
    def __init__(self, matches: frozenset[int]) -> None:
        self._matches = matches

    def find_matching_chat_ids(self, text: str) -> frozenset[int]:
        return self._matches


def test_keyword_match_stage_matches_case_insensitively():
    stage = keyword_match_stage(_StubAutomaton(frozenset({1})))
    post = ChannelPost(message_id=1, text="Big SALE today")

    outcome = stage(post)

    assert outcome == MatchedUsers(frozenset({1}))


def test_keyword_match_stage_dedupes_multiple_matches_for_same_subscriber():
    stage = keyword_match_stage(_StubAutomaton(frozenset({1, 2})))
    post = ChannelPost(message_id=1, text="sale sale discount")

    outcome = stage(post)

    assert outcome == MatchedUsers(frozenset({1, 2}))


def test_keyword_match_stage_no_match_returns_empty_matched_users():
    stage = keyword_match_stage(_StubAutomaton(frozenset()))
    post = ChannelPost(message_id=1, text="nothing relevant")

    outcome = stage(post)

    assert outcome == MatchedUsers(frozenset())


def test_jar_link_stage_broadcasts_when_pattern_present():
    post = ChannelPost(message_id=1, text="Support the cause: https://send.monobank.ua/jar/abc123")

    outcome = jar_link_stage(post)

    assert outcome == BroadcastAll()


def test_jar_link_stage_continues_when_pattern_absent():
    post = ChannelPost(message_id=1, text="Just a regular post about sale")

    outcome = jar_link_stage(post)

    assert outcome == Continue()


def test_pure_number_stage_skips_bare_number_post():
    post = ChannelPost(message_id=1, text="2800")

    outcome = pure_number_stage(post)

    assert outcome == Skip()


def test_pure_number_stage_skips_number_with_common_punctuation():
    post = ChannelPost(message_id=1, text="2,800.00")

    outcome = pure_number_stage(post)

    assert outcome == Skip()


def test_pure_number_stage_continues_when_other_text_present():
    post = ChannelPost(message_id=1, text="2800 UAH raised")

    outcome = pure_number_stage(post)

    assert outcome == Continue()


def test_run_pipeline_short_circuits_on_first_non_continue_stage():
    def always_continue(post):
        return Continue()

    def always_matched(post):
        return MatchedUsers(frozenset({99}))

    def never_called(post):
        raise AssertionError("later stage must not run")

    outcome = run_pipeline(
        [always_continue, always_matched, never_called],
        ChannelPost(message_id=1, text="anything"),
    )

    assert outcome == MatchedUsers(frozenset({99}))


def test_run_pipeline_falls_through_to_last_stage_when_all_continue():
    def always_continue(post):
        return Continue()

    stage = keyword_match_stage(_StubAutomaton(frozenset({5})))

    outcome = run_pipeline([always_continue, stage], ChannelPost(message_id=1, text="sale"))

    assert outcome == MatchedUsers(frozenset({5}))
