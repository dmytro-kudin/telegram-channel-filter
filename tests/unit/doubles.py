"""Shared aiogram test doubles for command-handler unit tests."""

from dataclasses import dataclass, field


@dataclass
class FakeChat:
    id: int


@dataclass
class FakeMessage:
    chat: FakeChat
    sent: list[str] = field(default_factory=list)
    markups: list = field(default_factory=list)
    edits: list[tuple[str, object]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup=None, **kwargs) -> None:
        self.sent.append(text)
        self.markups.append(reply_markup)

    async def edit_text(self, text: str, reply_markup=None, **kwargs) -> None:
        self.edits.append((text, reply_markup))


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


@dataclass
class FakeFSMContext:
    state: object | None = None

    async def set_state(self, state) -> None:
        self.state = state

    async def get_state(self):
        return self.state

    async def clear(self) -> None:
        self.state = None


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage
    answered: list[tuple[str | None, bool]] = field(default_factory=list)

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answered.append((text, show_alert))
