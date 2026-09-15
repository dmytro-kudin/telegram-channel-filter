# Quickstart: Validating Runtime Error Resilience

Prerequisites: repo checked out on branch `003-error-resilience`, `.venv`
set up (`uv sync`), feature implemented per `tasks.md`.

## 1. Automated tests (primary validation)

```bash
uv run pytest
```

Expect, in addition to all existing tests still passing:

- `tests/unit/test_notifier.py`
  - A job whose send raises `TelegramForbiddenError` results in
    `db.set_blocked(conn, chat_id, True)` being called, and the next queued
    job still gets sent (queue not stuck) — covers spec.md User Story 1,
    acceptance scenarios 1–2.
  - A job whose send raises an arbitrary/unrecognized exception is dropped
    (not requeued forever) and the next queued job still gets sent.
- `tests/unit/test_supervise.py`
  - A wrapped coroutine that raises is logged and re-invoked after the
    configured restart delay (use a fake clock / patched `asyncio.sleep` —
    do not sleep for real in the test suite).
  - A wrapped coroutine that returns cleanly is also re-invoked (a
    component exiting is still treated as needing restart).
  - Two independent `supervise()` calls: one wrapped coroutine raising
    does not affect the other's execution — covers spec.md User Story 2's
    "failure in one component MUST NOT interrupt... the others."

## 2. Manual smoke test — blocked subscriber never stops the queue

This validates User Story 1 end-to-end against a real (test) Telegram bot,
since the actual Telegram API behavior isn't something the unit tests
exercise.

1. Run the bot locally (`uv run python -m channel_filter.main`) against a
   test bot token and a test channel, with at least two subscribed test
   accounts.
2. From one test account, block the bot in Telegram.
3. Post a message in the source channel that matches both accounts'
   keywords (or triggers a broadcast).
4. **Expected**: the non-blocking account still receives the notification.
   The bot process keeps running (check `ps`/logs — no crash, no restart
   log line). Query `channel_filter.db`'s `subscribers` table and confirm
   the blocking account's row now has `blocked = 1`.
5. Post another matching message. **Expected**: no delivery attempt is
   made to the blocked account (no new forbidden-error log line for it).

## 3. Manual smoke test — component auto-recovery

Validates User Story 2.

1. Run the bot locally.
2. Deliberately break one component to force an exception on its next
   operation — e.g., temporarily revoke/rotate the bot token to force the
   aiogram polling component to fail, or briefly block outbound network
   access to Telegram's servers to force the Telethon listener to fail.
3. **Expected**: a log line naming the failed component appears, followed
   within ~2–10 seconds by a log line indicating it restarted. The *other*
   two components continue operating throughout — e.g., if you broke
   polling, the channel listener keeps forwarding matching posts to the
   notifier the whole time.
4. Restore the broken dependency (token/network) and confirm the recovered
   component resumes normal operation without a manual process restart.

## 4. Manual smoke test — process exits if recovery is impossible

Validates User Story 3 / FR-009. This is a last-resort backstop and
expected to be hard to trigger deliberately without temporarily modifying
code; treat as an implementation-time check rather than a repeatable
regression test:

1. Temporarily make the top-level safety net's guarded region raise (e.g.,
   momentarily have `main()` itself raise before entering the supervised
   `gather()`, simulating a failure that bypasses all three supervisors).
2. **Expected**: a `CRITICAL` log line is emitted, and the process exits
   immediately (check the exit code / that the OS process is gone) rather
   than continuing to run. Under systemd, confirm
   `systemctl status channel-filter` subsequently shows a restart
   (`NRestarts` incremented) rather than the process hanging as it did
   during the original incident.
3. Revert the temporary change before committing.

## Reference

- Functional requirements: [spec.md](./spec.md#functional-requirements)
- Success criteria: [spec.md](./spec.md#measurable-outcomes)
- Technical decisions and rationale: [research.md](./research.md)
- Data/state touched: [data-model.md](./data-model.md)
