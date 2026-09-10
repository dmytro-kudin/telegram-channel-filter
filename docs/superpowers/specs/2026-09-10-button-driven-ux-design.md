# Design: Button-Driven Subscriber UX & Admin Discoverability

**Created**: 2026-09-10

**Status**: Approved for spec

**Builds on**: `specs/001-channel-keyword-filter` (fully implemented). This is a
new feature layered on top of it, not a revision of it.

## Problem

The bot today is entirely typed-command driven (`/add`, `/remove`, `/list`,
`/stop`, `/deleteme`, `/help`, plus operator-only `/broadcast`, `/stats`,
`/block`, `/unblock`). Two problems surfaced from real usage:

1. Typing commands (and remembering their names/syntax) is friction for
   ordinary subscribers, especially for actions like removing a specific
   keyword (must retype the exact word) or adding several keywords in one go.
2. The operator did not know `/broadcast` and `/stats` existed and how to use
   them — they already work (`bot.py:139-158`) but are deliberately excluded
   from `/help` for non-operators (per `contracts/bot-commands.md`'s "admin
   commands ... not advertised to non-operator subscribers"), and there was no
   equivalent surfacing for the operator themselves.

## Scope

**In scope:**
- A persistent reply keyboard (Telegram's fixed button row above the text
  input) as the primary way to trigger: add a keyword, view/manage keywords,
  pause/resume, help, delete account.
- A guided "add keyword" flow: tapping the button prompts for word(s); the
  next plain-text message is parsed as one or more comma-separated keywords.
- Comma-separated multi-keyword support in `/add` itself (typed and guided
  paths share one parser).
- Inline-keyboard keyword deletion: tap a keyword from the list, confirm
  Yes/Cancel, it's removed.
- Operator-aware `/help`: the operator sees an additional section documenting
  `/broadcast`, `/stats`, `/block`, `/unblock`; non-operators see unchanged
  help text.

**Out of scope (explicitly deferred):**
- Admin-only buttons on a reply keyboard (operator keeps using typed
  `/broadcast`, `/stats`, `/block`, `/unblock`).
- A subscriber-picker UI for `/block`/`/unblock` (they stay typed with a
  numeric `chat_id` argument).
- Any change to matching/notification/pipeline behavior — this is purely a
  subscriber/operator interaction-layer feature.

**Explicitly preserved:** every existing typed command keeps working exactly
as documented in `contracts/bot-commands.md` and `contracts/admin-commands.md`
(with one narrow addition: `/add` gains comma-splitting). Buttons are an
additive interface, not a replacement — this keeps prior contracts and tests
valid rather than rewriting them.

## User-Facing Behavior

### Persistent reply keyboard

Sent with every bot reply to a subscriber (so it's always current), laid out
as:

```
➕ Додати слово   |   📋 Мої слова
⏸ Призупинити / ▶️ Відновити   |   ❓ Довідка
🗑 Видалити акаунт
```

The pause/resume button's label reflects the subscriber's current `active`
state (mirrors `/stop` / `/start` semantics — tapping it calls the same
handler logic as the corresponding typed command). Tapping any button is
equivalent to sending the matching typed command; no new business behavior,
only a new entry point.

### Guided add flow

1. Subscriber taps ➕ Додати слово.
2. Bot replies asking for one or more words, comma-separated, and enters a
   transient "awaiting keyword input" state for that chat (aiogram FSM,
   in-memory — acceptable to lose on restart, unlike persisted keyword data).
3. Subscriber's next plain-text message is split on commas; each piece is
   trimmed and lowercased, then run through the existing `db.add_keyword`
   validation (min length 3, per-subscriber cap 20, dedup) — unchanged rules,
   applied once per word.
4. Bot replies with one line per word: added / already existed / too short /
   limit reached (once the cap is hit, remaining words in the same batch also
   report limit-reached rather than silently stopping).
5. State clears after the reply, whether all words succeeded or not.

If anything else arrives while "awaiting keyword input" (e.g. a menu button
tap instead of a plain-text word list), the flow is cancelled explicitly and
that input is handled normally by its own handler — never merged into a
partially-typed keyword.

Typed `/add word1, word2, word3` uses the identical comma-splitting/validation
helper and reply format, so the two entry points behave identically.

### Keyword deletion via inline buttons

1. Subscriber taps 📋 Мої слова (or types `/list`).
2. If they have no keywords: same empty-state message as today.
3. If they have keywords: sent as an inline keyboard, one button per keyword
   (its text), each carrying that keyword's numeric id in `callback_data`.
4. Tapping a keyword edits the message to `Видалити «word»?` with Yes/Cancel
   inline buttons.
5. **Yes**: deletes the row, triggers an automaton rebuild (same as
   `/remove`), edits the message to confirm, and shows the refreshed list (or
   the empty-state message if none remain).
6. **Cancel**: reverts the message to the plain list view, no deletion.
7. A tap on a keyword that's already gone (e.g. deleted from a concurrent
   second tap, or via typed `/remove`) answers the callback with a small
   "already removed" toast and refreshes the list — never an unhandled error.

Typed `/remove <word>` is unchanged.

### Operator-aware help

`/help` (and the ❓ Довідка button, same handler) checks the sender's
`chat_id` against `admin_chat_id`. Non-operators get exactly today's
`HELP` text. The operator gets that same text plus an appended section:

```
Команди оператора:
/broadcast <текст> — розіслати повідомлення всім активним підписникам
/stats — переглянути статистику підписників
/block <chat_id> — заблокувати підписника
/unblock <chat_id> — розблокувати підписника
```

This does not change `set_my_commands` (the native Telegram command menu
stays subscriber-only, per the existing contract) — it only changes what
`/help` prints for the operator specifically.

## Technical Design

### New module: `keyboards.py`

Isolates keyboard construction from handler logic (mirrors how
`notifier.py` already builds its own inline "view original" keyboard):

- `subscriber_menu(active: bool) -> ReplyKeyboardMarkup` — the persistent
  menu, pause/resume label chosen from `active`.
- `keyword_list_keyboard(keywords: list[Keyword]) -> InlineKeyboardMarkup`
  — one button per keyword, `callback_data` encodes the keyword id.
- `delete_confirm_keyboard(keyword_id: int) -> InlineKeyboardMarkup` —
  Yes/Cancel, `callback_data` encodes the id and the action.

### `db.py` changes

- `list_keywords` returns `list[Keyword]` (id + substring) instead of
  `list[str]`. Every existing caller (`list_handler`, tests) updates to read
  `.substring`.
- New `remove_keyword_by_id(conn, chat_id, keyword_id) -> RemoveKeywordOutcome`
  alongside the existing text-based `remove_keyword` (typed `/remove` keeps
  using the text-based lookup; the callback flow uses the id it already has,
  avoiding a re-lookup by text and any ambiguity from re-normalization).

### `bot.py` changes

- New `AddKeywords` FSM `StatesGroup` with a single `waiting` state.
- New handlers, registered on the existing `Router`:
  - Reply-keyboard button handlers (`Message`, filtered by exact button
    text) for ➕/📋/⏸/▶️/❓/🗑 — each delegates to the same logic path as its
    typed-command counterpart (calling shared internal functions, not
    duplicating validation/reply logic, per Constitution IV).
  - `callback_query` handler for tapping a keyword in the list.
  - `callback_query` handler for Yes/Cancel on the delete-confirm step.
- `add_handler`'s body extracts a shared `_parse_and_add(conn, chat_id, raw)
  -> list[tuple[str, AddKeywordOutcome]]` helper, used by both the typed
  command and the guided-flow message handler.
- `help_handler` gains the `admin_chat_id` dependency and the operator
  branch described above.

### `messages.py` additions

Button labels, the guided-add prompt, the per-word add-summary formatter,
the delete-confirm prompt, the "already removed" toast, and the operator
help-section text — all Ukrainian, per FR-025.

### FSM storage

aiogram's default in-memory `MemoryStorage`. No persistence requirement:
losing "awaiting keyword input" on a restart just means the subscriber's
next message is treated as a fresh command/button tap, which is a safe,
self-correcting state (they only need to tap ➕ again).

## Error Handling

- Every `callback_query` is `answer()`-ed (Telegram requires this to clear
  the tap's loading spinner), including no-op/stale cases — never left
  unanswered, never raising.
- The comma-parser treats an all-empty batch (e.g. user sends just commas or
  whitespace) as equivalent to today's empty-`/add`-argument case — reuses
  the existing `TooShort` outcome messaging rather than inventing a new state.
- No change to `refuse_if_blocked` / `require_operator` — button handlers for
  subscriber actions go through `refuse_if_blocked` exactly like their typed
  counterparts; a blocked subscriber's button taps get the same `BLOCKED`
  reply.

## Testing

- Unit tests for the comma-parsing helper: single word, multiple words,
  extra whitespace, trailing/leading commas producing empty pieces, all
  duplicates, mixed valid/invalid, hitting the cap mid-batch.
- Unit tests for the new callback handlers: successful delete, cancel,
  stale/already-deleted tap, blocked subscriber.
- Unit test for operator-vs-subscriber `/help` output difference.
- Existing tests for `/add`, `/remove`, `/list`, `/help`, `/stop`,
  `/deleteme`, `/broadcast`, `/stats`, `/block`, `/unblock` must keep passing
  unchanged, aside from `test_db.py` updates for `list_keywords`'s new return
  type.

## Open Questions / Assumptions

- Reply-keyboard button labels are matched by exact text (no dedicated
  `callback_data` for reply-keyboard buttons — that's inherent to Telegram's
  reply-keyboard mechanism, unlike inline keyboards). If a subscriber's own
  keyword text happens to collide with a menu label (e.g. someone adds the
  literal keyword "❓ Довідка"), the button handler take priority for that
  literal chat message — an accepted, narrow edge case consistent with how
  Telegram reply keyboards work generally.
- No change to `SUBSCRIBER_COMMANDS` in `main.py` (the native Telegram "/"
  command menu) — this design only adds the reply/inline keyboard layer.
