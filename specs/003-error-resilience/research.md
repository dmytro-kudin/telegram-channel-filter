# Phase 0 Research: Runtime Error Resilience

All scope/behavior ambiguities were already resolved with the feature owner
during the brainstorming session that preceded `/speckit-specify` (see
spec.md → Assumptions). This phase resolves the remaining *technical*
questions needed to implement the approved design safely, using only the
stdlib and the frameworks already installed (aiogram, Telethon).

## Decision: Supervision mechanism

**Decision**: A small stdlib `asyncio`-only helper,
`async def supervise(name: str, coro_factory: Callable[[], Awaitable[None]]) -> None`,
looping forever: run `coro_factory()`; on any `Exception`, `logging.exception(...)`
and continue; on clean return, `logging.warning(...)` and continue; always
`await asyncio.sleep(RESTART_DELAY)` before the next attempt.
`main()` runs `asyncio.gather(supervise(...), supervise(...), supervise(...))`
over the three components instead of gathering their raw coroutines directly.

**Rationale**: The project has exactly three long-running components and no
existing process-supervision dependency (no `anyio`, no `tenacity`). A
~15-line stdlib helper satisfies FR-004/FR-005/FR-006 with zero new
dependencies, matches the constitution's Coding Standards bullet ("long-running
background tasks MUST be wrapped by a supervising retry loop"), and is small
enough to unit test directly by making the wrapped coroutine raise on demand.

**Alternatives considered**:
- `tenacity` (retry library) — rejected: designed for retrying a single call,
  not supervising an indefinitely-running task; would add a dependency for
  something ~15 lines of stdlib code already does.
