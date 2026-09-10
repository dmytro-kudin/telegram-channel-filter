---

description: "Task list for feature implementation"
---

# Tasks: Channel Keyword Filter

**Input**: Design documents from `/specs/001-channel-keyword-filter/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/ (bot-commands.md, admin-commands.md, pipeline-stage-contract.md), research.md, quickstart.md

**Tests**: Required — `.specify/memory/constitution.md`'s Development Workflow section mandates a strict RED-GREEN-REFACTOR cycle for every task: a failing test MUST exist and be confirmed failing before the corresponding production code is written. Test files below follow exactly the set named in plan.md's Project Structure (`test_pipeline.py`, `test_matcher.py`, `test_db.py`, `test_auth.py`, `test_bot_commands.py`, `test_pipeline_to_notifier.py`); wiring-only modules (`listener.py`, `main.py`) and simple data/config modules (`types.py`, `config.py`, `messages.py`) are not given dedicated unit test files, consistent with plan.md's structure and quickstart.md's note that only setup/manual scenarios need real Telegram credentials.

**Organization**: Tasks are grouped by user story (numbered as in spec.md) to enable independent implementation and testing of each story. Phases are ordered by story priority (P1 → P2 → P3), not by story number.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US9, matching spec.md's numbering)
- Include exact file paths in descriptions

## Path Conventions

Single project per plan.md: `src/channel_filter/`, `tests/unit/`, `tests/integration/`, `deploy/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure: `src/channel_filter/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`; add `.gitignore` entries for `.env`, `*.session`, `*.db`
- [ ] T002 Initialize Python project in `pyproject.toml` with dependencies: `telethon`, `aiogram`, `pyahocorasick`, `aiosqlite`, `python-dotenv`, and dev dependencies `pytest`, `pytest-asyncio` (per plan.md Technical Context)
- [ ] T003 Configure pytest for async tests in `pyproject.toml` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] Define core domain types (`Subscriber` incl. `active`/`blocked`, `Keyword`, `ChannelPost`, `Outcome` variants `Skip`/`BroadcastAll`/`MatchedUsers`/`Continue`) in `src/channel_filter/types.py` (data-model.md)
- [ ] T005 [P] Implement `.env` config loader (`API_ID`, `API_HASH`, `BOT_TOKEN`, `SOURCE_CHANNEL`, `ADMIN_CHAT_ID`, `DB_PATH`) in `src/channel_filter/config.py`
- [ ] T006 [P] Create the single Ukrainian bot-reply message template module (FR-025) in `src/channel_filter/messages.py`
- [ ] T007 Implement SQLite connection helper and schema creation (`subscribers(chat_id, active, blocked)`, `keywords(id, chat_id, substring)` with `UNIQUE(chat_id, substring)` and `ON DELETE CASCADE`; set `PRAGMA foreign_keys = ON` on every connection) in `src/channel_filter/db.py` (data-model.md Schema)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Get Notified When a Post Matches Your Keyword (Priority: P1) 🎯 MVP

**Goal**: A subscriber registers, adds a keyword, and is notified (with post text + link) exactly once when a channel post contains it.

**Independent Test**: Register a fresh subscriber, add one keyword, publish a channel post containing that keyword, confirm exactly one notification referencing that post arrives.

### Tests for User Story 1 ⚠️ (write first, confirm they FAIL)

- [ ] T008 [P] [US1] Write failing tests for `get_or_create_subscriber` (registers with `active=True`) and `add_keyword` (valid add succeeds; rejects `<3` chars per FR-002) in `tests/unit/test_db.py`
- [ ] T009 [P] [US1] Write failing tests for `AutomatonManager` build/rebuild/atomic-swap, restricted to eligible (`active AND NOT blocked`) subscribers' keywords, in `tests/unit/test_matcher.py`
- [ ] T010 [P] [US1] Write failing tests for `keyword_match_stage` and the pipeline runner's short-circuit contract (single keyword match, multi-keyword/multi-match same post → one `MatchedUsers` entry per subscriber not one per match, no match → empty) in `tests/unit/test_pipeline.py`
- [ ] T011 [P] [US1] Write failing tests for `/start` (registration, always-success reply) and `/add` (success reply, too-short reply) handlers against a stubbed db in `tests/unit/test_bot_commands.py`
- [ ] T012 [P] [US1] Write failing integration test asserting a matched `ChannelPost` enqueues exactly one `NotificationJob` per matching subscriber, even with multiple matching keywords, in `tests/integration/test_pipeline_to_notifier.py`

### Implementation for User Story 1

