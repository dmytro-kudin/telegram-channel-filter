# Phase 1 Data Model: Button-Driven Subscriber UX & Admin Discoverability

This feature introduces no new persisted entity and no schema migration. It
changes how one existing column is *read* and adds one transient,
non-persisted concept (the guided-add flag). Everything below is additive to
`specs/001-channel-keyword-filter/data-model.md`, which remains the source of
truth for `Subscriber`, `Keyword`, `Operator`, `Outcome`, and
`NotificationJob`.

## Changed read shape: Keyword

No schema change — `keywords.id` already exists (001 schema). Only the
Python-level return type of `db.list_keywords` changes:

| Before (001) | After (002) |
|---|---|
| `list[str]` (lowercased substrings only) | `list[Keyword]` (existing `dataclass`: `id`, `chat_id`, `substring`) |

**Why**: inline-keyboard buttons need a stable, compact identifier per
keyword for `callback_data` (research.md §4) — the id, not the text.

**Callers affected**: `list_handler` (typed `/list`) now reads `.substring`
off each `Keyword` instead of iterating bare strings; the new "My keywords"
button handler and the keyword-list inline keyboard builder consume the
same `list[Keyword]`.

## New DB operation: remove_keyword_by_id

| Signature | `remove_keyword_by_id(conn, chat_id: int, keyword_id: int) -> RemoveKeywordOutcome` |
|---|---|
| Returns | `Removed()` if a row matching both `chat_id` and `id` was deleted; `NotFound()` otherwise (already-removed / never existed / belongs to a different subscriber) |

Reuses the existing `RemoveKeywordOutcome` type from `types.py` — no new
outcome shape. The existing text-based `remove_keyword` (typed `/remove`) is
unchanged and continues to be used for that path; this is an additional
lookup path by id, not a replacement.

**Why both exist**: the typed `/remove <word>` command only ever has the
word text to go on; the inline-button flow only ever has the id it rendered
into `callback_data` (research.md §4). Normalizing an id back to text (or
vice versa) to force a single code path would add a lookup with no benefit.

## Transient (non-persisted) concepts

### Guided-add FSM state

| Field | Type | Notes |
|---|---|---|
| state | aiogram `State` (`AddKeywords.waiting`) | Set when the Add-keyword button is tapped; cleared after the next message is processed, or if any other command/button arrives first (research.md §2) |
| storage | aiogram in-memory `MemoryStorage` (default) | Keyed by chat, per aiogram's standard FSM context; not backed by SQLite — acceptable to lose on restart |

Not a domain entity — exists only to disambiguate "this plain-text message
is the answer to the add-keyword prompt" from "this is unrelated input." No
new dataclass; aiogram's own typed `State`/`StatesGroup` is the
representation (Constitution Principle III — no raw string/bool flag used
in its place).

### Callback data encoding

Two inline-keyboard interactions each encode a small, fixed-shape payload in
`callback_data` (Telegram's 64-byte limit, comfortably met by these):

| Interaction | Encoded payload | Example |
|---|---|---|
| Tap a keyword in the list | action tag + keyword id | `kw:42` |
| Confirm/cancel a pending deletion | action tag + keyword id + yes/no | `kwdel:42:y`, `kwdel:42:n` |

These are wire-format details of the callback handlers in `bot.py`/
`keyboards.py`, not persisted anywhere — listed here only so `tasks.md` has
an unambiguous contract to implement against.

## Unchanged

`Subscriber`, `Operator`, `ChannelPost`, `Outcome`, `NotificationJob`, and the
SQLite schema itself (`subscribers`, `keywords` tables) are exactly as
defined in `specs/001-channel-keyword-filter/data-model.md`. This feature
adds no column, no table, and no migration.
