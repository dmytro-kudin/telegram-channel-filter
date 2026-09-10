# Quickstart: Button-Driven Subscriber UX & Admin Discoverability

Validation guide for confirming this feature works end-to-end, on top of an
already-running 001 bot (see
`specs/001-channel-keyword-filter/quickstart.md` for initial setup — nothing
here requires new configuration or dependencies). For automated
verification, see the test suite (`tests/unit`) — this guide covers the
manual, real-Telegram-client scenarios.

## Prerequisites

Same as `specs/001-channel-keyword-filter/quickstart.md` — a running bot
with valid `.env` configuration, and at least one non-operator test account
plus the operator account (`ADMIN_CHAT_ID`).

## Validation scenarios

Each scenario below maps to a user story in `spec.md`.

### 1. Navigate without typing (User Story 1)

1. Send `/start`.
2. **Expected**: a persistent row of buttons appears above the text input:
   ➕ Додати слово, 📋 Мої слова, ⏸ Призупинити, ❓ Довідка.
3. Tap ❓ Довідка.
4. **Expected**: same reply as typing `/help` would produce.
5. Type `/list` directly instead of tapping the button.
6. **Expected**: works exactly as before — typing is never disabled.

### 2. Add multiple keywords at once (User Story 2)

1. Tap ➕ Додати слово.
2. **Expected**: bot asks for one or more words, comma-separated.
3. Send `ab, sale, sale, discount` (one too short, one valid, one duplicate
   of the one just added, one more valid).
4. **Expected**: a reply reporting, per word: `ab` too short, `sale` added,
   the second `sale` already exists, `discount` added.
5. Type `/add promo, deal` directly instead of using the guided flow.
6. **Expected**: identical per-word reporting behavior.
7. Add keywords via either path until 20 are saved, then submit one more
   new word in a batch.
8. **Expected**: it's reported as rejected due to the cap, same wording as
   today's single-word limit message.

### 3. Remove a keyword by tapping it (User Story 3)

1. With at least two saved keywords, tap 📋 Мої слова.
2. **Expected**: each keyword appears as its own tappable button.
3. Tap one keyword.
4. **Expected**: message changes to "Delete «word»?" with Yes/Cancel
   buttons.
5. Tap Cancel.
6. **Expected**: returns to the plain list, keyword still present.
7. Tap the same keyword again, then tap Yes.
8. **Expected**: keyword is removed, message confirms, and the refreshed
   list no longer shows it; the other keyword is untouched.
9. Publish a channel post that would have matched the removed keyword.
10. **Expected**: no notification for it.

### 4. Pause and resume via one tap (User Story 4)

1. As an active subscriber, tap ⏸ Призупинити.
2. **Expected**: notifications stop; the menu now shows ▶️ Відновити in
   its place.
3. Publish a post matching one of the subscriber's saved keywords.
4. **Expected**: no notification arrives.
5. Tap ▶️ Відновити.
6. **Expected**: menu shows ⏸ Призупинити again; publishing another
   matching post now delivers a notification, with no keywords re-entered.

### 5. Operator discovers admin commands (User Story 5)

1. As the operator (`ADMIN_CHAT_ID`), tap ❓ Довідка (or type `/help`).
2. **Expected**: reply includes the regular help content plus a section
   listing `/broadcast`, `/stats`, `/block`, `/unblock` and how to use each.
3. As a non-operator subscriber, tap ❓ Довідка.
4. **Expected**: no admin section appears — identical to today's `/help`.
5. As the operator, follow the newly-documented `/broadcast` and `/stats`
   usage.
6. **Expected**: both behave exactly as already validated in
   `specs/001-channel-keyword-filter/quickstart.md` scenario 8 — this
   feature only changes their discoverability, not their behavior.

## Automated test run

```bash
pytest tests/unit
```

All comma-parsing, callback-handler, keyboard-construction, and
operator-vs-subscriber help behavior above is covered by
`tests/unit/test_bot_commands.py`, `tests/unit/test_keyboards.py`, and
`tests/unit/test_db.py` without needing live Telegram credentials; only the
manual scenarios above require a real bot/account.
