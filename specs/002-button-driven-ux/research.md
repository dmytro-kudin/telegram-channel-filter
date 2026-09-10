# Phase 0 Research: Button-Driven Subscriber UX & Admin Discoverability

All Technical Context items were already decided during the brainstorming
session (see
`docs/superpowers/specs/2026-09-10-button-driven-ux-design.md`), so there are
no unresolved `NEEDS CLARIFICATION` markers. This document records the
supporting rationale and alternatives for each technology/integration choice,
per Phase 0 requirements.

## 1. Reply keyboard for primary navigation, inline keyboards for in-context actions

**Decision**: Use aiogram's `ReplyKeyboardMarkup`/`KeyboardButton` for the
persistent subscriber menu (Add, My keywords, Pause/Resume, Help), and
`InlineKeyboardBuilder` (already used in `notifier.py`) for the keyword list
and its delete-confirmation step.

**Rationale**: A reply keyboard is the only Telegram construct that stays
visible across turns without being attached to one specific message, which
is exactly what "always-available menu" requires. Inline keyboards are the
only construct that can be edited in place (list → confirm → result) and
that carry `callback_data` distinguishing *which* keyword was tapped —
reply-keyboard buttons only ever send their label text back as a plain
message, which can't disambiguate "delete keyword #7" from "delete keyword
#12". This matches the user's explicit choice of "both" during
brainstorming.

**Alternatives considered**: Inline keyboards only (attached per-message,
no permanent menu) — rejected per the user's explicit preference for an
always-visible menu; reply keyboard only, with keyword deletion done by
retyping — rejected, since it reintroduces the exact typing friction this
feature exists to remove.

## 2. Guided add-keyword flow via aiogram FSM

**Decision**: A minimal aiogram `StatesGroup` with one state
(`AddKeywords.waiting`), entered when the Add-keyword button is tapped,
cleared unconditionally after the next message is processed (success or
failure) or if any other button/command arrives first.

