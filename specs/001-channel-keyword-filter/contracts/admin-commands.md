# Contract: Admin Commands

Four commands are restricted to the single operator (FR-017/FR-018),
identified by the fixed `ADMIN_CHAT_ID` configuration value (data-model.md
§Operator). They are registered as bot commands like any other, but every
handler is wrapped in a shared `require_operator` decorator (research.md
§6b) that runs before the handler body.

## Cross-cutting rule: authorization

For every command below: if the sender's `chat_id` is not `ADMIN_CHAT_ID`,
the handler body never runs. The bot replies (in Ukrainian, FR-025) that
the command is restricted to the operator, and takes no other action. This
check happens identically for all four commands via the one
`require_operator` decorator — no handler re-implements it.

## `/broadcast <text>`

**Input**: one argument, `<text>` (free text, the message to send).

**Behavior**: Resolves the current set of eligible subscribers
(`active=1 AND blocked=0`, data-model.md §Eligibility predicate) via a
fresh DB read, and enqueues one `NotificationJob` per eligible subscriber
carrying `<text>` (FR-019). This does not go through the message-processing
pipeline (contracts/pipeline-stage-contract.md) — there is no `ChannelPost`
involved.

**Reply**: Confirms to the operator how many subscribers the broadcast was
queued for.

## `/stats`

**Input**: no arguments.

**Behavior**: Reads the total subscriber count and the breakdown by state
(active-and-not-blocked, paused, blocked) (FR-020). Read-only; no side
effects.

**Reply**: The total count plus the breakdown, in Ukrainian.

## `/block <chat_id>`

**Input**: one argument, `<chat_id>` (the target subscriber's identifier).

**Behavior**: Sets `blocked = True` for the target subscriber, if they
exist (FR-021). Does not modify their `active` value. Triggers an
automaton rebuild (research.md §6a — a blocked subscriber's keywords must
stop matching immediately).

**Replies** (mutually exclusive):
- Success: confirms the subscriber is now blocked.
- Not found: tells the operator no subscriber exists with that `chat_id`.

## `/unblock <chat_id>`

**Input**: one argument, `<chat_id>`.

**Behavior**: Sets `blocked = False` for the target subscriber, if they
exist and are currently blocked (FR-022). Restores whatever `active` value
they already had — unblocking never itself changes `active`. Triggers an
automaton rebuild.

**Replies** (mutually exclusive):
- Success: confirms the subscriber is unblocked and their prior
  active/paused state applies again.
- Not found / not blocked: tells the operator there's nothing to unblock
  for that `chat_id`.
