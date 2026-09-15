---

description: "Task list template for feature implementation"
---

# Tasks: Runtime Error Resilience

**Input**: Design documents from `/specs/003-error-resilience/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: This project's constitution (`.specify/memory/constitution.md` → Development Workflow → Superpowers TDD Protocol) makes RED-GREEN-REFACTOR **non-negotiable** for every task, so test tasks are included and MUST be completed (and observed failing for the right reason) before their paired implementation task. (Revised 2026-09-15 after `/speckit-analyze` finding C1: the `main.py` wiring step that previously had no preceding test now does — see T011/T012 below — so no task in this file is exempted from RED-GREEN-REFACTOR.)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and repository-relative

## Path Conventions

Single project (existing layout): `src/channel_filter/`, `tests/unit/`, `tests/integration/` at repository root.

---

## Phase 1: Setup

**Purpose**: Confirm a clean starting point. No new dependencies, tooling, or project scaffolding is needed — see plan.md's Technical Context.

- [X] T001 Run `uv run pytest` at the repository root and confirm the full existing suite is green before making any change, establishing the baseline this feature must not regress.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one piece of shared infrastructure every story's `logging.exception`/`logging.warning`/`logging.critical` calls depend on to be recorded properly (FR-008).

**⚠️ CRITICAL**: Complete before starting any user story phase.

- [X] T002 Write a failing test in `tests/unit/test_main.py` for a new `configure_logging()` function: reset the root logger's level (e.g. `logging.getLogger().setLevel(logging.WARNING)`), call `channel_filter.main.configure_logging()`, and assert `logging.getLogger().getEffectiveLevel() == logging.INFO`. Run it and confirm it fails because `configure_logging` doesn't exist yet.
- [X] T003 Implement `configure_logging()` in `src/channel_filter/main.py` (wraps `logging.basicConfig(level=logging.INFO)`) and call it at the top of `main()`, before any other setup. Confirm T002 now passes.

**Checkpoint**: Logging is configured; all subsequent stories' log calls will be recorded at INFO+ per FR-008.

---

## Phase 3: User Story 1 - One failed delivery never stops the rest of the queue (Priority: P1) 🎯 MVP

**Goal**: A delivery failure to one subscriber (blocked-bot or any other error) never stops notifications going out to the rest of the queue, and a blocking subscriber is automatically marked blocked.

**Independent Test**: Unit-test `Notifier` directly (no supervisor, no live Telegram needed) — see tests below. End-to-end: quickstart.md §2.

### Tests for User Story 1 ⚠️

> Write these first; confirm each fails for the right reason before implementing.

- [X] T004 [P] [US1] In `tests/unit/test_notifier.py` (new file), using the existing `conn` fixture (`tests/conftest.py`), `caplog`, and a fake `Bot` double whose `send_message` can be made to raise on demand, write three failing tests:
  1. `send_message` raises `aiogram.exceptions.TelegramForbiddenError` for job A → after `Notifier.run()` processes it, `db.get_or_create_subscriber(conn, A.chat_id)` shows `blocked is True`, a second queued job B for a different, non-failing chat_id is still delivered (fake bot recorded the call for B), **and** `caplog` captured a log record referencing `A.chat_id` for the failed delivery.
  2. `send_message` raises an arbitrary unrecognized `Exception` for job A → job A is dropped (not left in the queue, not retried forever), job B still gets delivered, **and** `caplog` captured a log record referencing `A.chat_id` for the failure (FR-008).
  3. The existing `TelegramRetryAfter` behavior (wait, then requeue and eventually deliver) still passes, now that `Notifier` takes a `conn` argument — regression coverage for the constructor signature change in T005.

### Implementation for User Story 1

- [X] T005 [US1] In `src/channel_filter/notifier.py`: add a `conn: aiosqlite.Connection` parameter to `Notifier.__init__` (store as `self._conn`); in `_send()`, keep the existing `except TelegramRetryAfter` first, then add `except TelegramForbiddenError:` → `await db.set_blocked(self._conn, job.chat_id, True)` (also `logging.info` this so it shows up per FR-008), then a catch-all `except Exception:` → `logging.exception("failed to deliver notification to %s", job.chat_id)`; wrap the `await self._send(bot, job)` call inside `run()`'s `while True` loop in its own `try/except Exception` (logged) as a second, defense-in-depth layer. Confirm all of T004 now passes.
- [X] T006 [US1] In `src/channel_filter/main.py`, update the `Notifier(...)` construction call to pass the open `conn` (`Notifier(channel_username=channel_username, conn=conn)`), matching T005's new constructor signature.

**Checkpoint**: User Story 1 is independently complete — run `uv run pytest tests/unit/test_notifier.py` and quickstart.md §2 to validate.

---

## Phase 4: User Story 2 - A failed component recovers on its own (Priority: P1)

**Goal**: Each of the three long-running components (channel listener, command polling, notification delivery) is independently supervised: an unhandled failure in one is logged and that component restarted after a fixed ~2s delay, without affecting the other two.

**Independent Test**: Unit-test the generic `supervise()` helper, the new Telethon restart wrapper, and the task-construction wiring directly, without a live Telegram connection. End-to-end: quickstart.md §3.

### Tests for User Story 2 ⚠️

> Write these first; confirm each fails for the right reason before implementing.

- [X] T007 [P] [US2] In `tests/unit/test_supervise.py` (new file), with `asyncio.sleep` patched (no real sleeping in tests) and `caplog` available, write four failing tests for a `supervise(name, coro_factory)` helper:
  1. A `coro_factory` whose coroutine raises is invoked again after the patched sleep is awaited with the configured `RESTART_DELAY` (~2.0s) — assert `coro_factory` was called at least twice within a bounded number of test iterations, **and** `caplog` captured a log record naming `name` and the failure (FR-008).
  2. A `coro_factory` whose coroutine returns cleanly is also invoked again (a clean exit still counts as needing restart), and `caplog` captured a log record naming `name` for the restart (FR-008).
  3. Two independent `supervise()` calls running concurrently (`asyncio.gather`): one wrapped coroutine raises repeatedly while the other succeeds on every call — assert the succeeding one's call count keeps advancing normally and is unaffected by the other's failures (FR-006).
  4. A `coro_factory` that raises on three consecutive invocations — assert `asyncio.sleep` was awaited with the *same* `RESTART_DELAY` value every time (not growing/backing off), covering FR-007 and the "fast, repeating failure" edge case in spec.md.
- [X] T008 [US2] Implement `RESTART_DELAY = 2.0` and `async def supervise(name: str, coro_factory: Callable[[], Awaitable[None]]) -> None` in `src/channel_filter/main.py` per research.md's "Decision: Supervision mechanism" (loop forever: run `coro_factory()`; on `Exception`, `logging.exception` naming `name`; on clean return, `logging.warning` naming `name`; always `await asyncio.sleep(RESTART_DELAY)` between attempts, using the same constant every time — no backoff state). Confirm all of T007 now passes.
- [X] T009 [P] [US2] In `tests/unit/test_listener.py` (new file), using fakes/doubles for `build_client` and a fake Telethon client object (recording call order), write a failing test asserting a new `run_listener_forever(...)` coroutine calls, in order: `build_client(...)`, then `client.start()`, then `client.run_until_disconnected()`.
- [X] T010 [US2] Implement `run_listener_forever(api_id, api_hash, source_channel, stages, conn, notifier, channel_username)` (or equivalent signature) in `src/channel_filter/listener.py` that builds a **fresh** client via the existing `build_client(...)` on every call, then `await client.start()`, then `await client.run_until_disconnected()`. Confirm T009 now passes.
- [X] T011 [US2] In `tests/unit/test_main.py`, write a failing test for a new `build_supervised_tasks(...)` function: with `channel_filter.main.supervise` patched to a fake that records `(name, coro_factory)` pairs instead of actually looping, call `build_supervised_tasks(...)` with fakes/doubles standing in for the Telethon client args, `dp`, `aiogram_bot`, and `notifier`, and assert `supervise` was invoked exactly three times with the names `"telethon-listener"`, `"bot-polling"`, `"notifier"` — then, for each recorded `coro_factory`, invoke it against the fakes and assert it routes to `run_listener_forever(...)`, `dp.start_polling(aiogram_bot)`, and `notifier.run(aiogram_bot)` respectively. Confirm it fails because `build_supervised_tasks` doesn't exist yet. Depends on T008 and T010 existing to reference (T007/T009 must be green first).
- [X] T012 [US2] Implement `build_supervised_tasks(...)` in `src/channel_filter/main.py` — a small function returning `[supervise("telethon-listener", lambda: run_listener_forever(...)), supervise("bot-polling", lambda: dp.start_polling(aiogram_bot)), supervise("notifier", lambda: notifier.run(aiogram_bot))]`. Confirm T011 now passes.
- [X] T013 [US2] In `src/channel_filter/main.py`'s `main()`, replace the single `await client.start()` + `await asyncio.gather(client.run_until_disconnected(), dp.start_polling(aiogram_bot), notifier.run(aiogram_bot))` with `await asyncio.gather(*build_supervised_tasks(...))`; remove the now-redundant standalone `build_client(...)`/`client.start()` calls (client construction and startup now happen inside `run_listener_forever` on every supervised attempt). This one-line composition call is already exercised by T011/T012's test of `build_supervised_tasks()`; validate the full wiring end-to-end via quickstart.md §3 (manual component-failure smoke test). Depends on T006 (US1's `Notifier(conn=...)` call site) and T012.

**Checkpoint**: User Stories 1 AND 2 both work independently — run `uv run pytest tests/unit/test_supervise.py tests/unit/test_listener.py tests/unit/test_main.py` and quickstart.md §3.

---

## Phase 5: User Story 3 - A total failure is never invisible (Priority: P2)

**Goal**: If a failure ever escapes all per-component supervision, the process terminates promptly instead of hanging in a running-but-inert state, so systemd's `Restart=on-failure` is a guaranteed last resort.

**Independent Test**: Unit-test the top-level wrapper directly by making `main()` raise. End-to-end: quickstart.md §4.

### Tests for User Story 3 ⚠️

> Write this first; confirm it fails for the right reason before implementing.

- [X] T014 [P] [US3] In `tests/unit/test_main.py`, write a failing test for a new `run()` function: patch `channel_filter.main.main` to raise an exception, patch `os._exit` (assert it is called with `1`) and `logging.shutdown` (assert it is called before `os._exit`), and assert a `CRITICAL` log record is emitted (via `caplog`) before the process-exit call.

### Implementation for User Story 3

- [X] T015 [US3] In `src/channel_filter/main.py`, extract a `def run() -> None:` that does `try: asyncio.run(main()) except Exception: logging.critical("unrecoverable failure escaped all supervisors", exc_info=True); logging.shutdown(); os._exit(1)`, and change the `if __name__ == "__main__":` block to call `run()`. Confirm T014 now passes.

**Checkpoint**: All three user stories are independently functional — run `uv run pytest tests/unit/test_main.py` and quickstart.md §4.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T016 [P] Walk through `specs/003-error-resilience/quickstart.md` §2, §3, and §4 manually (real bot token/test channel) and record the outcome of each; revert any temporary code used to force the §4 scenario before committing.
- [X] T017 Run `uv run pytest` for the full suite (existing + all new tests) and confirm everything passes cleanly, satisfying the constitution's task-completion gate.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (their log calls rely on `configure_logging()`).
- **User Story 1 (Phase 3)**: Depends on Foundational only. Independent of US2/US3.
- **User Story 2 (Phase 4)**: T007/T009 depend on Foundational only (independently testable), as do their implementations T008/T010. T011 depends on T008 and T010 (it exercises both). T012 depends on T011. T013 (the `main.py` wiring task) additionally depends on US1's T006, since both edit the same `main()` body and T013 assumes T006's `Notifier(conn=...)` call site already exists.
- **User Story 3 (Phase 5)**: Depends on Foundational only. Independent of US1/US2.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each Story

- Tests MUST be written and observed failing before their paired implementation task (constitution RED-GREEN-REFACTOR) — this now applies uniformly, including the `main.py` wiring step (T011 → T012, then T013).
- T004 → T005 → T006 (US1)
- T007 → T008; T009 → T010; T011 (needs T008, T010) → T012; then T013 (needs T006, T012) (US2)
- T014 → T015 (US3)

### Parallel Opportunities

- T004 (US1), T007 & T009 (US2), T014 (US3) touch independent new files and only depend on Phase 2 — they can be written in parallel (e.g., by different people, or across sessions).
- Within US2, T007 and T009 are independent of each other (different files, different concerns) and can proceed in parallel; T011 is not parallel with them (it depends on both T008 and T010 being implemented first).
- T016 (manual quickstart pass) can run alongside T017 (automated suite run) once all stories are implemented.

---

## Parallel Example: Story Kickoff (after Phase 2)

```bash
# These can start together, each in an independent file (test_main.py
# already exists from Foundational T002; T014 adds a new, non-conflicting
# test function to it — no US2 test targets test_main.py at kickoff time,
# since T011 depends on T008/T010 and isn't part of this first wave):
Task: "Write failing Notifier resilience tests in tests/unit/test_notifier.py"      # T004 (US1)
Task: "Write failing supervise() tests in tests/unit/test_supervise.py"             # T007 (US2)
Task: "Write failing run_listener_forever() test in tests/unit/test_listener.py"    # T009 (US2)
Task: "Write failing top-level safety-net test in tests/unit/test_main.py"          # T014 (US3)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and VALIDATE**: `uv run pytest tests/unit/test_notifier.py`, then quickstart.md §2 against a real test bot.
3. This alone fixes the exact production incident (a blocked subscriber can no longer take down the whole bot) and is deployable on its own.

