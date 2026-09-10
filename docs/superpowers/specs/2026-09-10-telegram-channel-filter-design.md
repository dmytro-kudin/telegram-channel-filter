# Telegram Channel Substring Filter — Design

## 1. System Overview

A single-process, multi-tenant Telegram message router. A userbot (MTProto,
via Telethon) monitors one public source channel that the operator does not
control and cannot join with a bot account. End users configure personal
substring keywords through a standard Telegram bot (aiogram). Matching runs
through a `pyahocorasick` automaton in O(N) per message. Matches are
delivered to users as re-posted messages with a link back to the original
post.

Workload profile: ≤100 users, ≤20 keywords/user (≤2000 total), messages
~20 characters at up to 2/sec peak. Single CPU core, <150MB RAM target.

## 2. Why a Userbot Is Required

The source channel is public but not operator-controlled, so the bot cannot
be added as a member/admin. Telegram's Bot API only pushes `channel_post`
updates to bots that are members of a channel — there is no API for a bot to
subscribe to an arbitrary public channel's posts. `forwardMessage` has the
same restriction: it fails with "message to forward not found" for channels
the bot isn't a member of, even when the channel is public (confirmed
against reported Bot API behavior since v3.4). Therefore:

- **Detection** requires Telethon, joined to the channel as an ordinary
  subscriber (trivial for a public channel, no operator control needed).
- **Delivery** cannot use a native Telegram forward. The bot re-posts the
  captured text as its own message instead.
- **"Navigate to source"** is still achievable because the channel is
  public: every notification includes an inline "🔗 View original" button
  linking to `https://t.me/<channel_username>/<message_id>`, which opens the
  original post for any user, member or not.

## 3. Architecture

Single Python process, one asyncio event loop, two Telegram clients running
concurrently via `asyncio.gather`:

- **Telethon userbot** — read-only, subscribed to the source channel.
  Listens for `NewMessage` events.
- **aiogram Bot** (long polling) — handles user commands and sends
  notifications.

Modules:

| Module | Responsibility |
|---|---|
| `config.py` | Loads `.env` (API_ID, API_HASH, BOT_TOKEN, SOURCE_CHANNEL, DB_PATH) |
| `db.py` | `aiosqlite` wrapper: users/keywords CRUD |
| `pipeline.py` | Ordered, short-circuiting message-processing stages (see §4) |
| `matcher.py` | `AutomatonManager` wrapping `pyahocorasick`; rebuild-and-swap on keyword changes |
| `listener.py` | Telethon setup + `NewMessage` handler wiring the pipeline to the notification queue |
| `notifier.py` | `asyncio.Queue` + rate-limited sender enforcing the global throughput cap |
| `bot.py` | aiogram routers: `/start`, `/add`, `/remove`, `/list`, `/stop`, `/help` |
| `main.py` | Startup wiring: open DB → build initial automaton → run both clients concurrently |

Startup order: open DB connection, build the initial automaton from
persisted keywords, *then* start the Telethon listener and the aiogram
polling loop together. No channel message is processed against an
uninitialized automaton.

## 4. Message Processing Pipeline

Each incoming channel post runs through an ordered list of stages. The first
stage that produces a non-`CONTINUE` outcome short-circuits the rest. Each
stage is a pure function (`text -> Outcome`) with no Telegram or DB
dependency, so the pipeline is fully unit-testable in isolation.

1. **Jar-link stage** — if the text contains `https://send.monobank.ua/jar/`
   (case-insensitive substring check) → outcome = **broadcast to all active
   users**, bypassing personal keyword filters entirely.
2. **Pure-number stage** — if the stripped text consists only of digits and
   numeric punctuation *and* contains at least one digit (`^[\d\s.,]+$` with
   at least one `\d`, e.g. `2800`, `2,800` — but not a string of only
   punctuation/whitespace like `"..."`) → outcome = **skip entirely**; no
   one is notified and the automaton is never consulted for this message.
3. **Keyword stage** (fallback) — run the Aho-Corasick automaton over the
   lowercased text, collect the **union** of matched user IDs (so a user
   with multiple matching keywords in one post still gets exactly one
   notification), filtered to active users.

New rules are added by inserting another stage in this ordered list; no
existing stage needs to change.

