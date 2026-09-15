# Implementation Plan: Runtime Error Resilience

**Branch**: `003-error-resilience` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-error-resilience/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

The bot's three long-running processes (Telethon channel listener, aiogram
command polling, and the notification sender) currently share a single
`asyncio.gather()` in `main.py` with no failure isolation: an unhandled
exception in any one of them — as happened in production when a notification
was sent to a subscriber who had blocked the bot — ends the whole process,
and the process can be left running-but-inert instead of actually exiting
for systemd to restart it. This plan replaces that single `gather()` with
three independently supervised loops (a small `supervise()` helper that
catches, logs, and restarts a failed component after a fixed 2-second
delay), makes the notifier's per-job send resilient (catch known Telegram
errors explicitly, mark a blocking subscriber `blocked` via the existing
`db.set_blocked()` helper, never let one job's failure stop the queue), and
adds a top-level safety net that forces the process to actually exit if
something ever escapes supervision — directly implementing constitution
Principle V (Resilient by Default) using only the stdlib `asyncio`/`logging`
already in use, no new dependencies.

## Technical Context

**Language/Version**: Python 3.11+ (project `requires-python`; deployed server runs 3.14)

**Primary Dependencies**: aiogram >=3.4, telethon >=1.36, aiosqlite >=0.20, pyahocorasick >=2.1 (all existing — no new dependencies; supervision is implemented with stdlib `asyncio`/`logging` only)

**Storage**: SQLite via `aiosqlite` (`channel_filter.db`) — reuses the existing `subscribers.blocked` column; no schema change

**Testing**: pytest + pytest-asyncio (`asyncio_mode = auto`, per `pyproject.toml`)

**Target Platform**: Linux server, managed by systemd (`deploy/channel-filter.service`, `Restart=on-failure`)

**Project Type**: Single Python application (long-running background service), not web/mobile — no new external interface

**Performance Goals**: Component auto-recovery within a few seconds of failure (SC-002: <10s); existing notification throttle (25 msg/s) unchanged

**Constraints**: No new dependencies; no change to bot command behavior/UX; must not weaken the existing `TelegramRetryAfter` rate-limit handling; restart delay is a fixed ~2s per component (not exponential backoff, not zero-delay — confirmed during brainstorming)

**Scale/Scope**: Single bot process; three supervised components (listener, polling, notifier); touches `main.py`, `notifier.py`, `listener.py` only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. No Assumptions, No Inferred Intent** — PASS. All open questions (restart philosophy, backoff strategy, scope) were resolved with the feature owner during the brainstorming session preceding `/speckit-specify`; resolutions are recorded in spec.md's Assumptions section.
- **II. Explicit, Typed Error Handling** — PASS. Every new `except` clause names a specific, documented exception type (`TelegramForbiddenError`, `TelegramRetryAfter`) or is an intentional last-resort `except Exception` boundary that logs the full cause (`logging.exception`/`logging.critical(..., exc_info=True)`) rather than discarding it — never a bare `except: pass`. See research.md for the exact catch hierarchy.
- **III. Typed Domain Values Over Raw Primitives** — N/A / PASS. This feature adds no new domain data; it reuses the existing `Subscriber`/`blocked` model as-is and introduces no new bare-primitive domain values.
- **IV. Cross-Cutting Concerns Stay Out of Business Logic** — PASS. The `supervise()` restart wrapper is exactly the kind of reusable, decorator-like cross-cutting mechanism this principle calls for, kept in `main.py` as infrastructure separate from `notifier.py`/`listener.py`/`bot.py`'s business logic. Notifier error handling for a *known* domain case (blocked subscriber) stays in the notifier because it's a business rule (update subscriber state), not a generic cross-cutting concern.
- **V. Resilient by Default** — PASS (this feature is the direct implementation of this principle: explicit handling of every reachable exception, per-component supervised auto-recovery, and a guaranteed process exit when recovery is impossible).
- **Coding Standards** (type hints, async never blocking, no duplicated constants, background tasks under a supervising retry loop) — PASS. `supervise()` is precisely the "background tasks MUST be wrapped by a supervising retry loop" bullet added to the constitution alongside Principle V.
- **TDD workflow** — Will be followed during `/speckit-implement`: each behavior (blocked-subscriber handling, catch-all job drop, supervisor restart-on-failure) gets a failing test first, per `tasks.md`.

No violations. Complexity Tracking table is not needed.

**Post-Design Re-check** (after Phase 0/1 artifacts below): research.md's
decisions (named exception types, stdlib-only supervisor, explicit
`logging.critical` + flush before the forced exit) and data-model.md's
"no new entities, one reused state transition" confirm no new violations
were introduced during design. Gate still PASSES.

## Project Structure

### Documentation (this feature)

```text
specs/003-error-resilience/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature changes internal runtime supervision
and error handling only. It exposes no new external interface — bot
commands, message formats, and the notification delivery contract to
Telegram are unchanged.

### Source Code (repository root)

```text
src/channel_filter/
├── main.py       # MODIFIED: add supervise() helper; replace the single
│                 #   asyncio.gather(...) with three supervised loops;
│                 #   add logging.basicConfig(...); add top-level
│                 #   safety-net exit handler around asyncio.run(main())
├── listener.py   # MODIFIED: add run_listener_forever() (or equivalent)
│                 #   that (re)builds a fresh TelegramClient and runs it,
│                 #   for the supervisor to call on each restart
├── notifier.py   # MODIFIED: Notifier takes a db connection; _send()
│                 #   gains explicit TelegramForbiddenError handling
│                 #   (-> db.set_blocked) and a catch-all Exception
│                 #   handler; run()'s loop also wraps _send() defensively
├── db.py         # UNCHANGED: existing set_blocked() is reused as-is
└── bot.py        # UNCHANGED: aiogram already isolates per-update
                  #   exceptions (confirmed from prior incident logs);
                  #   no change needed here

tests/unit/
├── test_notifier.py   # NEW: notifier resilience behavior
├── test_supervise.py  # NEW: supervisor restart-on-failure behavior
├── test_listener.py   # NEW: run_listener_forever() build/start/run ordering
└── test_main.py       # NEW: configure_logging(), build_supervised_tasks()
                        #   wiring, and the top-level safety-net wrapper

tests/integration/
└── test_pipeline_to_notifier.py  # EXISTING: verify still passes unchanged
```

**Structure Decision**: Single-project layout (already established by this
repo — `src/channel_filter/`, `tests/unit/`, `tests/integration/`). This
feature is implemented entirely within the existing package; no new
top-level directories or projects.

## Complexity Tracking

*No constitution violations — table not needed.*
