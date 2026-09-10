"""Reply/inline keyboard builders (contracts/button-menu.md, keyword-deletion.md)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from channel_filter.types import Keyword

ADD_KEYWORD = "➕ Додати слово"
MY_KEYWORDS = "📋 Мої слова"
PAUSE = "⏸ Призупинити"
RESUME = "▶️ Відновити"
HELP = "❓ Довідка"

CONFIRM_YES = "Так"
CONFIRM_CANCEL = "Скасувати"


def subscriber_menu(active: bool) -> ReplyKeyboardMarkup:
    pause_resume_label = PAUSE if active else RESUME
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD_KEYWORD), KeyboardButton(text=MY_KEYWORDS)],
            [KeyboardButton(text=pause_resume_label), KeyboardButton(text=HELP)],
        ],
        resize_keyboard=True,
    )


def keyword_list_keyboard(keywords: list[Keyword]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for keyword in keywords:
        builder.button(text=keyword.substring, callback_data=f"kw:{keyword.id}")
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_keyboard(keyword_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=CONFIRM_YES, callback_data=f"kwdel:{keyword_id}:y")
    builder.button(text=CONFIRM_CANCEL, callback_data=f"kwdel:{keyword_id}:n")
    builder.adjust(2)
    return builder.as_markup()
