---

description: "Task list for feature implementation"
---

# Tasks: Button-Driven Subscriber UX & Admin Discoverability

**Input**: Design documents from `/specs/002-button-driven-ux/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/ (button-menu.md, add-flow.md, keyword-deletion.md, admin-help.md), research.md, quickstart.md

**Tests**: Required — `.specify/memory/constitution.md`'s Development Workflow section mandates a strict RED-GREEN-REFACTOR cycle for every task: a failing test MUST exist and be confirmed failing before the corresponding production code is written. Test files below follow plan.md's Project Structure: `test_keyboards.py` is new; `test_bot_commands.py` and `test_db.py` are extended from 001. `main.py` and `config.py` need no changes for this feature (plan.md Constraints — aiogram's `Dispatcher()` already defaults to in-memory FSM storage), so they have no dedicated tasks here.

**Organization**: Tasks are grouped by user story (numbered as in spec.md) to enable independent implementation and testing of each story. Phases are ordered by story priority (P1 → P2), matching spec.md's own story order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5, matching spec.md's numbering)
- Include exact file paths in descriptions

## Path Conventions

Single project per plan.md: `src/channel_filter/`, `tests/unit/` at repository root — same layout as 001, no new top-level directories.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

No setup tasks are required. This feature adds no new dependency, no new
config, and no new project scaffolding — it extends the existing
`src/channel_filter/` package (plan.md Technical Context: aiogram's
`ReplyKeyboardMarkup`/`KeyboardButton`/`InlineKeyboardBuilder`/FSM are
already available under the pinned `aiogram>=3.4` in `pyproject.toml`). Work
starts at Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T001 [P] Write failing tests for `keyboards.subscriber_menu(active: bool) -> ReplyKeyboardMarkup` (returns ➕ Додати слово / 📋 Мої слова / ❓ Довідка plus ⏸ Призупинити when `active=True` or ▶️ Відновити when `active=False`) in `tests/unit/test_keyboards.py`
- [X] T002 Implement `keyboards.py` module and `subscriber_menu` in `src/channel_filter/keyboards.py` (contracts/button-menu.md; depends on T001; satisfies T001)

**Checkpoint**: Foundation ready — the shared, independently-tested persistent-menu builder exists; every user story below attaches it to replies.

---

## Phase 3: User Story 1 - Navigate the Bot Without Typing Commands (Priority: P1) 🎯 MVP

**Goal**: A persistent menu is visible on every reply; tapping 📋 or ❓ reproduces the exact outcome of typing `/list` or `/help`; every typed command keeps working untouched.

**Independent Test**: Start a conversation, confirm the menu is visible without typing anything, tap 📋 and ❓ and confirm each matches its typed-command outcome, then type a command directly and confirm it still works.

### Tests for User Story 1 ⚠️ (write first, confirm they FAIL)

- [X] T003 [US1] Write failing tests for message handlers on exact button text "📋 Мої слова" (delegates to `list_handler`) and "❓ Довідка" (delegates to `help_handler`), and for `keyboards.subscriber_menu(subscriber.active)` being attached as `reply_markup` on every subscriber-facing reply (`/start`, `/add`, `/list`, `/remove`, `/stop`, `/deleteme`, `/help`), in `tests/unit/test_bot_commands.py`

### Implementation for User Story 1

- [X] T004 [US1] Register message handlers for button text "📋 Мої слова" → `list_handler` and "❓ Довідка" → `help_handler`, and attach `keyboards.subscriber_menu(subscriber.active)` as `reply_markup` to every subscriber-facing reply, in `src/channel_filter/bot.py` (contracts/button-menu.md; depends on T002; satisfies T003)

**Checkpoint**: User Story 1 is fully functional and independently testable — the menu is visible everywhere, 📋/❓ buttons work, typed commands are unaffected.

---

## Phase 4: User Story 2 - Add Multiple Keywords at Once (Priority: P1)

**Goal**: Tapping ➕ prompts for word(s); one or more comma-separated words (guided or typed) are each evaluated independently with a clear per-word outcome.

**Independent Test**: Tap ➕, send a mix of a valid new word, a duplicate, and a too-short word in one message, and confirm each gets its own correct outcome; repeat via typed `/add` directly.

### Tests for User Story 2 ⚠️

- [X] T005 [US2] Write failing tests for the shared comma-parsing helper (split on `,`, strip whitespace, drop empty pieces, independent per-word evaluation including the cap being reached mid-batch) in `tests/unit/test_bot_commands.py`
- [X] T006 [US2] Write failing tests for typed `/add word1, word2[, ...]` producing a per-word outcome summary reply (FR-006) in `tests/unit/test_bot_commands.py`
- [X] T007 [US2] Write failing tests for the guided add flow — ➕ prompts for input, the next message is parsed via the shared helper regardless of its content, the per-word summary is replied, the awaiting-input state is cleared unconditionally afterward, and a different button/command received first abandons the flow cleanly (FR-004/FR-005, Edge Cases) — in `tests/unit/test_bot_commands.py`

### Implementation for User Story 2

- [X] T008 [US2] Implement the shared comma-parsing helper and per-word reply formatter in `src/channel_filter/bot.py` (contracts/add-flow.md; satisfies T005)
- [X] T009 [US2] Update the `/add` handler to use the shared helper for comma-separated input in `src/channel_filter/bot.py` (depends on T008; satisfies T006)
- [X] T010 [US2] Add an `AddKeywords` FSM `StatesGroup`, register the ➕ Додати слово button handler (prompts and enters `AddKeywords.waiting`), and register the guided-input message handler (parses via the shared helper, clears the state unconditionally after processing) in `src/channel_filter/bot.py` (depends on T002, T008; satisfies T007)

**Checkpoint**: User Stories 1 and 2 both work independently — adding one or many keywords works via both the guided and typed paths with correct per-word reporting.

---

## Phase 5: User Story 3 - Remove a Keyword by Tapping It (Priority: P2)

**Goal**: 📋 renders the keyword list as tappable buttons; tapping one asks for Yes/Cancel confirmation before deleting it; a stale tap is handled gracefully.

**Independent Test**: With two saved keywords, tap 📋, tap one keyword, confirm the Yes/Cancel prompt, cancel and confirm nothing changed, then confirm again and verify it's gone while the other keyword and its notifications are untouched.

### Tests for User Story 3 ⚠️

- [X] T011 [P] [US3] Update the existing `list_keywords` test in `tests/unit/test_db.py` to assert it returns `list[Keyword]` (id + substring, not bare strings — an intentional breaking change for this feature, data-model.md), and add new failing tests for `remove_keyword_by_id` (`Removed`/`NotFound` outcomes)
- [X] T012 [P] [US3] Write failing tests for `keyboards.keyword_list_keyboard` (one button per keyword, `callback_data` encodes its id) and `keyboards.delete_confirm_keyboard` (Yes/Cancel, `callback_data` encodes the id) in `tests/unit/test_keyboards.py`
- [X] T013 [P] [US3] Write failing tests for the keyword-list callback flow: tap a keyword → confirm prompt; Yes → deletes via `remove_keyword_by_id`, rebuilds the automaton, shows the refreshed list; Cancel → reverts to the plain list; stale tap (already removed) → "already removed" toast + refreshed list, in `tests/unit/test_bot_commands.py`

### Implementation for User Story 3

- [X] T014 [US3] Change `list_keywords` to return `list[Keyword]` (update the `list_handler` call site to read `.substring`) and add `remove_keyword_by_id` in `src/channel_filter/db.py` (data-model.md; depends on T011; satisfies T011)
- [X] T015 [US3] Implement `keyboards.keyword_list_keyboard` and `keyboards.delete_confirm_keyboard` in `src/channel_filter/keyboards.py` (depends on T002; satisfies T012)
- [X] T016 [US3] Update the 📋 Мої слова button handler to render `keyword_list_keyboard` instead of plain text, and add `callback_query` handlers for keyword-tap (show confirm), Yes (delete + rebuild + refresh), Cancel (revert to list), and stale-tap (toast + refresh) in `src/channel_filter/bot.py` (contracts/keyword-deletion.md; depends on T004, T014, T015; satisfies T013)

**Checkpoint**: User Stories 1, 2, and 3 all work independently — keyword deletion via tap-and-confirm works; typed `/remove` is unaffected.

---

## Phase 6: User Story 4 - Pause and Resume via a Single Tap (Priority: P2)

**Goal**: ⏸/▶️ button toggles notifications with one tap and always shows the option matching the subscriber's current state.

**Independent Test**: As an active subscriber, tap ⏸, confirm notifications stop and the menu now offers ▶️; tap it and confirm notifications resume against the existing keyword list with no re-entry.

### Tests for User Story 4 ⚠️

- [X] T017 [US4] Write failing tests for message handlers on button text "⏸ Призупинити" (delegates to `stop_handler`) and "▶️ Відновити" (delegates to `start_handler`), confirming the menu's label reflects the new state on the next reply, in `tests/unit/test_bot_commands.py`

### Implementation for User Story 4

- [X] T018 [US4] Register the ⏸/▶️ button-text handlers in `src/channel_filter/bot.py` (depends on T002, T004; satisfies T017) — the dynamic label itself is already covered by Foundational's T001/T002 tests

**Checkpoint**: User Stories 1–4 all work independently — one-tap pause/resume works and the label toggles correctly.

---

## Phase 7: User Story 5 - Operator Discovers Their Own Admin Commands (Priority: P2)

**Goal**: The operator's `/help` (typed or via ❓) additionally lists `/broadcast`, `/stats`, `/block`, `/unblock` and how to use them; non-operators see unchanged output.

**Independent Test**: As the operator, request help and confirm the admin section appears; as a non-operator, request help and confirm it doesn't.

### Tests for User Story 5 ⚠️

- [X] T019 [US5] Write failing tests for `help_handler` appending the admin-command section when `chat_id == admin_chat_id`, and omitting it (byte-identical to today's `HELP`) otherwise, in `tests/unit/test_bot_commands.py`

### Implementation for User Story 5

- [X] T020 [US5] Add the admin-command help section text to `src/channel_filter/messages.py` and update `help_handler` to accept `admin_chat_id` and branch on it in `src/channel_filter/bot.py` (contracts/admin-help.md; depends on T004; satisfies T019)

**Checkpoint**: All 5 user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and regression confirmation once the full button/callback set exists

- [ ] T021 [P] Run all quickstart.md validation scenarios end-to-end against a real Telegram bot/account
- [X] T022 Run the full `pytest` suite and confirm zero regressions in pre-existing 001 tests (`test_pipeline.py`, `test_matcher.py`, `test_auth.py`, `test_pipeline_to_notifier.py`, and the unchanged portions of `test_db.py`/`test_bot_commands.py`) per SC-005 (depends on all prior tasks) — 96/96 tests pass (`pytest tests/`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks — nothing to wait on
- **Foundational (Phase 2)**: BLOCKS all user stories — `subscriber_menu` is attached to every reply in every story below
- **User Stories (Phases 3–7)**: All depend on Foundational; implemented in priority order (P1 → P2) below
  - Phase 3 (US1, P1) — MVP, no dependency on other stories
  - Phase 4 (US2, P1) — depends on Foundational only; independent of US1's specific button wiring
  - Phase 5 (US3, P2) — depends on US1's 📋 handler existing (T004) to upgrade it
  - Phase 6 (US4, P2) — depends on US1's reply-markup wiring (T004) to add ⏸/▶️ alongside it
  - Phase 7 (US5, P2) — depends on US1's `help_handler` wiring (T004) to extend it
- **Polish (Phase 8)**: Depends on all user stories being complete

### Within Each User Story

- Tests MUST be written and confirmed FAILING before implementation (constitution TDD gate)
- Shared helpers/keyboard builders before the handlers that use them
- Story complete and checkpoint-verified before moving to the next priority phase

### Parallel Opportunities

- T011, T012, T013 (US3 tests — different files: `test_db.py`, `test_keyboards.py`, `test_bot_commands.py`) can run in parallel
- Once Foundational (T001–T002) completes, US1 must land first (its 📋/❓/reply-markup wiring in `bot.py` is what US3/US4/US5 each extend); after that, US2 can proceed independently in parallel with US3/US4/US5's test-writing, though US3/US4/US5's implementation tasks each touch `bot.py` alongside US1's and US2's changes, so converge sequentially there

---

## Parallel Example: User Story 3

```bash
# Launch all US3 tests together (different files):
Task: "Update list_keywords test + add remove_keyword_by_id tests in tests/unit/test_db.py"
Task: "Write failing tests for keyword_list_keyboard/delete_confirm_keyboard in tests/unit/test_keyboards.py"
Task: "Write failing tests for the keyword-list callback flow in tests/unit/test_bot_commands.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**: Run quickstart.md scenario 1 against a real bot
4. Deploy/demo if ready

### Incremental Delivery

1. Foundational → shared menu builder ready
2. US1 → validate independently → MVP demo (menu + 📋/❓ wired)
3. US2 → validate independently (guided + typed multi-add)
4. US3 → validate independently (tap-to-delete)
5. US4 → validate independently (pause/resume toggle)
6. US5 → validate independently (operator help)
7. Polish → full quickstart.md run + regression check against 001's existing suite

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability (spec.md numbering)
- Per the constitution's TDD gate, a checkbox may only flip to `[x]` after RED (test written, confirmed failing) → GREEN (minimal code, test passes) → REFACTOR, with `pytest` passing cleanly
- T011 intentionally updates a pre-existing 001 test rather than adding a parallel one — the return-type change is a deliberate part of this feature's contract (data-model.md), not a case of a test "violating the spec" being edited around
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
