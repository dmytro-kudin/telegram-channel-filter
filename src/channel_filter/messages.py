"""Single source of all Ukrainian bot-reply text (FR-025)."""

from __future__ import annotations

MIN_KEYWORD_LENGTH = 3
MAX_KEYWORDS_PER_SUBSCRIBER = 20

WELCOME = (
    "Вітаємо! Ви підписані на сповіщення про нові пости в каналі.\n"
    "Додайте ключове слово командою /add <слово>, щоб отримувати сповіщення, "
    "коли воно з'явиться в новому пості.\n"
    "Використайте /help, щоб побачити всі команди."
)

HELP = (
    "Доступні команди:\n"
    "/start — почати або відновити отримання сповіщень\n"
    "/add <слово> — додати ключове слово (мінімум 3 символи)\n"
    "/remove <слово> — видалити ключове слово\n"
    "/list — показати всі збережені ключові слова\n"
    "/stop — призупинити сповіщення (ключові слова зберігаються)\n"
    "/deleteme — назавжди видалити свій акаунт і всі ключові слова\n"
    "/help — показати це повідомлення"
)

ADD_TOO_SHORT = f"Ключове слово має містити щонайменше {MIN_KEYWORD_LENGTH} символи."
ADD_LIMIT_REACHED = (
    f"Ви досягли ліміту в {MAX_KEYWORDS_PER_SUBSCRIBER} ключових слів. "
    "Видаліть якесь, щоб додати нове."
)
ADD_ALREADY_EXISTS = "Це ключове слово вже збережено у вашому списку."


def add_success(keyword: str) -> str:
    return f"Ключове слово «{keyword}» додано."


REMOVE_NOT_FOUND = "Таке ключове слово не знайдено у вашому списку."


def remove_success(keyword: str) -> str:
    return f"Ключове слово «{keyword}» видалено."


LIST_EMPTY = "У вас поки немає збережених ключових слів."


def list_keywords(keywords: list[str]) -> str:
    lines = "\n".join(f"— {kw}" for kw in keywords)
    return f"Ваші ключові слова:\n{lines}"


STOP_CONFIRMATION = (
    "Сповіщення призупинено. Ваші ключові слова збережено — надішліть /start, "
    "щоб відновити отримання сповіщень."
)

DELETE_CONFIRMATION = (
    "Ваш акаунт і всі ключові слова назавжди видалено. "
    "Наступний /start почне все з чистого аркуша."
)

BLOCKED = "Вас заблоковано оператором. Ви не можете користуватися цим ботом."

NOT_AUTHORIZED = "Ця команда доступна лише оператору."

VIEW_ORIGINAL = "🔗 Переглянути оригінал"


def broadcast_queued(count: int) -> str:
    return f"Розсилку поставлено в чергу для {count} підписників."


def stats(total: int, active: int, paused: int, blocked: int) -> str:
    return (
        f"Усього підписників: {total}\n"
        f"Активні: {active}\n"
        f"На паузі: {paused}\n"
        f"Заблоковані: {blocked}"
    )


BLOCK_NOT_FOUND = "Підписника з таким chat_id не знайдено."


def block_success(chat_id: int) -> str:
    return f"Підписника {chat_id} заблоковано."


UNBLOCK_NOT_FOUND = "Підписника з таким chat_id не знайдено серед заблокованих."


def unblock_success(chat_id: int) -> str:
    return f"Підписника {chat_id} розблоковано. Його попередній стан відновлено."
