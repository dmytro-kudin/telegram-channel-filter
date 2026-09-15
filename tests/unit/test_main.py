"""Unit tests for main.py's logging setup, supervisor wiring, and top-level safety net."""

import logging
import os

from channel_filter import main


def test_configure_logging_sets_root_level_to_info():
    logging.getLogger().setLevel(logging.WARNING)

    main.configure_logging()

    assert logging.getLogger().getEffectiveLevel() == logging.INFO


class _FakeDispatcher:
    def __init__(self) -> None:
        self.polling_calls: list[object] = []

    async def start_polling(self, bot: object) -> None:
        self.polling_calls.append(bot)


class _FakeNotifierLike:
    def __init__(self) -> None:
        self.run_calls: list[object] = []

    async def run(self, bot: object) -> None:
        self.run_calls.append(bot)


async def test_build_supervised_tasks_wires_three_supervised_components(monkeypatch):
    recorded: list[tuple[str, object]] = []

    def fake_supervise(name, coro_factory):
        recorded.append((name, coro_factory))
        return None

    monkeypatch.setattr(main, "supervise", fake_supervise)

    listener_calls: list[dict] = []

    async def fake_run_listener_forever(**kwargs):
        listener_calls.append(kwargs)

    monkeypatch.setattr(main, "run_listener_forever", fake_run_listener_forever, raising=False)

    dp = _FakeDispatcher()
    notifier = _FakeNotifierLike()
    aiogram_bot = object()

    tasks = main.build_supervised_tasks(
        api_id=1,
        api_hash="hash",
        source_channel="@chan",
        stages=[],
        conn=object(),
        notifier=notifier,
        channel_username="chan",
        dp=dp,
        aiogram_bot=aiogram_bot,
    )

    assert len(tasks) == 3
    names = [name for name, _ in recorded]
    assert names == ["telethon-listener", "bot-polling", "notifier"]

    factories_by_name = dict(recorded)

    await factories_by_name["telethon-listener"]()
    assert len(listener_calls) == 1
    assert listener_calls[0]["api_id"] == 1
    assert listener_calls[0]["source_channel"] == "@chan"

    await factories_by_name["bot-polling"]()
    assert dp.polling_calls == [aiogram_bot]

    await factories_by_name["notifier"]()
    assert notifier.run_calls == [aiogram_bot]


def test_run_forces_process_exit_when_main_raises(monkeypatch, caplog):
    async def fake_main() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "main", fake_main)

    events: list[object] = []
    monkeypatch.setattr(logging, "shutdown", lambda: events.append("shutdown"))
    monkeypatch.setattr(os, "_exit", lambda code: events.append(("exit", code)))

    with caplog.at_level(logging.CRITICAL):
        main.run()

    assert events == ["shutdown", ("exit", 1)]
    assert any(record.levelname == "CRITICAL" for record in caplog.records)
