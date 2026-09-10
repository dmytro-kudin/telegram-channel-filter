# Implementation Plan: Channel Keyword Filter

**Branch**: `001-channel-keyword-filter` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-channel-keyword-filter/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A single Python process runs two Telegram clients concurrently: a Telethon
userbot that detects new posts in one public channel the operator doesn't
control, and an aiogram bot that handles subscriber commands and deliveries.
Every detected post runs through an ordered, short-circuiting rule pipeline
(jar-link broadcast → bare-number suppression → keyword match) built so new
rules can be added later without touching existing ones (FR-016). Matches
are re-posted (not natively forwarded, since the bot can't join the source
channel) with a link back to the original public post. Subscriber keywords,
pause state, and blocked state persist in SQLite and are matched via an
in-memory Aho-Corasick automaton, built only from active, non-blocked
subscribers' keywords and rebuilt/atomically swapped whenever a keyword, or
a subscriber's active/blocked eligibility, changes.

A single fixed operator (identified by a config value, not a Subscriber
record) has three admin-only actions layered on top of the same bot:
broadcasting an arbitrary message to every active, non-blocked subscriber;
viewing subscriber counts by state; and blocking/unblocking a subscriber,
which overrides that subscriber's own pause control and their ability to
run any command except deleting their own data. Any subscriber can also
permanently delete their own record and keywords at any time, including
while blocked. All bot-authored text is Ukrainian (FR-025); channel content
and subscriber-supplied keywords are shown/matched as-is regardless of
language.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Telethon (MTProto userbot client), aiogram 3.x
(Bot API, long polling), pyahocorasick (C-backed Aho-Corasick automaton),
aiosqlite (async SQLite access), python-dotenv (`.env` loading). No i18n
library is needed for the Ukrainian-only UI text (FR-025) — a single module
of plain string constants is sufficient since there is exactly one fixed
language and no per-subscriber language selection.

**Storage**: SQLite, single local file (`aiosqlite`) — stores subscribers
(including blocked state) and keywords only; no notification history is
persisted (see data-model.md)

**Testing**: pytest + pytest-asyncio

**Target Platform**: Single Linux server/container, one long-running process

**Project Type**: Single project (backend service / bot) — no frontend, no
separate API layer beyond the Telegram bot itself

**Performance Goals**: Detect and enqueue a matching post within a couple of
seconds of publication; deliver queued notifications at up to ~25 msg/sec
(safety margin under Telegram's 30/sec bot-wide cap) to meet SC-001's 5s
target under the expected ≤2 posts/sec channel volume

**Constraints**: Single CPU core, <150MB RAM steady-state; no native
Telegram forward available (bot isn't a channel member — see spec.md §
rationale in User Story context); source channel is plain text only

**Scale/Scope**: ≤100 subscribers, ≤20 keywords/subscriber (≤2000 keywords
total) — trivial rebuild cost for `pyahocorasick` at this scale

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance approach |
|---|---|
| I. No Assumptions, No Inferred Intent | All open questions (aggregation, forwarding feasibility, media scope, keyword limits, jar-link scope, stop semantics, pipeline extensibility, admin scope, data deletion, UI language) were already resolved with the user during brainstorming/spec/clarify phases; nothing here is guessed. |
| II. Explicit, Typed Error Handling | Pipeline stages return an explicit `Outcome` value (`Skip`/`BroadcastAll`/`MatchedUsers`/`Continue`), never raise for expected results. Bot command handlers — including admin ones — return/reply with explicit validation failures (too-short keyword, over-limit, not-found, not-authorized) rather than raising. Exceptions are reserved for actual failures (DB errors, Telegram API errors). |
| III. Typed Domain Values Over Raw Primitives | `Subscriber` (now carrying `blocked`), `Keyword`, `ChannelPost`, and `Outcome` are modeled as `dataclass`/`NamedTuple` types (data-model.md), not passed as bare dicts/tuples across module boundaries. The operator identity is a single configured `ChatId`, compared explicitly rather than inferred. |
| IV. Cross-Cutting Concerns Stay Out of Business Logic | Rate limiting and retry-on-flood-wait live in `notifier.py`; operator-authorization checking lives in one `require_operator` decorator in `auth.py`, applied to the four admin handlers rather than repeated inline in each; DB access is isolated in `db.py`; pipeline stages themselves are pure functions with no I/O. |

No violations identified. Complexity Tracking is not needed.

**Post-Phase 1 re-check (reconciled after clarify session)**: data-model.md's
typed `Outcome`/`Subscriber`/`Keyword` shapes, the `require_operator`
decorator, and the contracts/ stage interface confirm the plan still
satisfies all four principles after adding the operator role, blocking, and
self-service deletion — no new violations, no changes to this table's
verdict were needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-channel-keyword-filter/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── bot-commands.md
│   ├── admin-commands.md
│   └── pipeline-stage-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── channel_filter/
    ├── __init__.py
    ├── config.py        # loads .env: API_ID, API_HASH, BOT_TOKEN, SOURCE_CHANNEL, ADMIN_CHAT_ID, DB_PATH
    ├── messages.py       # single source of all Ukrainian bot-reply text templates (FR-025)
    ├── db.py             # aiosqlite wrapper: subscribers (active/blocked)/keywords CRUD, stats query, delete
    ├── types.py          # Subscriber (+blocked), Keyword, ChannelPost, Outcome dataclasses/NewTypes
    ├── pipeline.py        # ordered stage list + jar-link/pure-number/keyword-match stages
    ├── matcher.py         # AutomatonManager (pyahocorasick build/rebuild/swap on keyword or eligibility change)
    ├── notifier.py        # asyncio.Queue + token-bucket sender, flood-wait retry
    ├── listener.py         # Telethon client setup + NewMessage handler wiring
    ├── auth.py             # require_operator decorator (FR-017/FR-018)
    ├── bot.py             # aiogram routers: /start /add /remove /list /stop /deleteme /help + admin: /broadcast /stats /block /unblock
    └── main.py            # startup wiring: open DB → build automaton → run both clients

tests/
├── unit/
│   ├── test_pipeline.py    # jar-link / pure-number / keyword-stage short-circuit logic
│   ├── test_matcher.py     # rebuild-and-swap correctness, incl. rebuild on eligibility change
│   ├── test_db.py          # CRUD, uniqueness constraint, 20-keyword cap, active/blocked flags, delete, stats
│   ├── test_auth.py        # require_operator accepts the configured admin, refuses everyone else
│   └── test_bot_commands.py # command handlers (incl. admin ones) against a stubbed db + stubbed send
└── integration/
    └── test_pipeline_to_notifier.py  # pipeline output correctly enqueues notifier jobs
```

**Structure Decision**: Single project, one flat package (`src/channel_filter/`)
rather than the generic `models/services/cli/lib` template split — the
codebase is small (single bot process) and each module already has one
clear responsibility (Coding Standard: module layout matches logical
structure). No web/mobile split applies.

## Complexity Tracking

*No Constitution Check violations — this section is not needed.*
