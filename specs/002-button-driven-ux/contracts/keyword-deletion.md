# Contract: Keyword Deletion via the Keyword List

Follows select/trigger → explicit confirmation → act, and must never delete a
keyword on a single tap. Does not change the underlying deletion behavior
already documented in
`specs/001-channel-keyword-filter/contracts/bot-commands.md` (`/remove`); it
adds a confirmation step in front of it.

**Trigger**: Subscriber taps 📋 Мої слова (`button-menu.md`), or otherwise
arrives at their keyword list.

**Behavior**:
1. If the subscriber has no keywords: same empty-state reply as today's
   `/list` (`LIST_EMPTY`).
2. If the subscriber has keywords: rendered as an inline keyboard, one
   button per keyword, each labeled with that keyword's text and carrying
   its id in `callback_data` (data-model.md "Callback data encoding").
3. Tapping a keyword button edits the message to ask for confirmation
   ("Delete «word»?") with Yes/Cancel inline buttons, both carrying that
   same keyword id.
4. **Yes**: deletes the keyword (`remove_keyword_by_id`), triggers the same
   automaton rebuild `/remove` already triggers, edits the message to
   confirm, and shows the refreshed list (or the empty-state message if none
   remain) (FR-008).
5. **Cancel**: edits the message back to the plain list view — nothing is
   deleted (FR-008).
6. **Stale tap** (the keyword id no longer exists by the time Yes/Cancel or
   even the initial tap is processed — e.g. removed by a concurrent typed
   `/remove`): the callback is answered with a brief "already removed" toast
   and the message is refreshed to the current (possibly now-empty) list —
   never an unhandled error (FR-009).

**Reply**: Ukrainian text throughout, reusing `/remove`'s existing success
wording where the outcome matches.

## Cross-cutting rules

- Every callback query in this flow is explicitly answered (Telegram
  requirement to clear the tap's loading state), on every branch including
  Cancel and stale-tap — never left unanswered, never raising an unhandled
  exception (Constitution Principle II).
- This flow is unreachable for a blocked subscriber, since 📋 Мої слова
  itself is refused for them like any other menu action (`button-menu.md`
  cross-cutting rules).
