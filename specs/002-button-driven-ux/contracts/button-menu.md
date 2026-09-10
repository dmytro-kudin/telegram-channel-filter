# Contract: Persistent Subscriber Button Menu

Extends `specs/001-channel-keyword-filter/contracts/bot-commands.md`. The
persistent reply keyboard is an additional entry point onto the commands
documented there — it does not change any of their behavior, replies, or
edge cases.

## Menu contents

Sent alongside every bot reply to a subscriber chat (`refuse_if_blocked`
handlers), as a `ReplyKeyboardMarkup`:

| Button | Equivalent typed command | Notes |
|---|---|---|
| ➕ Додати слово | `/add` (guided — see `add-flow.md`) | Starts the guided add flow rather than expecting inline arguments |
| 📋 Мої слова | `/list` | Rendered as an inline keyboard — see `keyword-deletion.md` |
| ⏸ Призупинити | `/stop` | Shown only while the subscriber is active |
| ▶️ Відновити | `/start` | Shown only while the subscriber is paused — mutually exclusive with the row above |
| ❓ Довідка | `/help` | Same handler as typed `/help`, including the operator-aware branch (`admin-help.md`) |

Permanently deleting an account (`/deleteme`) is deliberately **not** on this
menu — it stays a typed-only action, unchanged from
`bot-commands.md`, since it's rare and irreversible and doesn't need one-tap
access (spec.md Assumptions).

**Behavior**:
- The menu is (re)sent with every reply so its pause/resume label always
  reflects the subscriber's *current* `active` state after whatever action
  just happened (FR-010).
- Tapping any button MUST produce the same outcome as sending its
  equivalent typed command would, including every existing validation rule,
  reply text, and edge case documented in `bot-commands.md` (FR-002).
- Typed commands MUST continue to work exactly as before for every
  subscriber who ignores the buttons entirely (FR-003).

## Cross-cutting rules

- A blocked subscriber tapping any menu button gets the same `BLOCKED` reply
  as tapping/typing the equivalent command — `refuse_if_blocked` wraps the
  button handlers identically to the typed ones (FR-011). This has no
  bearing on `/deleteme`'s existing block-exemption (`bot-commands.md`),
  since that action isn't on this menu at all.
- The menu itself is never shown to, or altered for, the operator based on
  their operator status — no admin-only buttons are added by this feature
  (spec.md Assumptions).
- The native Telegram "/" command list (`set_my_commands`) is unchanged —
  this menu is a separate, additional UI surface, not a replacement for it.
