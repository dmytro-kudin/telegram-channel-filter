# Contract: Bot Commands

The bot's command set is its only user-facing interface. Each command is
registered via `set_my_commands` so it appears in Telegram's native command
menu. This contract fixes each command's inputs and possible replies;
`tasks.md` and implementation must satisfy it exactly.

## `/start`

**Input**: no arguments.

**Behavior**: Registers the sending `chat_id` as a Subscriber if not
already known (FR-001); sets `active = True` regardless of prior state
(resumes a paused subscriber with their existing keyword list intact,
FR-011).

**Reply**: Welcome/usage text, always success — this command cannot fail.

## `/add <word>`

**Input**: one argument, `<word>` (free text, may contain spaces if quoted
by the user — treated as a single substring).

**Behavior**:
- Reject if `<word>` is missing, or shorter than 3 characters after
  stripping whitespace (FR-002).
- Reject if the subscriber already has 20 keywords (FR-003).
- If the (lowercased) keyword already exists for this subscriber, no new
  row is created (FR-004).
- Otherwise, insert the lowercased keyword and trigger an automaton
  rebuild.

**Replies** (mutually exclusive):
- Success: confirms the keyword was added.
- Already exists: confirms it's already saved (not an error).
- Too short: explains the 3-character minimum.
- Limit reached: explains the 20-keyword cap.

## `/remove <word>`

**Input**: one argument, `<word>`.

**Behavior**: Deletes the matching row (case-insensitive) for this
subscriber if present, and triggers an automaton rebuild.

**Replies** (mutually exclusive):
- Success: confirms removal.
- Not found: tells the subscriber this keyword wasn't in their list
  (FR-006) — never a silent no-op, never a hard error.

## `/list`

**Input**: no arguments.

**Behavior**: Reads all keywords currently saved for this subscriber
(FR-005).

**Replies**:
- Non-empty: the full list of the subscriber's keywords.
- Empty: a message indicating no keywords are saved yet.

## `/stop`

**Input**: no arguments.

**Behavior**: Sets `active = False` for this subscriber (FR-010). Keywords
are left untouched.

**Reply**: Confirms notifications are paused and that `/start` resumes them.

## `/deleteme`

**Input**: no arguments.

**Behavior**: Permanently deletes the Subscriber row and all of their
Keyword rows (FR-023). Succeeds unconditionally regardless of `blocked`
status — this is the one action a blocked subscriber can still perform
(FR-023, spec Edge Cases). Does **not** require a prior `/start` — deleting
a subscriber that was never registered is a no-op reply, not an error.

**Reply**: Confirms the account and all keywords have been permanently
removed, and that a future `/start` begins fresh with no saved keywords.

## `/help`

**Input**: no arguments.

**Behavior**: No state change.

**Reply**: Usage text listing all commands above (subscriber-facing
commands only — admin commands are documented separately in
`admin-commands.md` and are not advertised to non-operator subscribers).

## Cross-cutting rules for every command

- A command from a `chat_id` with no Subscriber row yet (i.e., every
  command except `/start` used before ever `/start`-ing) MUST still work —
  registration happens implicitly on first interaction (FR-001, spec Edge
  Cases). Handlers MUST NOT require `/start` to have been called first.
  `/deleteme` is the one exception where "no row exists" is itself a valid,
  already-satisfied end state, not an implicit registration trigger.
- No command ever raises an unhandled exception to the user; every
  validation failure above is an explicit reply, per Constitution Principle
  II.
- All replies are in Ukrainian (FR-025).
- A blocked subscriber (see `admin-commands.md`) gets a "you are blocked"
  reply for every command above except `/deleteme`, which always proceeds
  normally regardless of block status.
