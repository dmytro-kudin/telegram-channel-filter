"""Unit tests for listener.run_listener_forever()'s build/start/run ordering."""

from channel_filter import listener


class FakeClient:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def start(self) -> None:
        self.events.append("start")

    async def run_until_disconnected(self) -> None:
        self.events.append("run_until_disconnected")


async def test_run_listener_forever_builds_fresh_client_then_starts_then_runs(monkeypatch):
    fake_client = FakeClient()
    build_calls: list[dict] = []

    def fake_build_client(**kwargs):
        build_calls.append(kwargs)
        return fake_client

    monkeypatch.setattr(listener, "build_client", fake_build_client)

    await listener.run_listener_forever(
        api_id=1,
        api_hash="hash",
        source_channel="@chan",
        stages=[],
        conn=object(),
        notifier=object(),
        channel_username="chan",
    )

    assert len(build_calls) == 1
    assert build_calls[0]["api_id"] == 1
    assert build_calls[0]["source_channel"] == "@chan"
    assert fake_client.events == ["start", "run_until_disconnected"]