**Rationale**: aiogram's FSM is the standard, built-in mechanism for "the
next message from this chat means something different than usual" — no
extra dependency, and it integrates with the same `Dispatcher`/`Router`
already in use. Because the flag only needs to survive a few seconds
between a button tap and the subscriber's reply, the default in-memory
`MemoryStorage` (aiogram's default when no storage is configured) is
sufficient — losing it on a restart just means the subscriber's next
message is treated as a normal command/button tap instead, which is a safe,
self-correcting outcome (Constraints, plan.md).

**Alternatives considered**: A DB-backed "pending action" column on
`subscribers` — rejected as unnecessary persistence for a transient,
seconds-long UI flag with no correctness requirement across restarts;
requiring the guided flow's input on the *same* message as the button tap
(impossible in Telegram, since a `ReplyKeyboardMarkup` tap only sends the
button's label text, it cannot also carry free text) was never a viable
option.

## 3. Comma-separated multi-keyword parsing as one shared helper

**Decision**: One function, `_parse_keyword_batch(raw: str) -> list[str]`,
splits on `,`, strips whitespace from each piece, and drops empty pieces
(e.g. from trailing commas or all-whitespace input); each surviving piece is
then run through the existing `db.add_keyword` once, unchanged. Both the
typed `/add` handler and the guided-flow message handler call this same
helper and share one per-word reply-formatting function.

**Rationale**: Constitution Coding Standards require repeated per-type
parsing/formatting logic to be a shared function rather than duplicated at
each call site; here there are exactly two call sites (typed, guided) that
must behave identically per spec.md FR-006. Reusing `db.add_keyword`
per-word (rather than inventing a batch-aware variant) keeps the existing,
already-tested validation rules (min length, cap, dedup) as the single
source of truth — this feature only changes how many times that function is
invoked per user action, not its rules.

**Alternatives considered**: A batch-aware `add_keywords` DB function that
validates the whole list in one transaction — rejected: per FR-005 each word
is evaluated *independently* (one word being too short must not affect
another word in the same batch), so a per-word loop over the existing
function is both simpler and already spec-correct; splitting on other
delimiters (semicolons, whitespace) — rejected, spec.md only calls for
comma-separation and keywords may legitimately contain spaces.

## 4. Exposing a stable keyword identifier for inline deletion

**Decision**: `db.list_keywords` changes its return type from `list[str]` to
`list[Keyword]` (the existing `dataclass` already defined in `types.py`,
carrying `id`), and a new `db.remove_keyword_by_id(conn, chat_id,
keyword_id) -> RemoveKeywordOutcome` deletes by that id. Inline
keyword-list and delete-confirm buttons encode the keyword's `id` (a small
integer) in `callback_data`.

**Rationale**: The keyword's own text could exceed Telegram's 64-byte
`callback_data` limit or contain characters needing escaping; the row's
existing autoincrement `id` (already part of the 001 schema, just not
previously selected) is short, stable, and unambiguous even if two
subscribers happen to share an identical keyword string. This avoids a
second lookup-by-text round-trip and avoids re-normalizing text pulled back
out of `callback_data`.

**Alternatives considered**: Encode the keyword text itself (truncated or
hashed) in `callback_data` — rejected as fragile (truncation could collide
two different keywords for the same subscriber; hashing adds complexity
with no benefit over an id already on hand from the same query that renders
the list).

## 5. Stale/already-removed keyword tap handling

**Decision**: If a delete-confirm callback's `keyword_id` no longer exists
(e.g. removed by a second, near-simultaneous tap, or via typed `/remove`),
`remove_keyword_by_id` returns the existing `NotFound` outcome shape
(reused from `RemoveKeywordOutcome`), and the callback handler answers the
callback query with a short "already removed" toast and refreshes the
displayed list — never an unhandled exception.

**Rationale**: Constitution Principle II requires expected failures as
explicit typed values, not exceptions; `NotFound` already exists for exactly
this "nothing to remove" case in the typed `/remove` path (see
`specs/001-channel-keyword-filter/data-model.md`), so reusing it here keeps
one definition of "keyword removal can fail this one way" instead of a
second, parallel error type.

**Alternatives considered**: Silently no-op the stale tap with no feedback —
rejected, since a silent tap that visibly does nothing reads as a bug to the
subscriber; a full error message instead of a lightweight toast — rejected
as disproportionate for a benign, expected race (Telegram's own
`answerCallbackQuery` "toast" mechanism exists for exactly this kind of
brief, non-blocking notice).

## 6. Operator-aware `/help` instead of a separate admin command or admin buttons

**Decision**: `help_handler` gains the existing `admin_chat_id` dependency
(already injected into the dispatcher context per `main.py`) and appends the
admin-command section to its reply only when `message.chat.id ==
admin_chat_id`. No new command, no new buttons for the operator.

**Rationale**: This was the user's explicit choice during brainstorming
("just fix discoverability another way" over admin buttons). `/help` is
already the natural, existing place subscribers (and the operator) go to
learn what they can do; branching its content on sender identity requires no
new registered command and no change to `set_my_commands` (the native "/"
menu stays subscriber-only, preserving the existing "not advertised to
non-operators" contract in `specs/001-channel-keyword-filter/contracts/
admin-commands.md`).

**Alternatives considered**: A separate `/adminhelp` command — rejected as
an extra thing to remember, the opposite of this feature's goal; operator-only
reply-keyboard buttons — explicitly rejected by the user as out of scope for
this round.

## 7. No change to rate limiting, matching, or persistence guarantees

**Decision**: This feature touches none of `pipeline.py`, `matcher.py`,
`notifier.py`, or the eligibility/blocking rules established in 001.

**Rationale**: Every button/callback path in this feature terminates in the
same DB operations (`add_keyword`, `remove_keyword`/`remove_keyword_by_id`,
`set_active`, `delete_subscriber`) already exercised by the typed commands,
which already trigger the existing automaton rebuild and pass through the
existing `refuse_if_blocked`/`require_operator` decorators unchanged. There
is nothing new to design here — it's explicitly out of scope (spec.md
Assumptions).
