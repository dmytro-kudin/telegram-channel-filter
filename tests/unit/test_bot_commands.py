from channel_filter import bot, db, keyboards
from channel_filter import messages as msg
from channel_filter.matcher import AutomatonManager

from .doubles import FakeCallbackQuery, FakeCommand, FakeFSMContext, FakeNotifier, make_message


def _menu_labels(markup):
    return [button.text for row in markup.keyboard for button in row]


async def test_start_handler_registers_subscriber_and_always_replies_success(conn):
    message = make_message(42)

    await bot.start_handler(message, conn=conn, matcher=AutomatonManager(conn))

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.active is True
    assert message.sent == [msg.WELCOME]


async def test_add_handler_success_reply(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    message = make_message(42)

    await bot.add_handler(message, command=FakeCommand(args="sale"), conn=conn, matcher=manager)

    assert message.sent == [msg.add_success("sale")]


async def test_add_handler_too_short_reply(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    message = make_message(42)

    await bot.add_handler(message, command=FakeCommand(args="ab"), conn=conn, matcher=manager)

    assert message.sent == [msg.ADD_TOO_SHORT]


async def test_add_handler_already_exists_reply(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    message = make_message(42)
    await bot.add_handler(message, command=FakeCommand(args="sale"), conn=conn, matcher=manager)

    message2 = make_message(42)
    await bot.add_handler(message2, command=FakeCommand(args="Sale"), conn=conn, matcher=manager)

    assert message2.sent == [msg.ADD_ALREADY_EXISTS]


async def test_add_handler_limit_reached_reply(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    for i in range(20):
        await bot.add_handler(
            make_message(42), command=FakeCommand(args=f"kw{i:02d}"), conn=conn, matcher=manager
        )

    message = make_message(42)
    await bot.add_handler(message, command=FakeCommand(args="onemore"), conn=conn, matcher=manager)

    assert message.sent == [msg.ADD_LIMIT_REACHED]


async def test_list_handler_shows_saved_keywords_as_inline_keyboard(conn):
    # Intentional breaking change for 002-button-driven-ux (contracts/keyword-deletion.md):
    # /list now renders keywords as tappable inline-keyboard buttons, not a plain-text list.
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    await bot.add_handler(
        make_message(42), command=FakeCommand(args="discount"), conn=conn, matcher=manager
    )

    message = make_message(42)
    await bot.list_handler(message, conn=conn)

    assert message.sent == [msg.LIST_HEADER]
    buttons = [b for row in message.markups[-1].inline_keyboard for b in row]
    assert [b.text for b in buttons] == ["sale", "discount"]


async def test_list_handler_empty(conn):
    message = make_message(42)

    await bot.list_handler(message, conn=conn)

    assert message.sent == [msg.LIST_EMPTY]


async def test_remove_handler_success_reply(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)

    message = make_message(42)
    await bot.remove_handler(message, command=FakeCommand(args="sale"), conn=conn, matcher=manager)

    assert message.sent == [msg.remove_success("sale")]


async def test_remove_handler_not_found_reply(conn):
    message = make_message(42)

    await bot.remove_handler(
        message, command=FakeCommand(args="sale"), conn=conn, matcher=AutomatonManager(conn)
    )

    assert message.sent == [msg.REMOVE_NOT_FOUND]


async def test_stop_handler_pauses_and_keeps_keywords(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)

    message = make_message(42)
    await bot.stop_handler(message, conn=conn, matcher=manager)

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.active is False
    assert [kw.substring for kw in await db.list_keywords(conn, 42)] == ["sale"]
    assert message.sent == [msg.STOP_CONFIRMATION]


async def test_start_handler_resumes_paused_subscriber(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    await bot.stop_handler(make_message(42), conn=conn, matcher=manager)

    message = make_message(42)
    await bot.start_handler(message, conn=conn, matcher=manager)

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.active is True
    assert manager.find_matching_chat_ids("sale") == frozenset({42})


async def test_deleteme_handler_removes_subscriber_and_keywords(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)

    message = make_message(42)
    await bot.deleteme_handler(message, conn, manager)

    cursor = await conn.execute("SELECT COUNT(*) FROM subscribers WHERE chat_id = ?", (42,))
    (count,) = await cursor.fetchone()
    assert count == 0
    assert message.sent == [msg.DELETE_CONFIRMATION]
    assert manager.find_matching_chat_ids("sale") == frozenset()


async def test_deleteme_handler_succeeds_for_never_registered_subscriber(conn):
    message = make_message(999)

    await bot.deleteme_handler(message, conn, AutomatonManager(conn))

    assert message.sent == [msg.DELETE_CONFIRMATION]


ADMIN_CHAT_ID = 999


async def _block(message_chat_id, conn, manager, chat_id_arg):
    message = make_message(message_chat_id)
    await bot.block_handler(
        message,
        command=FakeCommand(args=chat_id_arg),
        conn=conn,
        matcher=manager,
        admin_chat_id=ADMIN_CHAT_ID,
    )
    return message


async def _unblock(message_chat_id, conn, manager, chat_id_arg):
    message = make_message(message_chat_id)
    await bot.unblock_handler(
        message,
        command=FakeCommand(args=chat_id_arg),
        conn=conn,
        matcher=manager,
        admin_chat_id=ADMIN_CHAT_ID,
    )
    return message


async def test_block_handler_success_reply(conn):
    manager = AutomatonManager(conn)
    await db.get_or_create_subscriber(conn, 1)

    message = await _block(ADMIN_CHAT_ID, conn, manager, "1")

    assert message.sent == [msg.block_success(1)]
    subscriber = await db.get_or_create_subscriber(conn, 1)
    assert subscriber.blocked is True


async def test_block_handler_not_found_reply(conn):
    manager = AutomatonManager(conn)

    message = await _block(ADMIN_CHAT_ID, conn, manager, "123456")

    assert message.sent == [msg.BLOCK_NOT_FOUND]


async def test_block_handler_refused_for_non_operator(conn):
    manager = AutomatonManager(conn)
    await db.get_or_create_subscriber(conn, 1)

    message = await _block(1, conn, manager, "1")

    assert message.sent == [msg.NOT_AUTHORIZED]
    subscriber = await db.get_or_create_subscriber(conn, 1)
    assert subscriber.blocked is False


async def test_unblock_handler_success_reply_restores_prior_active(conn):
    manager = AutomatonManager(conn)
    await db.get_or_create_subscriber(conn, 1)
    await db.set_active(conn, 1, False)
    await db.set_blocked(conn, 1, True)

    message = await _unblock(ADMIN_CHAT_ID, conn, manager, "1")

    assert message.sent == [msg.unblock_success(1)]
    subscriber = await db.get_or_create_subscriber(conn, 1)
    assert subscriber.blocked is False
    assert subscriber.active is False


async def test_unblock_handler_not_found_reply(conn):
    manager = AutomatonManager(conn)
    await db.get_or_create_subscriber(conn, 1)

    message = await _unblock(ADMIN_CHAT_ID, conn, manager, "1")

    assert message.sent == [msg.UNBLOCK_NOT_FOUND]


async def test_blocked_subscriber_commands_are_refused(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await db.get_or_create_subscriber(conn, 1)
    await db.set_blocked(conn, 1, True)

    start_message = make_message(1)
    await bot.start_handler(start_message, conn=conn, matcher=manager)
    assert start_message.sent == [msg.BLOCKED]

    add_message = make_message(1)
    await bot.add_handler(add_message, command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    assert add_message.sent == [msg.BLOCKED]

    remove_message = make_message(1)
    await bot.remove_handler(
        remove_message, command=FakeCommand(args="sale"), conn=conn, matcher=manager
    )
    assert remove_message.sent == [msg.BLOCKED]

    list_message = make_message(1)
    await bot.list_handler(list_message, conn=conn)
    assert list_message.sent == [msg.BLOCKED]

    stop_message = make_message(1)
    await bot.stop_handler(stop_message, conn=conn, matcher=manager)
    assert stop_message.sent == [msg.BLOCKED]


async def test_broadcast_handler_enqueues_one_job_per_eligible_subscriber(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.get_or_create_subscriber(conn, 2)
    await db.set_active(conn, 2, False)
    await db.get_or_create_subscriber(conn, 3)
    await db.set_blocked(conn, 3, True)
    notifier = FakeNotifier()

    message = make_message(ADMIN_CHAT_ID)
    await bot.broadcast_handler(
        message,
        command=FakeCommand(args="Тестове повідомлення"),
        conn=conn,
        notifier=notifier,
        admin_chat_id=ADMIN_CHAT_ID,
    )

    assert {job.chat_id for job in notifier.jobs} == {1}
    for job in notifier.jobs:
        assert job.text == "Тестове повідомлення"
        assert job.message_id is None
    assert message.sent == [msg.broadcast_queued(1)]


async def test_broadcast_handler_refused_for_non_operator(conn):
    await db.get_or_create_subscriber(conn, 1)
    notifier = FakeNotifier()

    message = make_message(1)
    await bot.broadcast_handler(
        message,
        command=FakeCommand(args="hi"),
        conn=conn,
        notifier=notifier,
        admin_chat_id=ADMIN_CHAT_ID,
    )

    assert message.sent == [msg.NOT_AUTHORIZED]
    assert notifier.jobs == []


async def test_stats_handler_shows_breakdown(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.get_or_create_subscriber(conn, 2)
    await db.set_active(conn, 2, False)

    message = make_message(ADMIN_CHAT_ID)
    await bot.stats_handler(message, conn=conn, admin_chat_id=ADMIN_CHAT_ID)

    assert message.sent == [msg.stats(total=2, active=1, paused=1, blocked=0)]


async def test_stats_handler_refused_for_non_operator(conn):
    message = make_message(1)

    await bot.stats_handler(message, conn=conn, admin_chat_id=ADMIN_CHAT_ID)

    assert message.sent == [msg.NOT_AUTHORIZED]


async def test_help_handler_lists_subscriber_commands_only(conn):
    message = make_message(42)

    await bot.help_handler(message, conn=conn, admin_chat_id=ADMIN_CHAT_ID)

    assert message.sent == [msg.HELP]
    for admin_command in ("/broadcast", "/stats", "/block", "/unblock"):
        assert admin_command not in msg.HELP


async def test_help_handler_appends_admin_section_for_operator(conn):
    message = make_message(ADMIN_CHAT_ID)

    await bot.help_handler(message, conn=conn, admin_chat_id=ADMIN_CHAT_ID)

    (reply,) = message.sent
    assert reply.startswith(msg.HELP)
    for admin_command in ("/broadcast", "/stats", "/block", "/unblock"):
        assert admin_command in reply


async def test_start_handler_attaches_active_menu(conn):
    message = make_message(42)

    await bot.start_handler(message, conn=conn, matcher=AutomatonManager(conn))

    assert message.markups[-1] is not None
    assert keyboards.PAUSE in _menu_labels(message.markups[-1])
    assert keyboards.RESUME not in _menu_labels(message.markups[-1])


async def test_stop_handler_attaches_paused_menu(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.start_handler(make_message(42), conn=conn, matcher=manager)

    message = make_message(42)
    await bot.stop_handler(message, conn=conn, matcher=manager)

    assert keyboards.RESUME in _menu_labels(message.markups[-1])
    assert keyboards.PAUSE not in _menu_labels(message.markups[-1])


async def test_list_handler_attaches_menu(conn):
    message = make_message(42)

    await bot.list_handler(message, conn=conn)

    assert message.markups[-1] is not None


async def test_add_handler_attaches_menu(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    message = make_message(42)

    await bot.add_handler(message, command=FakeCommand(args="sale"), conn=conn, matcher=manager)

    assert message.markups[-1] is not None


async def test_remove_handler_attaches_menu(conn):
    message = make_message(42)

    await bot.remove_handler(
        message, command=FakeCommand(args="sale"), conn=conn, matcher=AutomatonManager(conn)
    )

    assert message.markups[-1] is not None


async def test_help_handler_attaches_menu(conn):
    message = make_message(42)

    await bot.help_handler(message, conn=conn, admin_chat_id=ADMIN_CHAT_ID)

    assert message.markups[-1] is not None


async def test_deleteme_handler_attaches_menu_without_recreating_subscriber(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)

    message = make_message(42)
    await bot.deleteme_handler(message, conn, manager)

    assert message.markups[-1] is not None
    cursor = await conn.execute("SELECT COUNT(*) FROM subscribers WHERE chat_id = ?", (42,))
    (count,) = await cursor.fetchone()
    assert count == 0


def test_parse_keyword_batch_splits_strips_and_drops_empty():
    assert bot._parse_keyword_batch("sale, discount ,  promo") == ["sale", "discount", "promo"]
    assert bot._parse_keyword_batch("ab,,sale") == ["ab", "sale"]


def test_parse_keyword_batch_blank_or_comma_only_falls_back_to_single_empty_entry():
    assert bot._parse_keyword_batch("") == [""]
    assert bot._parse_keyword_batch(",,,") == [""]
    assert bot._parse_keyword_batch("   ") == [""]


async def test_add_handler_multiple_comma_separated_words_reports_each_outcome(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    message = make_message(42)

    await bot.add_handler(
        message, command=FakeCommand(args="ab, sale, sale, discount"), conn=conn, matcher=manager
    )

    assert message.sent == [
        "\n".join(
            [
                msg.ADD_TOO_SHORT,
                msg.add_success("sale"),
                msg.ADD_ALREADY_EXISTS,
                msg.add_success("discount"),
            ]
        )
    ]


async def test_add_handler_batch_reports_limit_reached_for_words_after_cap(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    for i in range(19):
        await bot.add_handler(
            make_message(42), command=FakeCommand(args=f"kw{i:02d}"), conn=conn, matcher=manager
        )

    message = make_message(42)
    await bot.add_handler(
        message, command=FakeCommand(args="last, over1, over2"), conn=conn, matcher=manager
    )

    assert message.sent == [
        "\n".join([msg.add_success("last"), msg.ADD_LIMIT_REACHED, msg.ADD_LIMIT_REACHED])
    ]


async def test_add_prompt_handler_asks_for_words_and_sets_waiting_state(conn):
    message = make_message(42)
    state = FakeFSMContext()

    await bot.add_prompt_handler(message, conn=conn, state=state)

    assert message.sent == [msg.ADD_PROMPT]
    assert state.state == bot.AddKeywords.waiting


async def test_guided_add_input_handler_parses_and_clears_state(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    state = FakeFSMContext(state=bot.AddKeywords.waiting)
    message = make_message(42)
    message.text = "ab, sale"

    await bot.guided_add_input_handler(message, conn=conn, matcher=manager, state=state)

    assert message.sent == ["\n".join([msg.ADD_TOO_SHORT, msg.add_success("sale")])]
    assert state.state is None
    assert manager.find_matching_chat_ids("sale") == frozenset({42})


async def test_my_keywords_button_handler_clears_pending_add_state(conn):
    state = FakeFSMContext(state=bot.AddKeywords.waiting)
    message = make_message(42)

    await bot.my_keywords_button_handler(message, conn=conn, state=state)

    assert state.state is None
    assert message.sent == [msg.LIST_EMPTY]


async def test_help_button_handler_clears_pending_add_state(conn):
    state = FakeFSMContext(state=bot.AddKeywords.waiting)
    message = make_message(42)

    await bot.help_button_handler(message, conn=conn, state=state, admin_chat_id=ADMIN_CHAT_ID)

    assert state.state is None
    assert message.sent == [msg.HELP]


async def test_keyword_tap_handler_shows_confirm_prompt(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    (keyword,) = await db.list_keywords(conn, 42)

    callback_message = make_message(42)
    callback = FakeCallbackQuery(data=f"kw:{keyword.id}", message=callback_message)
    await bot.keyword_tap_handler(callback, conn=conn)

    text, markup = callback_message.edits[-1]
    assert text == msg.delete_confirm_prompt("sale")
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert {b.callback_data for b in buttons} == {f"kwdel:{keyword.id}:y", f"kwdel:{keyword.id}:n"}
    assert callback.answered


async def test_keyword_tap_handler_stale_tap_shows_toast_and_refreshes(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    (keyword,) = await db.list_keywords(conn, 42)
    await db.remove_keyword_by_id(conn, 42, keyword.id)

    callback_message = make_message(42)
    callback = FakeCallbackQuery(data=f"kw:{keyword.id}", message=callback_message)
    await bot.keyword_tap_handler(callback, conn=conn)

    assert callback.answered[-1][0] == msg.KEYWORD_ALREADY_REMOVED
    text, markup = callback_message.edits[-1]
    assert text == msg.LIST_EMPTY
    assert markup is None


async def test_keyword_delete_confirm_yes_deletes_and_refreshes_list(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    await bot.add_handler(
        make_message(42), command=FakeCommand(args="discount"), conn=conn, matcher=manager
    )
    keywords = await db.list_keywords(conn, 42)
    target = next(kw for kw in keywords if kw.substring == "sale")

    callback_message = make_message(42)
    callback = FakeCallbackQuery(data=f"kwdel:{target.id}:y", message=callback_message)
    await bot.keyword_delete_confirm_handler(callback, conn=conn, matcher=manager)

    remaining = await db.list_keywords(conn, 42)
    assert [kw.substring for kw in remaining] == ["discount"]
    assert manager.find_matching_chat_ids("sale") == frozenset()
    text, markup = callback_message.edits[-1]
    assert msg.remove_success("sale") in text
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert [b.text for b in buttons] == ["discount"]
    assert callback.answered


async def test_keyword_delete_confirm_yes_last_keyword_shows_empty_state(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    (keyword,) = await db.list_keywords(conn, 42)

    callback_message = make_message(42)
    callback = FakeCallbackQuery(data=f"kwdel:{keyword.id}:y", message=callback_message)
    await bot.keyword_delete_confirm_handler(callback, conn=conn, matcher=manager)

    text, markup = callback_message.edits[-1]
    assert msg.LIST_EMPTY in text
    assert markup is None


async def test_keyword_delete_confirm_cancel_reverts_to_list(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    (keyword,) = await db.list_keywords(conn, 42)

    callback_message = make_message(42)
    callback = FakeCallbackQuery(data=f"kwdel:{keyword.id}:n", message=callback_message)
    await bot.keyword_delete_confirm_handler(callback, conn=conn, matcher=manager)

    remaining = await db.list_keywords(conn, 42)
    assert [kw.substring for kw in remaining] == ["sale"]
    text, markup = callback_message.edits[-1]
    assert text == msg.LIST_HEADER
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert [b.text for b in buttons] == ["sale"]
    assert callback.answered


async def test_keyword_delete_confirm_stale_shows_toast_and_refreshes(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.add_handler(make_message(42), command=FakeCommand(args="sale"), conn=conn, matcher=manager)
    (keyword,) = await db.list_keywords(conn, 42)
    await db.remove_keyword_by_id(conn, 42, keyword.id)

    callback_message = make_message(42)
    callback = FakeCallbackQuery(data=f"kwdel:{keyword.id}:y", message=callback_message)
    await bot.keyword_delete_confirm_handler(callback, conn=conn, matcher=manager)

    assert callback.answered[-1][0] == msg.KEYWORD_ALREADY_REMOVED
    text, markup = callback_message.edits[-1]
    assert text == msg.LIST_EMPTY
    assert markup is None


async def test_pause_button_handler_pauses_and_clears_pending_add_state(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.start_handler(make_message(42), conn=conn, matcher=manager)
    state = FakeFSMContext(state=bot.AddKeywords.waiting)

    message = make_message(42)
    await bot.pause_button_handler(message, conn=conn, matcher=manager, state=state)

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.active is False
    assert state.state is None
    assert message.sent == [msg.STOP_CONFIRMATION]


async def test_resume_button_handler_resumes_and_clears_pending_add_state(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await bot.start_handler(make_message(42), conn=conn, matcher=manager)
    await bot.stop_handler(make_message(42), conn=conn, matcher=manager)
    state = FakeFSMContext(state=bot.AddKeywords.waiting)

    message = make_message(42)
    await bot.resume_button_handler(message, conn=conn, matcher=manager, state=state)

    subscriber = await db.get_or_create_subscriber(conn, 42)
    assert subscriber.active is True
    assert state.state is None
    assert message.sent == [msg.WELCOME]


async def test_blocked_subscriber_can_still_deleteme(conn):
    manager = AutomatonManager(conn)
    await manager.build()
    await db.get_or_create_subscriber(conn, 1)
    await db.set_blocked(conn, 1, True)

    message = make_message(1)
    await bot.deleteme_handler(message, conn, manager)

    assert message.sent == [msg.DELETE_CONFIRMATION]
