from channel_filter import keyboards
from channel_filter.types import Keyword


def test_subscriber_menu_active_shows_pause_button():
    markup = keyboards.subscriber_menu(active=True)

    labels = [button.text for row in markup.keyboard for button in row]
    assert keyboards.PAUSE in labels
    assert keyboards.RESUME not in labels


def test_subscriber_menu_paused_shows_resume_button():
    markup = keyboards.subscriber_menu(active=False)

    labels = [button.text for row in markup.keyboard for button in row]
    assert keyboards.RESUME in labels
    assert keyboards.PAUSE not in labels


def test_keyword_list_keyboard_one_button_per_keyword_with_id_callback_data():
    keywords = [
        Keyword(id=7, chat_id=42, substring="sale"),
        Keyword(id=9, chat_id=42, substring="discount"),
    ]

    markup = keyboards.keyword_list_keyboard(keywords)

    buttons = [button for row in markup.inline_keyboard for button in row]
    assert [(b.text, b.callback_data) for b in buttons] == [
        ("sale", "kw:7"),
        ("discount", "kw:9"),
    ]


def test_delete_confirm_keyboard_yes_cancel_with_id_callback_data():
    markup = keyboards.delete_confirm_keyboard(7)

    buttons = [button for row in markup.inline_keyboard for button in row]
    callback_data = [b.callback_data for b in buttons]
    assert "kwdel:7:y" in callback_data
    assert "kwdel:7:n" in callback_data
