"""Unit tests for the supervise() restart-on-failure helper in main.py."""

import asyncio
import contextlib

from channel_filter import main

_REAL_SLEEP = asyncio.sleep


def _install_fast_sleep(monkeypatch, calls: list[float]) -> None:
    async def fake_sleep(delay: float) -> None:
        calls.append(delay)
        await _REAL_SLEEP(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)


async def _pump(n: int = 20) -> None:
    for _ in range(n):
        await _REAL_SLEEP(0)


async def _cancel(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_supervise_restarts_after_delay_when_coroutine_raises(monkeypatch, caplog):
    calls: list[float] = []
    _install_fast_sleep(monkeypatch, calls)
    call_count = 0

    async def failing() -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("boom")

    task = asyncio.create_task(main.supervise("thing", failing))
    await _pump()
    await _cancel(task)

    assert call_count >= 2
    assert calls
    assert all(delay == main.RESTART_DELAY for delay in calls)
    assert any("thing" in record.getMessage() for record in caplog.records)


async def test_supervise_restarts_when_coroutine_returns_cleanly(monkeypatch, caplog):
    calls: list[float] = []
    _install_fast_sleep(monkeypatch, calls)
    call_count = 0

    async def clean() -> None:
        nonlocal call_count
        call_count += 1

    task = asyncio.create_task(main.supervise("other-thing", clean))
    await _pump()
    await _cancel(task)

    assert call_count >= 2
    assert any("other-thing" in record.getMessage() for record in caplog.records)


async def test_supervise_isolates_failures_between_independent_calls(monkeypatch):
    _install_fast_sleep(monkeypatch, [])
    fail_count = 0
    ok_count = 0

    async def always_fails() -> None:
        nonlocal fail_count
        fail_count += 1
        raise RuntimeError("boom")

    async def always_ok() -> None:
        nonlocal ok_count
        ok_count += 1

    failing_task = asyncio.create_task(main.supervise("failing", always_fails))
    ok_task = asyncio.create_task(main.supervise("ok", always_ok))
    await _pump()
    await _cancel(failing_task)
    await _cancel(ok_task)

    assert fail_count >= 2
    assert ok_count >= 2


async def test_supervise_uses_same_delay_on_repeated_consecutive_failures(monkeypatch):
    calls: list[float] = []
    _install_fast_sleep(monkeypatch, calls)

    async def failing() -> None:
        raise RuntimeError("boom")

    task = asyncio.create_task(main.supervise("thing", failing))
    await _pump()
    await _cancel(task)

    assert len(calls) >= 3
    assert set(calls) == {main.RESTART_DELAY}
