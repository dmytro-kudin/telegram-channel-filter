# Contract: Operator-Aware Help

Extends `/help` from `specs/001-channel-keyword-filter/contracts/bot-commands.md`
and preserves the authorization rule from
`specs/001-channel-keyword-filter/contracts/admin-commands.md` ("admin
commands ... not advertised to non-operator subscribers"). This is the only
change in that authorization rule's scope: the operator themselves may now
be advertised their own admin commands.

## `/help` (typed or via ❓ Довідка button)

**Input**: no arguments.

**Behavior**: Unchanged base behavior — no state change, reads
`admin_chat_id` (already available to the handler via dispatcher-injected
context, per `main.py`) and compares it against the sender's `chat_id`.

**Reply**:
- **Non-operator subscriber**: exactly today's `HELP` text — unchanged,
  byte-for-byte (FR-013).
- **Operator** (`message.chat.id == admin_chat_id`): today's `HELP` text,
  plus an appended section listing every admin-only action and how to use
  it:
  ```
  Команди оператора:
  /broadcast <текст> — розіслати повідомлення всім активним підписникам
  /stats — переглянути статистику підписників
  /block <chat_id> — заблокувати підписника
  /unblock <chat_id> — розблокувати підписника
  ```
  (FR-012)

## Cross-cutting rules

- This is the only surface where admin commands are described to anyone —
  `set_my_commands` (the native "/" menu) remains subscriber-commands-only,
  unchanged from 001. The operator finds `/broadcast`, `/stats`, `/block`,
  `/unblock` by typing them directly (as documented in
  `admin-commands.md`), now with `/help` confirming they exist and how to
  use them.
- No new admin-only buttons are introduced (spec.md Assumptions) — this
  contract only changes text content, not the button menu.
- If the operator is also, separately, a Subscriber row (i.e. the operator's
  own chat also ran `/start` at some point), this contract still applies
  purely by `chat_id` comparison — no interaction with `Subscriber.blocked`
  or `Subscriber.active`, matching how `require_operator` already treats the
  operator as identified by configuration, not by any Subscriber state
  (`specs/001-channel-keyword-filter/data-model.md` §Operator).
