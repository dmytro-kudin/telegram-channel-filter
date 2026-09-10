"""Shared aiogram test doubles for command-handler unit tests."""

from dataclasses import dataclass, field


@dataclass
class FakeChat:
    id: int


@dataclass
class FakeMessage:
    chat: FakeChat
    sent: list[str] = field(default_factory=list)

    async def answer(self, text: str, **kwargs) -> None:
        self.sent.append(text)


@dataclass
class FakeCommand:
    args: str | None


def make_message(chat_id: int) -> FakeMessage:
    return FakeMessage(chat=FakeChat(id=chat_id))


@dataclass
class FakeNotifier:
    jobs: list = field(default_factory=list)

    async def enqueue(self, job) -> None:
        self.jobs.append(job)
