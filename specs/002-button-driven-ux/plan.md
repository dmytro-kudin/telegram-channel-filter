# Implementation Plan: Button-Driven Subscriber UX & Admin Discoverability

**Branch**: `002-button-driven-ux` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-button-driven-ux/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Layers a button-driven interface on top of the existing, fully-typed
001-channel-keyword-filter bot without changing any of its underlying rules.
A persistent reply keyboard (aiogram `ReplyKeyboardMarkup`) gives subscribers
one-tap access to add/list/pause-resume/help; tapping "add" starts a short
FSM-tracked prompt so the subscriber's next plain message (one or more
comma-separated words) is parsed and validated per-word through the existing
`add_keyword` rules. Tapping "my keywords" renders the list as an inline
keyboard (`InlineKeyboardBuilder`), and tapping a keyword opens a Yes/Cancel
inline confirmation before it's deleted. `/help` becomes operator-aware,
appending the existing `/broadcast`/`/stats`/`/block`/`/unblock` usage only
when the sender is `ADMIN_CHAT_ID`. Permanently deleting an account remains a
typed-only action (`/deleteme`, unchanged) — deliberately left off the
persistent menu since it's rare and irreversible, not something that needs
one-tap access. Every typed command keeps behaving exactly as documented in
`specs/001-channel-keyword-filter/contracts/`; nothing here changes matching,
delivery, or admin authorization semantics.

## Technical Context

**Language/Version**: Python 3.11+ (unchanged)

**Primary Dependencies**: aiogram 3.x — no new dependency. This feature uses
parts of aiogram already in the project (`InlineKeyboardBuilder`, used today
in `notifier.py`) plus two parts not yet used: `ReplyKeyboardMarkup`/
`KeyboardButton` for the persistent menu, and aiogram's built-in FSM
(`State`/`StatesGroup`/`FSMContext`) for the guided add-keyword prompt.

**Storage**: SQLite, unchanged schema — `keywords.id` (already a schema
column, see `specs/001-channel-keyword-filter/data-model.md`) is now also
*selected* by `list_keywords` so each keyword can carry a stable identifier
into inline-keyboard `callback_data`. No migration needed.

**Testing**: pytest + pytest-asyncio (unchanged)

**Target Platform**: Same Oracle Cloud Always-Free VM deployment as
001 — no infrastructure change; this is an interaction-layer-only feature
on the same long-running process.

**Project Type**: Single project (same `src/channel_filter/` package)

**Performance Goals**: No new measurable target — button taps and callback
queries are handled on the same event loop as today's message commands, with
the same sub-second local processing cost; no additional network calls per
interaction beyond what the equivalent typed command already made.

**Constraints**: The guided add-keyword "awaiting input" flag is tracked via
aiogram's default in-memory FSM storage (`MemoryStorage`) — acceptable to
lose on process restart, since it only affects a subscriber mid-way through
one guided prompt (they just tap the button again), unlike keyword/pause
data which must survive restarts (FR-015, unaffected by this feature).
Inline-keyboard `callback_data` is capped at 64 bytes by the Telegram Bot
API; the id-based encoding chosen in research.md comfortably fits.