- [ ] T013 [US1] Implement `get_or_create_subscriber` and `add_keyword` (min-length validation only) in `src/channel_filter/db.py` (depends on T004, T007; satisfies T008)
- [ ] T014 [US1] Implement `AutomatonManager` (build/rebuild off to the side via `await asyncio.to_thread(automaton.make_automaton)` — `make_automaton()` is a synchronous, CPU-bound C call and MUST NOT be invoked directly from an `async def`, per constitution Coding Standards and research.md §4's compliance note — then an atomic reference swap, with an `asyncio.Lock` around rebuild triggers) in `src/channel_filter/matcher.py` (depends on T004, T007; satisfies T009)
- [ ] T015 [US1] Implement the pipeline runner (ordered stage list, first-non-`Continue`-wins) and `keyword_match_stage` (lowercases the post's text before the automaton lookup for case-insensitive matching per FR-004/FR-007, then always resolves via the automaton) in `src/channel_filter/pipeline.py` (depends on T004, T014; satisfies T010)
- [ ] T016 [US1] Implement `NotificationJob`, the `asyncio.Queue`, and a token-bucket sender (~25 msg/sec) with `TelegramRetryAfter` requeue-and-retry in `src/channel_filter/notifier.py` (depends on T004; satisfies T012)
- [ ] T017 [US1] Implement Telethon `NewMessage` listener wiring (build `ChannelPost`, run pipeline, resolve `MatchedUsers` to enqueued jobs with a "🔗 View original" link to `https://t.me/<channel_username>/<message_id>`) in `src/channel_filter/listener.py` (depends on T015, T016)
- [ ] T018 [US1] Implement `/start` and `/add` aiogram handlers in `src/channel_filter/bot.py` (depends on T006, T013, T014; satisfies T011)
- [ ] T019 [US1] Wire application startup (open DB, init schema, build initial automaton, run Telethon client and aiogram polling concurrently via `asyncio.gather`) in `src/channel_filter/main.py` (depends on T005, T017, T018)

**Checkpoint**: User Story 1 is fully functional and independently testable (MVP) — matching, single-notification dedup, and delivery all work end-to-end.

---

## Phase 4: User Story 2 - Manage Your Personal Keyword List (Priority: P2)

**Goal**: A subscriber views their keyword list and removes entries; duplicate adds and the 20-keyword cap are handled gracefully.

**Independent Test**: With two saved keywords, `/list` shows both; remove one, `/list` shows only the other and it stops matching.

### Tests for User Story 2 ⚠️

- [ ] T020 [P] [US2] Write failing tests for `list_keywords`, `remove_keyword` (not-found case, FR-006), `add_keyword` case-insensitive dedup (no-op + confirm, FR-004), and the 20-keyword cap rejection (FR-003) in `tests/unit/test_db.py`
- [ ] T021 [P] [US2] Write failing tests for `/list` and `/remove` handlers, and updated `/add` replies (already-exists, limit-reached), in `tests/unit/test_bot_commands.py`

### Implementation for User Story 2

- [ ] T022 [US2] Implement `list_keywords` and `remove_keyword` in `src/channel_filter/db.py` (depends on T013; satisfies the list/remove cases of T020)
- [ ] T023 [US2] Extend `add_keyword` with case-insensitive dedup no-op and 20-keyword cap rejection in `src/channel_filter/db.py` (depends on T013; satisfies the remaining T020 cases)
- [ ] T024 [US2] Implement `/list` and `/remove` handlers, update `/add` replies, and trigger an automaton rebuild on remove, in `src/channel_filter/bot.py` (depends on T018, T022, T023, T014; satisfies T021)

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Pause and Resume Alerts (Priority: P2)

**Goal**: A subscriber pauses notifications without losing their keyword list, then resumes with everything intact.

**Independent Test**: Pause an active subscriber with saved keywords, confirm a matching post delivers nothing, resume, confirm delivery restarts with no re-entry.

### Tests for User Story 3 ⚠️

- [ ] T025 [P] [US3] Write failing tests for `set_active(chat_id, bool)` and the eligibility-filtered automaton rebuild on active-state change (rebuilding via `AutomatonManager.rebuild()` from T014, which already re-reads `active`/`blocked` from the DB — no additional matcher.py logic is needed for this case) in `tests/unit/test_db.py` and `tests/unit/test_matcher.py`
- [ ] T026 [P] [US3] Write failing tests for `/stop` (pauses, keywords untouched) and `/start`'s resume behavior (existing keywords immediately active again) in `tests/unit/test_bot_commands.py`

### Implementation for User Story 3

- [ ] T027 [US3] Implement `set_active` in `src/channel_filter/db.py` (depends on T007; satisfies the db cases of T025)
- [ ] T028 [US3] Implement `/stop` handler and update `/start` to resume (`set_active True`, then rebuild via `AutomatonManager.rebuild()` from T014 — no additional matcher.py code is needed since eligibility is re-read from the DB on every rebuild) in `src/channel_filter/bot.py` (depends on T018, T027; satisfies T026 and the matcher-rebuild cases of T025)

**Checkpoint**: User Stories 1, 2, and 3 all work independently.

---

## Phase 6: User Story 6 - Permanently Delete My Data (Priority: P2)

**Goal**: A subscriber permanently erases their account and all keywords; a later interaction starts fresh.

**Independent Test**: Request deletion for a subscriber with saved keywords, confirm keywords are gone and matches stop, then re-interact and confirm they're a brand-new subscriber.

### Tests for User Story 6 ⚠️

- [ ] T029 [P] [US6] Write failing tests for `delete_subscriber` (cascades to all keyword rows; safe no-op when the subscriber was never registered) in `tests/unit/test_db.py`
- [ ] T030 [P] [US6] Write failing tests for `/deleteme` (always succeeds unconditionally, confirms a future `/start` begins fresh) in `tests/unit/test_bot_commands.py`

### Implementation for User Story 6

- [ ] T031 [US6] Implement `delete_subscriber` (cascading delete via `ON DELETE CASCADE`, safe no-op if missing) in `src/channel_filter/db.py` (depends on T007; satisfies T029)
- [ ] T032 [US6] Implement `/deleteme` handler with an automaton rebuild afterward in `src/channel_filter/bot.py` (depends on T018, T031, T014; satisfies T030)

**Checkpoint**: User Stories 1, 2, 3, and 6 all work independently.

---

## Phase 7: User Story 7 - Operator Blocks an Abusive Subscriber (Priority: P2)

**Goal**: The operator blocks a subscriber, immediately cutting off all delivery and command access (except `/deleteme`), and can later unblock them.

**Independent Test**: Block a test subscriber, confirm they receive nothing and their commands are refused; unblock and confirm normal behavior returns.

### Tests for User Story 7 ⚠️

- [ ] T033 [P] [US7] Write failing tests for `require_operator` (accepts `ADMIN_CHAT_ID`, refuses everyone else, FR-018) and `refuse_if_blocked` decorators in `tests/unit/test_auth.py`
- [ ] T034 [P] [US7] Write failing tests for `set_blocked` (block/unblock preserves the subscriber's prior `active` value, FR-022) and its effect on automaton eligibility in `tests/unit/test_db.py`
- [ ] T035 [P] [US7] Write failing tests for `/block`, `/unblock` admin handlers and for blocked-subscriber command refusal (every command except `/deleteme`) in `tests/unit/test_bot_commands.py`

### Implementation for User Story 7

- [ ] T036 [US7] Implement `require_operator` and `refuse_if_blocked` decorators in `src/channel_filter/auth.py` (depends on T005, T006; satisfies T033)
- [ ] T037 [US7] Implement `set_blocked` in `src/channel_filter/db.py` (depends on T007; satisfies T034)
- [ ] T038 [US7] Implement `/block` and `/unblock` admin handlers (wrapped in `require_operator`, triggers automaton rebuild) in `src/channel_filter/bot.py` (depends on T036, T037, T014)
- [ ] T039 [US7] Apply the `refuse_if_blocked` decorator to `/start`, `/add`, `/remove`, `/list`, `/stop` handlers in `src/channel_filter/bot.py` (depends on T036, T018, T024, T028; satisfies T035)

**Checkpoint**: User Stories 1, 2, 3, 6, and 7 all work independently.

---

## Phase 8: User Story 4 - Guaranteed Delivery of Jar-Link Announcements (Priority: P3)

**Goal**: Any post containing the designated jar link reaches every active, non-blocked subscriber, regardless of their keywords.

**Independent Test**: Publish a jar-link post with subscribers who have no matching keywords; confirm every active subscriber receives it and a paused one does not.

### Tests for User Story 4 ⚠️

- [ ] T040 [P] [US4] Write failing tests for `jar_link_stage` (`BroadcastAll` when the designated pattern is present, `Continue` otherwise) in `tests/unit/test_pipeline.py`

### Implementation for User Story 4

- [ ] T041 [US4] Implement `jar_link_stage` and insert it first in the pipeline's ordered stage list, without modifying `keyword_match_stage`'s body, in `src/channel_filter/pipeline.py` (depends on T015; satisfies T040)
- [ ] T042 [US4] Resolve a `BroadcastAll` outcome against a fresh eligible-subscriber (`active=1 AND blocked=0`) query and enqueue notifier jobs in `src/channel_filter/listener.py` (depends on T017, T041, T007)

**Checkpoint**: Jar-link posts reach every active subscriber regardless of personal keywords; existing stages unaffected.

---

## Phase 9: User Story 5 - Suppress Bare-Number Noise (Priority: P3)

**Goal**: Posts whose entire content is only a number produce zero notifications, without affecting normal matching for posts that merely contain a number.

**Independent Test**: Publish a post that is only digits (with a numeric keyword saved); confirm nothing is sent. Publish a post with that same number plus other text; confirm normal matching applies.

### Tests for User Story 5 ⚠️

- [ ] T043 [P] [US5] Write failing tests for `pure_number_stage` (`Skip` when stripped text is only digits/numeric punctuation, `Continue` otherwise) in `tests/unit/test_pipeline.py`

### Implementation for User Story 5

- [ ] T044 [US5] Implement `pure_number_stage` and insert it between `jar_link_stage` and `keyword_match_stage` in the ordered list, without modifying either existing stage's body, in `src/channel_filter/pipeline.py` (depends on T041; satisfies T043)

**Checkpoint**: All five priority stories (1, 2, 3, 6, 7) plus the jar-link and bare-number rules are independently functional.

---

## Phase 10: User Story 8 - Operator Sends a Manual Broadcast (Priority: P3)

**Goal**: The operator sends an arbitrary message to every active, non-blocked subscriber, independent of any channel post.

**Independent Test**: Send a broadcast; confirm every active, non-blocked subscriber receives it, a paused/blocked one does not, and a non-operator cannot trigger it.

### Tests for User Story 8 ⚠️

- [ ] T045 [P] [US8] Write failing tests for `/broadcast` (enqueues one job per currently eligible subscriber; refused for a non-operator) in `tests/unit/test_bot_commands.py`

### Implementation for User Story 8

- [ ] T046 [US8] Implement `/broadcast` admin handler (wrapped in `require_operator`, fresh eligible-subscriber query, enqueue via the notifier queue — no `ChannelPost`/pipeline involved) in `src/channel_filter/bot.py` (depends on T036, T016, T007; satisfies T045)

**Checkpoint**: Broadcast reaches only active, non-blocked subscribers.

---

## Phase 11: User Story 9 - Operator Views Subscriber Stats (Priority: P3)

**Goal**: The operator sees the total subscriber count and the active/paused/blocked breakdown.

**Independent Test**: Register a few subscribers, pause one and block another, request stats, confirm the counts match.

### Tests for User Story 9 ⚠️

- [ ] T047 [P] [US9] Write failing tests for `get_subscriber_stats` (total count plus active/paused/blocked breakdown) in `tests/unit/test_db.py`
- [ ] T048 [P] [US9] Write failing tests for `/stats` admin handler (correct breakdown reply; refused for a non-operator) in `tests/unit/test_bot_commands.py`

### Implementation for User Story 9

- [ ] T049 [US9] Implement `get_subscriber_stats` query in `src/channel_filter/db.py` (depends on T007; satisfies T047)
- [ ] T050 [US9] Implement `/stats` admin handler in `src/channel_filter/bot.py` (depends on T036, T049; satisfies T048)

**Checkpoint**: All 9 user stories are independently functional.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final subscriber-facing piece, durability verification, deployment, and end-to-end validation once the full command set exists

- [ ] T051 [P] Write failing test for `/help` (lists all subscriber-facing commands per contracts/bot-commands.md, admin commands excluded) in `tests/unit/test_bot_commands.py`
- [ ] T052 [P] Implement `/help` handler in `src/channel_filter/bot.py` (depends on T006, T018; satisfies T051)
- [ ] T053 [P] Register the bot's subscriber-facing command menu via `set_my_commands` during startup in `src/channel_filter/main.py`
- [ ] T054 Run all quickstart.md validation scenarios end-to-end against a real Telegram bot/channel
- [ ] T055 [P] Write a systemd unit file (`deploy/channel-filter.service`: `ExecStart=python -m channel_filter.main`, `EnvironmentFile=` pointing at `.env`, `Restart=on-failure`, `WantedBy=multi-user.target`) for auto-restart on crash or reboot (plan.md Constraints, research.md §8)
- [ ] T056 Provision the Oracle Cloud Always-Free VM (`VM.Standard.E2.1.Micro` shape), place the SQLite DB file, Telethon `.session` file, and `.env` on the VM's persistent boot volume, install and enable the systemd unit from T055, and confirm outbound-only networking (HTTPS + MTProto) requires no security-list changes (research.md §8)
- [ ] T057 [P] Write a failing test asserting subscriber/keyword state (including `active`/`blocked` flags) survives closing and reopening the aiosqlite connection against the same `DB_PATH` (simulating a process/VM restart) in `tests/unit/test_db.py`, then confirm it passes against the existing `db.py` implementation with no new production code required — the guarantee already comes from writing to a persistent file-backed DB (T007) rather than `:memory:` (depends on T007, T013, T027, T037; validates FR-015/SC-007)
- [ ] T058 Add a manual restart-survival validation scenario to quickstart.md (stop the running bot process, restart it — or, once deployed, reboot the Oracle Cloud VM — and confirm `/list` and pause state are unchanged with no reconfiguration) (depends on T057)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3–11)**: All depend on Foundational phase completion; implemented in priority order (P1 → P2 → P3) below, though most are independently startable once Foundational is done
  - Phase 3 (US1, P1) - MVP, no dependency on other stories
  - Phase 4 (US2, P2) - depends on US1's `add_keyword`/`bot.py` scaffolding (T013, T018)
  - Phase 5 (US3, P2) - depends on Foundational + US1's `bot.py`/`matcher.py` scaffolding (T018, T014)
  - Phase 6 (US6, P2) - depends on Foundational + US1's `bot.py` scaffolding (T018)
  - Phase 7 (US7, P2) - depends on US2 and US3's handlers existing to apply `refuse_if_blocked` to (T024, T028)
  - Phase 8 (US4, P3) - depends on US1's pipeline runner (T015, T017)
  - Phase 9 (US5, P3) - depends on US4's stage insertion (T041)
  - Phase 10 (US8, P3) - depends on US7's `require_operator` (T036) and US1's notifier (T016)
  - Phase 11 (US9, P3) - depends on US7's `require_operator` (T036)
- **Polish (Phase 12)**: Depends on all user stories being complete (needs the full command set for `/help`). T056 (VM provisioning/deployment) additionally depends on T055 (systemd unit) and T019 (`main.py` startup wiring) existing. T057 (restart-survival test, validates FR-015/SC-007) depends on T007, T013, T027, and T037 (so both `active` and `blocked` flags are exercised); T058 (quickstart restart-survival scenario) depends on T057.

### Within Each User Story

- Tests MUST be written and confirmed FAILING before implementation (constitution TDD gate)
- db.py functions before matcher/pipeline before bot.py handlers before main.py wiring
- Story complete and checkpoint-verified before moving to the next priority phase

### Parallel Opportunities

- Foundational tasks T004–T006 (different files) can run in parallel; T007 follows
- All test-writing tasks marked [P] within a phase (different files) can run in parallel
- Once Foundational completes, US1 must land first (MVP, everything else's `bot.py`/`matcher.py` scaffolding depends on it); after that, US2/US3/US6 can proceed in parallel (different db.py functions, converging only on shared `bot.py` edits)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: "Write failing tests for get_or_create_subscriber/add_keyword in tests/unit/test_db.py"
Task: "Write failing tests for AutomatonManager in tests/unit/test_matcher.py"
Task: "Write failing tests for keyword_match_stage/pipeline runner in tests/unit/test_pipeline.py"
Task: "Write failing tests for /start and /add handlers in tests/unit/test_bot_commands.py"
Task: "Write failing integration test for pipeline-to-notifier dedup in tests/integration/test_pipeline_to_notifier.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run quickstart.md scenario 1 against a real bot/channel
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → validate independently → MVP demo
3. US2, US3, US6 (all P2, keyword-list/pause/delete) → validate each independently
4. US7 (P2, operator block) → validate independently
5. US4, US5 (P3, jar-link/bare-number rules) → validate each independently
6. US8, US9 (P3, broadcast/stats) → validate each independently
7. Polish (`/help`, command menu registration) → full quickstart.md run
8. Deploy (T055–T056) → systemd unit written, Oracle Cloud Always-Free VM provisioned and running the service, persistent volume holding the DB/session files
9. Verify restart-survival (T057–T058) → confirm subscriber/keyword/pause/blocked state survives a simulated restart and, once deployed, an actual VM reboot

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability (spec.md numbering, not phase order)
- Per the constitution's TDD gate, a checkbox may only flip to `[x]` after RED (test written, confirmed failing) → GREEN (minimal code, test passes) → REFACTOR, with `pytest` passing cleanly
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