## 5. Data Model

```sql
CREATE TABLE users (
    chat_id INTEGER PRIMARY KEY,
    active  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE keywords (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER NOT NULL REFERENCES users(chat_id),
    substring TEXT NOT NULL,
    UNIQUE(chat_id, substring)
);
```

Substrings are stored lowercased for case-insensitive matching. `active`
gates both the jar-link broadcast and the keyword stage — a paused user
receives nothing from either path.

## 6. Automaton Rebuild

`AutomatonManager` holds a reference to the current, immutable automaton. A
rebuild fetches all `(substring, chat_id)` pairs from the DB, groups user
IDs by substring, builds a brand-new `ahocorasick.Automaton` off to the
side, calls `make_automaton()`, then atomically reassigns the manager's
reference (a single attribute assignment, safe under the GIL — readers
never see a partially-built automaton). An `asyncio.Lock` serializes rebuild
triggers so rapid-fire `/add`/`/remove` calls don't race each other doing
redundant work. Triggered on startup and after every keyword mutation.

## 7. Delivery & Rate Limiting

A single global `asyncio.Queue` feeds one sender task that drains it under a
token bucket capped at ~25 messages/sec — a safety margin under Telegram's
30/sec bot-wide limit. On `TelegramRetryAfter` (flood wait), the sender
sleeps for the given delay and requeues that item rather than dropping it.
Because each user receives at most one notification per source post
(deduped in the keyword stage) and source posts arrive at ≤2/sec, per-chat
flood limits are not a separate concern — the shared global throttle already
keeps any single chat's rate well below Telegram's own per-chat pacing.

Each keyword-match or jar-link notification is the re-posted text plus an
inline "🔗 View original" button linking to
`https://t.me/<channel_username>/<message_id>`.

## 8. Bot Commands

Registered via `set_my_commands` so they appear in Telegram's native bot
command menu:

- `/start` — register the user (insert into `users` if new), set
  `active=1`, show usage.
- `/add <word>` — reject if <3 characters or the user already has 20
  keywords; otherwise insert (lowercased, deduped via the UNIQUE
  constraint) and trigger a rebuild.
- `/remove <word>` — delete the row if present, trigger a rebuild.
- `/list` — show all of the user's keywords.
- `/stop` — set `active=0`. Keywords are untouched; `/start` again resumes
  delivery with the same keyword set, no re-adding needed.
- `/help` — usage text.

No inline button is attached to notification messages for stopping —
`/stop` is a first-class command in the bot's menu, not part of each
notification.

## 9. Error Handling

- Telethon disconnects rely on its built-in auto-reconnect; disconnects are
  logged, not treated as fatal.
- DB and input-validation failures produce a user-facing error reply from
  the relevant command handler; they never propagate as unhandled
  exceptions (per the project constitution's explicit-error-handling
  principle).
- Rate-limited sends (`TelegramRetryAfter`) are retried via requeue, never
  silently dropped.

## 10. Testing Strategy

- **Pipeline stages**: pure-function unit tests with plain strings, no
  Telegram/DB dependency — covers jar-link detection, pure-number
  detection, and keyword-stage dedup logic.
- **`AutomatonManager`**: unit tests for rebuild-and-swap correctness
  (old automaton keeps serving until the new one is ready; new one reflects
  the latest DB state after swap).
- **`db.py`**: tests against a temporary SQLite file — add/remove/list,
  the `(chat_id, substring)` uniqueness constraint, the ≤20-keyword cap,
  and the `active` flag.
- **Bot command handlers**: tested with a stubbed DB and a stubbed
  `bot.send_message`, asserting on the reply content and DB side effects.
- **Telethon connectivity** is not unit-tested (requires a real Telegram
  account/session); it stays thin glue code between the pipeline and the
  queue, verified manually against the live channel.

## 11. Out of Scope (YAGNI)

- Multiple source channels — this deployment monitors exactly one,
  configured via `SOURCE_CHANNEL`.
- Media handling — the source channel is plain text only; no photo/document
  capture or re-upload.
- Native Telegram forwarding — established as infeasible in §2; the
  re-post + link-button approach is the permanent solution, not an interim
  one.
- Per-chat rate limiting beyond the shared global throttle — not needed
  given the traffic profile (§7).