### Incremental Delivery

1. Setup + Foundational → logging ready.
2. US1 → blocked/failed deliveries no longer crash anything → validate → deployable.
3. US2 → every component self-heals within seconds of any other failure → validate → deployable.
4. US3 → the last-resort backstop that guarantees a truly unrecoverable failure is never invisible → validate → deployable.
5. Polish → full manual + automated validation pass.

### Notes

- All tests use real `aiosqlite` connections (`conn` fixture) and hand-written dataclass fakes for `Bot`/Telethon client objects, following the existing pattern in `tests/unit/doubles.py` and `tests/integration/test_pipeline_to_notifier.py` — assert against real DB state and recorded fake calls, never against internal mock call counts alone (constitution: "Assert Behavior, Not Mocks").
- Commit after each task or logical group; stop at any checkpoint to validate a story independently before moving on.
- **Revision history**: 2026-09-15, after `/speckit-analyze` — inserted T011/T012 (`build_supervised_tasks()` test + implementation) and renumbered everything from the old T011 onward (old T011→T013, old T012→T014, old T013→T015, old T014→T016, old T015→T017) to close finding C1 (the `main.py` wiring step previously had no preceding failing test, violating the constitution's non-negotiable RED-GREEN-REFACTOR gate); added `caplog` assertions to T004 and T007 to close finding E1 (FR-008 log coverage); added T007's 4th case to close finding E2 (FR-007 steady-pace coverage).
