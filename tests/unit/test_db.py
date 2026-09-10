from channel_filter import db
from channel_filter.messages import MAX_KEYWORDS_PER_SUBSCRIBER
from channel_filter.types import Added, AlreadyExists, LimitReached, NotFound, Removed, TooShort


async def test_get_or_create_subscriber_registers_new_subscriber_as_active(conn):
    subscriber = await db.get_or_create_subscriber(conn, 42)

    assert subscriber.chat_id == 42
    assert subscriber.active is True
    assert subscriber.blocked is False


async def test_get_or_create_subscriber_returns_existing_subscriber(conn):
    first = await db.get_or_create_subscriber(conn, 42)
    second = await db.get_or_create_subscriber(conn, 42)

    assert first == second


async def test_add_keyword_valid_add_succeeds(conn):
    await db.get_or_create_subscriber(conn, 42)

    outcome = await db.add_keyword(conn, 42, "sale")

    assert outcome == Added()


async def test_add_keyword_rejects_short_keyword(conn):
    await db.get_or_create_subscriber(conn, 42)

    outcome = await db.add_keyword(conn, 42, "ab")

    assert outcome == TooShort()


async def test_list_keywords_returns_all_saved_keywords(conn):
    await db.get_or_create_subscriber(conn, 42)
    await db.add_keyword(conn, 42, "sale")
    await db.add_keyword(conn, 42, "discount")

    keywords = await db.list_keywords(conn, 42)

    assert sorted(keywords) == ["discount", "sale"]


async def test_list_keywords_empty_for_new_subscriber(conn):
    await db.get_or_create_subscriber(conn, 42)

    keywords = await db.list_keywords(conn, 42)

    assert keywords == []


async def test_remove_keyword_success(conn):
    await db.get_or_create_subscriber(conn, 42)
    await db.add_keyword(conn, 42, "sale")

    outcome = await db.remove_keyword(conn, 42, "sale")

    assert outcome == Removed()
    assert await db.list_keywords(conn, 42) == []


async def test_remove_keyword_not_found(conn):
    await db.get_or_create_subscriber(conn, 42)

    outcome = await db.remove_keyword(conn, 42, "sale")

    assert outcome == NotFound()


async def test_add_keyword_case_insensitive_dedup_is_noop(conn):
    await db.get_or_create_subscriber(conn, 42)
    await db.add_keyword(conn, 42, "Sale")

    outcome = await db.add_keyword(conn, 42, "sale")

    assert outcome == AlreadyExists()
    assert await db.list_keywords(conn, 42) == ["sale"]


async def test_add_keyword_rejects_over_limit(conn):
    await db.get_or_create_subscriber(conn, 42)
    for i in range(MAX_KEYWORDS_PER_SUBSCRIBER):
        outcome = await db.add_keyword(conn, 42, f"keyword{i:02d}")
        assert outcome == Added()

    outcome = await db.add_keyword(conn, 42, "onemore")

    assert outcome == LimitReached()


async def test_set_active_pauses_subscriber(conn):
    await db.get_or_create_subscriber(conn, 42)

    await db.set_active(conn, 42, False)

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.active is False


async def test_set_active_resumes_subscriber(conn):
    await db.get_or_create_subscriber(conn, 42)
    await db.set_active(conn, 42, False)

    await db.set_active(conn, 42, True)

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.active is True


async def test_delete_subscriber_cascades_to_keywords(conn):
    await db.get_or_create_subscriber(conn, 42)
    await db.add_keyword(conn, 42, "sale")
    await db.add_keyword(conn, 42, "discount")

    await db.delete_subscriber(conn, 42)

    cursor = await conn.execute("SELECT COUNT(*) FROM subscribers WHERE chat_id = ?", (42,))
    (subscriber_count,) = await cursor.fetchone()
    assert subscriber_count == 0
    cursor = await conn.execute("SELECT COUNT(*) FROM keywords WHERE chat_id = ?", (42,))
    (keyword_count,) = await cursor.fetchone()
    assert keyword_count == 0


async def test_delete_subscriber_is_safe_noop_when_never_registered(conn):
    await db.delete_subscriber(conn, 999)

    cursor = await conn.execute("SELECT COUNT(*) FROM subscribers WHERE chat_id = ?", (999,))
    (count,) = await cursor.fetchone()
    assert count == 0


async def test_set_blocked_blocks_subscriber_and_preserves_active(conn):
    await db.get_or_create_subscriber(conn, 42)
    await db.set_active(conn, 42, False)

    await db.set_blocked(conn, 42, True)

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.blocked is True
    assert subscriber.active is False


async def test_set_blocked_unblock_restores_prior_active_value_unchanged(conn):
    await db.get_or_create_subscriber(conn, 42)
    await db.set_active(conn, 42, True)
    await db.set_blocked(conn, 42, True)

    await db.set_blocked(conn, 42, False)

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.blocked is False
    assert subscriber.active is True


async def test_get_subscriber_stats_breakdown(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.get_or_create_subscriber(conn, 2)
    await db.set_active(conn, 2, False)
    await db.get_or_create_subscriber(conn, 3)
    await db.set_blocked(conn, 3, True)

    stats = await db.get_subscriber_stats(conn)

    assert stats.total == 3
    assert stats.active == 1
    assert stats.paused == 1
    assert stats.blocked == 1


async def test_subscriber_and_keyword_state_survives_reconnect(tmp_path):
    db_path = str(tmp_path / "restart_survival.db")

    conn1 = await db.connect(db_path)
    await db.get_or_create_subscriber(conn1, 42)
    await db.add_keyword(conn1, 42, "sale")
    await db.set_active(conn1, 42, False)
    await db.set_blocked(conn1, 42, True)
    await conn1.close()

    conn2 = await db.connect(db_path)
    subscriber = await db.get_or_create_subscriber(conn2, 42)
    keywords = await db.list_keywords(conn2, 42)
    await conn2.close()

    assert subscriber.active is False
    assert subscriber.blocked is True
    assert keywords == ["sale"]
