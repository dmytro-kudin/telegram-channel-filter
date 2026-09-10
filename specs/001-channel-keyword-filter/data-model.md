# Phase 1 Data Model: Channel Keyword Filter

## Persisted entities

### Subscriber

Maps to spec's **Subscriber** entity.

| Field | Type | Notes |
|---|---|---|
| `chat_id` | `int` (primary key) | Telegram chat ID; assigned on first `/start` (FR-001) |
| `active` | `bool` (default `True`) | `False` while paused (FR-010–FR-012) |
| `blocked` | `bool` (default `False`) | `True` only while the operator has blocked this subscriber (FR-021/FR-022); overrides `active` for eligibility |

**Eligibility predicate**, used everywhere delivery is decided (keyword
match, jar-link broadcast, operator broadcast): `eligible(subscriber) =
subscriber.active and not subscriber.blocked`. A subscriber is `eligible`
if and only if they should receive anything at all (FR-012, FR-013,
FR-019, FR-021).

State transitions:
- `active`: `True → False` on `/stop`; `False → True` on `/start` after
  first registration. Unaffected by `blocked`.
- `blocked`: `False → True` only via the operator's block action; `True →
  False` only via the operator's unblock action, which restores whatever
  `active` value the subscriber had before being blocked (FR-022) — the
  row's `active` field is never modified by block/unblock itself.
- **Deletion** (FR-023/FR-024) is not a field transition — the row (and all
  its Keyword rows) is removed entirely. It is available regardless of
  `blocked`, since deleting one's own data is exempt from a block.

### Keyword

Maps to spec's **Keyword** entity.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` (primary key, autoincrement) | Internal identifier |
| `chat_id` | `int` (foreign key → Subscriber.chat_id) | Owning subscriber |
| `substring` | `str` | Stored lowercased for case-insensitive matching (FR-004) |

**Validation rules** (enforced before insert, per FR-002–FR-004):
- `len(substring) >= 3` after stripping whitespace, or the add is rejected.
- A subscriber may not have more than 20 rows — the 21st add attempt is
  rejected (FR-003).
- `(chat_id, lower(substring))` is unique — adding an existing keyword is a
  no-op with a confirmation reply, not a new row (FR-004).

**Relationship**: one Subscriber has many Keywords (1:N). Deleting a
Subscriber (FR-023) cascades to delete all of their Keyword rows in the
same operation — see Schema below.

## Non-persisted identity

### Operator

Maps to spec's **Operator** entity (FR-017). Not a database row — a single
Telegram `chat_id` fixed in configuration (`ADMIN_CHAT_ID`). Authorization
for the four admin actions (broadcast, stats, block, unblock) is a direct
equality check against this configured value, applied via one shared
decorator (see research.md §6b) rather than a role flag stored per
Subscriber.

## Transient (non-persisted) concepts

These exist only in memory during processing of a single channel post; none
are written to storage, since no requirement calls for notification history
or replay.

### ChannelPost

The raw input to the pipeline (FR-016), sourced from a Telethon `NewMessage`
event, never persisted.

| Field | Type | Notes |
|---|---|---|
| `message_id` | `int` | Used to build the "View original" link |
| `text` | `str` | Raw post text; lowercased where a stage needs case-insensitivity |

### Outcome

The explicit, typed result of running a `ChannelPost` through the pipeline
(Constitution Principle II — no exceptions for expected control flow). Only
one of these four shapes can be true for a given post, enforced by the
pipeline's short-circuit contract (FR-016):

| Variant | Meaning |
|---|---|
| `Skip` | No one is notified for this post (e.g., bare-number stage matched) |
| `BroadcastAll` | Every currently *eligible* Subscriber is notified (e.g., jar-link stage matched); resolved against a fresh DB read at delivery time, not baked into the automaton |
| `MatchedUsers(chat_ids: frozenset[int])` | Only these Subscribers are notified (keyword stage) — already guaranteed eligible, because the automaton is rebuilt only from eligible subscribers' keywords (research.md §6a), so no separate filtering step is needed here |
| `Continue` | This stage doesn't apply; pipeline proceeds to the next stage |

An operator-triggered `/broadcast` (FR-019) does **not** go through this
pipeline at all — it has no `ChannelPost` to evaluate. It resolves
recipients the same way `BroadcastAll` does (a fresh query for currently
eligible subscribers) and enqueues `NotificationJob`s directly (research.md
§6c).

### NotificationJob

What's placed on the delivery queue in `notifier.py` for exactly one
`(subscriber, text)` pair — one job per recipient, whether the text and
`message_id` came from a matched `ChannelPost` or from an operator
broadcast. Not persisted — if the process restarts mid-send, in-flight jobs
are lost; this is acceptable because FR-015 only requires Subscriber/
Keyword configuration to survive a restart, not notification history or
delivery guarantees across a crash.

| Field | Type | Notes |
|---|---|---|
| `chat_id` | `int` | Delivery target |
| `text` | `str` | The original post's text (pipeline-driven), or the operator's own text (broadcast) |
| `message_id` | `int \| None` | Present for pipeline-driven jobs, used to build the "🔗 View original" link; `None` for an operator broadcast, which has no source post and so is sent with no such link |

## Schema (SQLite, via aiosqlite)

```sql
CREATE TABLE subscribers (
    chat_id INTEGER PRIMARY KEY,
    active  INTEGER NOT NULL DEFAULT 1,
    blocked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE keywords (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER NOT NULL REFERENCES subscribers(chat_id) ON DELETE CASCADE,
    substring TEXT NOT NULL,
    UNIQUE(chat_id, substring)
);
```

`ON DELETE CASCADE` requires `PRAGMA foreign_keys = ON` to be set on every
`aiosqlite` connection (SQLite has it off by default) — deleting a
subscriber's row (FR-023) then removes all their keywords in the same
statement, with no separate cleanup query needed.
