# Phase 1 Data Model: Runtime Error Resilience

This feature introduces **no new persisted entities and no schema change**.
It touches one existing entity's state transition and adds one
non-persisted, code-level concept.

## Existing entity touched: Subscriber (`subscribers` table, `db.py`)

| Field     | Type    | Notes                                                      |
|-----------|---------|--------------------------------------------------------------|
| `chat_id` | INTEGER | Primary key. Unchanged by this feature.                     |
| `active`  | INTEGER (bool) | Unchanged by this feature.                            |
| `blocked` | INTEGER (bool) | **New writer**: `Notifier._send()` now calls the existing `db.set_blocked(conn, chat_id, True)` when a delivery attempt raises `TelegramForbiddenError`, in addition to the existing callers (subscriber-initiated block detection elsewhere in the app, if any, and `auth.py`'s read path via `refuse_if_blocked`). |

**State transition added**:

```
Subscriber(blocked=False) --[delivery raises TelegramForbiddenError]--> Subscriber(blocked=True)
```

This is the *only* state transition this feature adds. The reverse
transition (`blocked=True` → `blocked=False`) already exists via the
subscriber's own resubscription flow (`/start`) per FR-010 and is
unchanged by this feature.

No new columns, no new tables, no migration required — `db.SCHEMA` in
`db.py` is unmodified.

## Non-persisted concept: Bot component

Not a database entity — a **runtime/code-level concept** introduced purely
to describe the supervision design:

| Component            | Represents                                   | Supervised coroutine (Phase 2 will name the exact function) |
|-----------------------|----------------------------------------------|----------------------------------------------------------------|
| Channel listener      | Telethon client connection + new-message handling | `listener.run_listener_forever(...)` (new) |
| Command handling      | aiogram bot command polling                  | `dp.start_polling(aiogram_bot)` (existing, unchanged) |
| Notification delivery | The notifier's send queue                    | `notifier.run(aiogram_bot)` (existing, modified per this feature) |

Each is wrapped by `main.py`'s new `supervise(name, coro_factory)` helper
(see research.md → "Decision: Supervision mechanism"). No new dataclass or
type is needed to represent this concept in code — it exists only as the
three `supervise(...)` call sites in `main()`.
