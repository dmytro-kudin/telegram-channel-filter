from channel_filter import db
from channel_filter.matcher import AutomatonManager


async def test_automaton_manager_builds_from_eligible_subscribers_keywords(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.add_keyword(conn, 1, "sale")

    manager = AutomatonManager(conn)
    await manager.build()

    matches = manager.find_matching_chat_ids("big sale today")
    assert matches == frozenset({1})


async def test_automaton_manager_excludes_paused_subscribers(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.add_keyword(conn, 1, "sale")
    await conn.execute("UPDATE subscribers SET active = 0 WHERE chat_id = 1")
    await conn.commit()

    manager = AutomatonManager(conn)
    await manager.build()

    matches = manager.find_matching_chat_ids("big sale today")
    assert matches == frozenset()


async def test_automaton_manager_excludes_blocked_subscribers(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.add_keyword(conn, 1, "sale")
    await conn.execute("UPDATE subscribers SET blocked = 1 WHERE chat_id = 1")
    await conn.commit()

    manager = AutomatonManager(conn)
    await manager.build()

    matches = manager.find_matching_chat_ids("big sale today")
    assert matches == frozenset()


async def test_automaton_manager_rebuild_picks_up_new_keyword(conn):
    await db.get_or_create_subscriber(conn, 1)
    manager = AutomatonManager(conn)
    await manager.build()
    assert manager.find_matching_chat_ids("sale today") == frozenset()

    await db.add_keyword(conn, 1, "sale")
    await manager.rebuild()

    assert manager.find_matching_chat_ids("sale today") == frozenset({1})


async def test_automaton_manager_rebuild_excludes_after_set_active_false(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.add_keyword(conn, 1, "sale")
    manager = AutomatonManager(conn)
    await manager.build()
    assert manager.find_matching_chat_ids("sale today") == frozenset({1})

    await db.set_active(conn, 1, False)
    await manager.rebuild()

    assert manager.find_matching_chat_ids("sale today") == frozenset()


async def test_automaton_manager_no_match_returns_empty(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.add_keyword(conn, 1, "sale")

    manager = AutomatonManager(conn)
    await manager.build()

    assert manager.find_matching_chat_ids("nothing relevant here") == frozenset()