**Scale/Scope**: Same ≤100 subscribers / ≤20 keywords each as 001. A
20-keyword inline list is well within Telegram's per-message keyboard limits
(100 buttons/message, 8 buttons/row), so no pagination is needed at this
feature's scale.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance approach |
|---|---|
| I. No Assumptions, No Inferred Intent | Every open UX question (reply vs. inline keyboards, delete confirmation style, guided-add prompt shape, partial-batch add semantics, admin-menu scope, block/unblock scope) was already resolved with the user during the brainstorming session (`docs/superpowers/specs/2026-09-10-button-driven-ux-design.md`) before this plan was written; nothing here is guessed. |
| II. Explicit, Typed Error Handling | The comma-parsing helper reuses the existing `AddKeywordOutcome` variants (`Added`/`AlreadyExists`/`TooShort`/`LimitReached`) per word — no new exception types, no bare `except`. A stale/already-removed keyword tap reuses `RemoveKeywordOutcome`'s `NotFound` shape rather than raising. Every `callback_query` handler explicitly answers the callback (Telegram requirement) on every branch, including no-op ones. |
| III. Typed Domain Values Over Raw Primitives | `list_keywords` returns `list[Keyword]` (existing `dataclass`, `id`+`chat_id`+`substring`) instead of bare `list[str]`, so callback data is built from a typed field, not a re-parsed string. The guided-add FSM state is a typed aiogram `State` (`AddKeywords.waiting`), not a raw string/bool flag on some ad-hoc object. |
| IV. Cross-Cutting Concerns Stay Out of Business Logic | Keyboard construction is isolated in a new `keyboards.py` (mirrors `notifier.py`'s existing pattern of building its own inline keyboard away from handler/business logic). Comma-parsing is one shared helper used by both the typed `/add` path and the guided-flow path (Coding Standard: no duplicated per-type parsing logic). The existing `require_operator`/`refuse_if_blocked` decorators are reused unchanged for every new handler — no new inline authorization checks. |

No violations identified. Complexity Tracking is not needed.

**Post-Phase 1 re-check**: data-model.md's typed `Keyword` (now flowing
through `list_keywords`), the `keyboards.py` isolation, and the shared
comma-parsing helper confirm the design still satisfies all four principles
after Phase 1 detail — no new violations, no change to this table's verdict.

## Project Structure

### Documentation (this feature)

```text
specs/002-button-driven-ux/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── button-menu.md
│   ├── add-flow.md
│   ├── keyword-deletion.md
│   └── admin-help.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── channel_filter/
    ├── __init__.py
    ├── config.py        # unchanged
    ├── messages.py       # + button labels, guided-add prompt, per-word add summary,
    │                     #   delete-confirm prompts, "already removed" toast, admin help section
    ├── keyboards.py       # NEW: ReplyKeyboardMarkup (subscriber menu) + InlineKeyboardMarkup
    │                     #   builders (keyword list, delete-confirm) — mirrors notifier.py's
    │                     #   existing pattern of keeping keyboard construction out of handlers
    ├── db.py             # list_keywords -> list[Keyword] (was list[str]); + remove_keyword_by_id
    ├── types.py          # unchanged (Keyword already has id/chat_id/substring)
    ├── pipeline.py       # unchanged
    ├── matcher.py         # unchanged
    ├── notifier.py        # unchanged
    ├── listener.py         # unchanged
    ├── auth.py             # unchanged — require_operator/refuse_if_blocked reused as-is
    ├── bot.py             # + reply-keyboard button handlers, guided-add FSM state + handler,
    │                     #   keyword-delete / delete-confirm callback_query handlers,
    │                     #   shared comma-parsing helper used by /add and the guided flow,
    │                     #   help_handler gains the operator-aware branch
    └── main.py            # unchanged (aiogram's Dispatcher() already defaults to in-memory
                          #   FSM storage, sufficient per Constraints above)

tests/
├── unit/
│   ├── test_pipeline.py    # unchanged
│   ├── test_matcher.py     # unchanged
│   ├── test_db.py          # + list_keywords return type, remove_keyword_by_id
│   ├── test_auth.py        # unchanged
│   ├── test_keyboards.py   # NEW: menu layout/labels reflect active state, keyword-list and
│   │                       #   delete-confirm keyboards encode the right callback_data
│   └── test_bot_commands.py # + comma-parser edge cases, guided-add flow, delete/cancel/stale
│                             #   callback handling, operator-vs-subscriber /help
└── integration/
    └── test_pipeline_to_notifier.py  # unchanged

deploy/
└── channel-filter.service  # unchanged
```

**Structure Decision**: Same single flat package as 001
(`src/channel_filter/`) — this feature adds one new module (`keyboards.py`,
one clear responsibility: build keyboard markup) and extends existing
modules along their current responsibilities (`bot.py` for handlers,
`db.py` for persistence, `messages.py` for user-facing text). No new
top-level structure is warranted at this scale.

## Complexity Tracking

*No Constitution Check violations — this section is not needed.*