- `anyio` task groups (structured concurrency, cancel-on-first-failure) —
  rejected: `anyio`'s task-group semantics *propagate* a child failure to
  siblings by default (the opposite of FR-006, "a failure in one component
  MUST NOT interrupt... the others"); working around that default adds
  complexity without benefit here, and it's a new dependency.

## Decision: Restart delay

**Decision**: Fixed `RESTART_DELAY = 2.0` seconds, no backoff growth, no
jitter, applied uniformly to all three components and to every consecutive
failure.

**Rationale**: Explicitly confirmed with the feature owner during
brainstorming (see spec.md → Assumptions: "a fixed, small delay... rather
than escalating backoff"). Satisfies SC-002 (<10s recovery) with wide
margin and edge case "fast, repeating failure retries at the same steady
pace" (spec.md Edge Cases).

**Alternatives considered**: Exponential backoff with a cap — presented as
an option during brainstorming and explicitly not chosen, to keep behavior
simple and predictable.

## Decision: Notifier exception handling

**Decision**: `Notifier._send()`'s existing `except TelegramRetryAfter` stays
first (unchanged: wait, requeue). Add, in order:
1. `except TelegramForbiddenError:` → `await db.set_blocked(self._conn, job.chat_id, True)`, then return (drop this job, do not requeue).
2. `except Exception:` → `logging.exception("failed to deliver notification to %s", job.chat_id)`, then return (drop this job).

`notifier.run()`'s `while True` loop also wraps its call to `_send()` in its
own `try/except Exception` (logged), as defense in depth so a bug in the
handling above still can't kill the sender loop — this is the second,
outer layer the design calls for.

Confirmed via the installed aiogram package
(`aiogram.exceptions.TelegramForbiddenError.__mro__`): `TelegramForbiddenError`
→ `TelegramAPIError` → `DetailedAiogramError` → `AiogramError` → `Exception`.
It is a concrete, importable, documented exception type — exactly what
constitution Principle II requires ("a narrow, well-defined exception type
... not a bare except").

**Rationale**: Matches FR-001/FR-002/FR-003 exactly: known case (blocked)
updates subscriber state per the domain rule already encoded elsewhere in
the app (`auth.py`'s `refuse_if_blocked`, `listener.py`'s eligibility
query); unknown case is logged and skipped, never silently discarded
(Principle II) and never allowed to propagate (FR-001).

**Alternatives considered**: Catching only `TelegramForbiddenError` and
letting everything else propagate to the (new) supervisor — rejected:
would satisfy FR-002 but not FR-001/FR-003, since *any other* delivery
error (a transient `TelegramNetworkError`, a malformed request, etc.) would
still drop every subsequent queued job until the supervisor restarts the
notifier a couple of seconds later — a real, if smaller, availability gap
the spec explicitly rules out ("regardless of the reason for that failure").

## Decision: Telethon listener restart

**Decision**: New `listener.run_listener_forever(...)` (or equivalently
named) coroutine, called by the supervisor, that on each invocation: builds
a **fresh** `TelegramClient` via the existing `build_client(...)`, then
`await client.start()`, then `await client.run_until_disconnected()`.

**Rationale**: A `TelegramClient` that has disconnected due to an
unrecoverable error is not documented as safe to restart in place (Telethon
issues recommend constructing a new client). Rebuilding fresh on every
supervised restart is the safe default and costs nothing extra since
`build_client()` is already a pure constructor call with no side effects
until `.start()`.

**Alternatives considered**: Reusing one long-lived `TelegramClient`
instance across restarts and just re-calling `.start()`/`.run_until_disconnected()`
— rejected as unverified/unsafe; Telethon's own connection/session state
machine is not guaranteed to recover cleanly from an arbitrary failure
without rebuilding.

## Decision: Do the aiogram/Telethon frameworks already isolate handler-level exceptions?

**Finding**: Yes, both do, already, independent of this feature:
- aiogram's `Dispatcher._process_update()` (`aiogram/dispatcher/dispatcher.py`)
  wraps update processing in `try/except Exception`, logs via
  `loggers.event.exception(...)`, and returns — a bug in a single command
  handler cannot crash `dp.start_polling()`. This matches the
  `"Cause exception while process update id=... TypeError: ..."` log lines
  observed in the production incident: that earlier, unrelated bug
  (`auth.py` forwarding an unexpected `dispatcher` kwarg) never took down
  the bot, precisely because of this existing isolation.
- Telethon's `_dispatch_event()` (`telethon/client/updates.py`) similarly
  wraps each registered event callback in `try/except Exception`.

**Rationale for scope decision**: Because this isolation already exists at
the framework level for *handler*-level code, `bot.py` and the
`_on_new_message` callback body in `listener.py` need no additional
try/except for this feature — adding one would be redundant defensive
code the constitution's YAGNI-adjacent simplicity expectations argue
against. The actual, confirmed gap was narrower: (a) `notifier.run()`,
which has no framework underneath it, and (b) `main.py`'s composition of
the three components, which had no supervision layer at all. This finding
directly scopes `tasks.md` to `main.py`, `notifier.py`, and `listener.py`
only, matching plan.md's Project Structure section.

## Decision: Logging setup

**Decision**: Add a single `logging.basicConfig(level=logging.INFO)` call
at the top of `main()` (or module level in `main.py`).

**Rationale**: `src/channel_filter/` currently configures no logging at
all — every log line seen in the incident's journal came from aiogram's/
Telethon's own pre-configured loggers, which apparently attach a default
handler. Without `basicConfig`, our new `logging.exception`/`logging.warning`
calls in `supervise()` and `notifier.py` would rely on Python's "handler of
last resort" (stderr, `WARNING`+ only, minimal formatting) — sufficient to
not be silently lost, but not to satisfy FR-008 ("record... every component
failure and every automatic recovery action") at `INFO` level for the
"restarting" log lines. systemd's `Type=simple` service (no `StandardOutput=`
override in `deploy/channel-filter.service`) already sends the process's
stdout/stderr to journald, so no deploy/unit changes are needed — this is a
one-line, in-process change.

**Alternatives considered**: A dedicated logging config module / structured
JSON logging — rejected as out of scope; the spec's only logging
requirement (FR-008) is that failures and recoveries are recorded for
operator review, which plain `journalctl -u channel-filter` already serves
today for every other log line in the app.

## Decision: Top-level safety net (FR-009)

**Decision**: Wrap the existing `asyncio.run(main())` call:

```python
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logging.critical("unrecoverable failure escaped all supervisors", exc_info=True)
        logging.shutdown()  # flush handlers before a hard exit
        os._exit(1)
```

**Rationale**: FR-009 requires the process to terminate *promptly* rather
than risk the exact hang observed in the incident (the process's exact
cause of not exiting after the unhandled `TelegramForbiddenError` was not
conclusively identified during the incident investigation — plausibly a
straggler task ignoring cancellation during `asyncio.run`'s cleanup phase).
Rather than depend on unverified graceful-shutdown behavior,
`os._exit(1)` deterministically terminates the process immediately at the C
level, bypassing any cooperative-cancellation path that could hang —
guaranteeing systemd's `Restart=on-failure` fires. `logging.shutdown()`
immediately before it ensures the critical log line (the one that tells an
operator *why* it happened) is flushed first, so this isn't a silent kill.
This code path is expected to be effectively unreachable after this
feature ships, since `supervise()` never itself raises — it exists purely
as the backstop the constitution's Principle V requires.

**Alternatives considered**: `sys.exit(1)` alone — rejected as insufficient
given this is the exact safety net for the "process didn't actually exit"
failure mode; `sys.exit` only raises `SystemExit` and still depends on
normal interpreter shutdown completing, which is precisely what's in
question. Investigating and fixing the root cause of the original hang —
considered, but out of scope: the specific failure that caused it (an
uncaught `TelegramForbiddenError` reaching `asyncio.run`'s top level) is
eliminated entirely by this feature's other changes, so root-causing the
exact hang mechanism has no remaining reproduction path within this
feature's scope; `os._exit()` provides an unconditional guarantee for any
*other* future top-level escape, making further investigation unnecessary
for FR-009's purposes.

## Summary

No `[NEEDS CLARIFICATION]` markers remain. All technical decisions trace
directly to a functional requirement or success criterion in spec.md, use
only already-installed dependencies, and were validated against the
actually-installed aiogram/Telethon source where relevant.
