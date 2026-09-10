# Feature Specification: Button-Driven Subscriber UX & Admin Discoverability

**Feature Branch**: `002-button-driven-ux`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "use this doc docs/superpowers/specs/2026-09-10-button-driven-ux-design.md for new specs"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Navigate the Bot Without Typing Commands (Priority: P1)

A subscriber interacts with the bot entirely through a fixed set of on-screen
buttons — add a keyword, view my keywords, pause/resume, help — instead of
memorizing and typing command names.

**Why this priority**: This is the foundational UX shift every other story in
this feature builds on. Without a persistent, always-visible menu, none of
the other button-driven interactions (add, remove, pause, help) have an
entry point.

**Independent Test**: Start a conversation with the bot and confirm a fixed
row of buttons is visible without typing anything; tapping each button
triggers the same outcome as its equivalent typed command would, without the
subscriber typing a command name.

**Acceptance Scenarios**:

1. **Given** a subscriber opens or continues a conversation with the bot,
   **When** they look at the message input area, **Then** they see a
   persistent set of buttons covering: add a keyword, view my keywords,
   pause/resume, and help.
2. **Given** the subscriber taps any one of these buttons, **When** the bot
   responds, **Then** the outcome matches what the equivalent typed command
   would have produced, and the button menu remains visible for the next
   action.
3. **Given** a subscriber who prefers typing, **When** they type a command
   directly instead of tapping a button, **Then** it still works exactly as
   before — buttons are an additional way in, not a replacement requirement.

---

### User Story 2 - Add Multiple Keywords at Once (Priority: P1)

A subscriber taps a button to add keyword(s), is prompted for the word(s)
they want, and can supply several at once separated by commas, receiving a
clear per-word result instead of having to repeat the action once per word.

**Why this priority**: Adding a keyword is the single most common action in
the bot, and today it requires one full typed command per word. This is the
highest-value UX improvement requested.

**Independent Test**: Tap the add-keyword button, send several comma
separated words in one message (including a mix of a brand-new valid word,
one already saved, and one too short), and confirm each word's individual
outcome is reported back correctly.

**Acceptance Scenarios**:

1. **Given** a subscriber taps the add-keyword button, **When** the bot
   replies asking for the word(s), **Then** the subscriber can respond with
   a single word or several words separated by commas in one message.
2. **Given** a subscriber submits several comma-separated words in one
   message, **When** the bot processes them, **Then** each word is
   evaluated independently against the existing add rules (minimum length,
   per-subscriber cap, no duplicates) and the reply states, per word,
   whether it was added, already existed, was too short, or could not be
   added because the cap was reached.
3. **Given** a subscriber is already at their keyword cap, **When** they
   submit a batch containing new words, **Then** every new word in that
   batch is reported as rejected due to the cap, with no partial confusion
   about which ones "almost" made it.
4. **Given** a subscriber types the equivalent typed command with
   comma-separated words directly (bypassing the guided prompt), **When**
   they submit it, **Then** the same per-word evaluation and reporting
   applies.

---

### User Story 3 - Remove a Keyword by Tapping It (Priority: P2)

A subscriber views their saved keywords as a tappable list and removes one by
tapping it and confirming, without typing the word out again.

**Why this priority**: Removing a keyword today requires retyping it exactly,
which is unnecessary friction once the subscriber can already see their list.
Builds on User Story 1's navigation but is independently valuable and
testable on its own.

**Independent Test**: With a subscriber who has at least two saved keywords,
view the list as tappable items, tap one, confirm the removal, and verify it
no longer appears in the list or triggers future notifications, while the
other keyword remains untouched.

**Acceptance Scenarios**:

1. **Given** a subscriber with saved keywords views their list, **When** the
   list is shown, **Then** each keyword is individually tappable.
2. **Given** the subscriber taps one keyword from the list, **When** the bot
   responds, **Then** it asks the subscriber to confirm removal of that
   specific keyword before anything is deleted.
3. **Given** the subscriber confirms the removal, **When** the confirmation
   is processed, **Then** that keyword is deleted, no longer triggers
   notifications, and the subscriber sees their updated list.
4. **Given** the subscriber instead cancels the confirmation, **When** they
   do so, **Then** no keyword is deleted and they return to viewing their
   unchanged list.
5. **Given** a subscriber taps a keyword that has already been removed (for
   example, through a separate, near-simultaneous action), **When** the tap
   is processed, **Then** the bot tells them it's already gone rather than
   failing or showing a confusing error.

---

### User Story 4 - Pause and Resume via a Single Tap (Priority: P2)

A subscriber pauses or resumes notifications with one tap, without typing a
command, and the button itself reflects their current state.

**Why this priority**: A frequently used action that benefits directly from
one-tap access; independently valuable but lower-impact than adding/removing
keywords.

**Independent Test**: As an active subscriber, tap the pause button and
confirm notifications stop while keywords remain saved; confirm the same
button now offers to resume; tap it again and confirm notifications restart
with the same keyword list.

**Acceptance Scenarios**:

1. **Given** an active subscriber, **When** they view the button menu,
   **Then** it offers to pause notifications.
2. **Given** the subscriber taps the pause button, **When** the action
   completes, **Then** notifications stop, their keywords remain saved, and
   the menu now offers to resume instead.
3. **Given** a paused subscriber taps the resume option, **When** the action
   completes, **Then** notifications restart immediately against their
   existing keyword list with no re-entry required.

---

### User Story 5 - Operator Discovers Their Own Admin Commands (Priority: P2)

The operator asks the bot for help and, because they are the operator, also
sees the admin-only actions available to them (broadcasting a message and
viewing subscriber statistics) and how to use each one — which today are not
shown to anyone.

**Why this priority**: These admin capabilities already exist and work, but
are undiscoverable, which defeats their purpose for the one person who is
supposed to use them. This is a low-effort, high-value fix distinct from the
subscriber-facing button work above.

**Independent Test**: As the operator, request help and confirm the reply
includes a section describing the admin-only actions and their usage; as a
regular subscriber, request help and confirm that section does not appear.

**Acceptance Scenarios**:

1. **Given** the operator requests help, **When** the bot replies, **Then**
   the reply includes the regular help content plus a clearly separated
   section listing every admin-only action and how to use it.
2. **Given** a non-operator subscriber requests help, **When** the bot
   replies, **Then** the admin-only section does not appear, unchanged from
   current behavior.

---

### Edge Cases

- What happens when a subscriber sends only commas, blank entries, or
  whitespace in response to the add-keyword prompt? It is treated the same
  as submitting no word at all today — rejected with the existing
  "too short" explanation, not a new or confusing error.
- What happens if a subscriber ignores the add-keyword prompt and instead
  taps a different button (e.g. view my keywords)? The add flow is
  abandoned cleanly and the newly tapped action proceeds normally — the
  subscriber's unrelated next message is never mistaken for keyword input.
- What happens when a blocked subscriber taps any button? They see the same
  "you are blocked" response they would get from the equivalent typed
  command — buttons do not bypass the existing block.
- What happens when a subscriber taps a keyword-removal confirmation after
  it has become stale (the keyword was already removed another way)? The
  bot tells them it's already gone and shows their current list, rather than
  erroring.
- What happens to the native "/" command menu subscribers already know?
  Every existing typed command continues to work exactly as before; nothing
  is removed or hidden from the people who prefer typing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST present a persistent set of buttons to every
  subscriber, covering: add a keyword, view my keywords, pause/resume
  notifications, and help, in every conversation.
- **FR-002**: System MUST make each button trigger the same outcome as its
  equivalent existing typed command, with no difference in the underlying
  rule (limits, validation, confirmations of state).
- **FR-003**: System MUST NOT remove or change the behavior of any existing
  typed command; typing remains fully functional alongside the buttons.
- **FR-004**: System MUST let a subscriber, after tapping the add-keyword
  button, submit one or more words in a single message, separated by commas.
- **FR-005**: System MUST evaluate each word in a multi-word submission
  independently against the existing add rules (minimum length, duplicate
  check, per-subscriber cap) and report each word's individual outcome to
  the subscriber.
- **FR-006**: System MUST let a subscriber submit multiple comma-separated
  words via the existing typed add command as well, with identical
  per-word evaluation and reporting as the guided button flow.
- **FR-007**: System MUST present a subscriber's saved keywords as
  individually selectable items when they view their list.
- **FR-008**: System MUST require an explicit confirmation step before
  deleting a keyword selected from the list, and MUST NOT delete it if the
  subscriber cancels.
- **FR-009**: System MUST tell a subscriber clearly when they attempt to
  remove a keyword that no longer exists (e.g. already removed), rather than
  failing silently or with an unexplained error.
- **FR-010**: System MUST reflect a subscriber's current pause/active state
  in the button menu (offering to pause when active, offering to resume
  when paused).
- **FR-011**: System MUST apply the existing blocked-subscriber restriction
  identically whether a blocked subscriber uses a button or a typed command.
- **FR-012**: System MUST, when the operator specifically requests help,
  include a section describing every admin-only action and how to use it,
  in addition to the regular help content.
- **FR-013**: System MUST NOT show the admin-only help section to any
  subscriber who is not the operator, preserving current restriction of
  admin actions to the operator alone.

### Key Entities

- **Subscriber**: Unchanged from the existing feature — gains no new
  attributes, but its keyword list must now be presentable as individually
  selectable items (each keyword must be distinguishable from the others
  when shown as a tappable list) and its active/paused state must be
  reflected back into the button menu shown to it.
- **Keyword**: Unchanged in meaning (a short text fragment a subscriber is
  alerted about) — must be individually identifiable when presented as a
  selectable list item, distinct from being merely listed as text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new subscriber can add their first keyword, view their list,
  and remove a keyword without typing a single command, using only buttons.
- **SC-002**: A subscriber adding 3 keywords in one message receives a
  correct, individual outcome for each within a single reply, rather than
  needing 3 separate submissions.
- **SC-003**: 100% of keyword deletions initiated via the button list require
  an explicit confirmation step and never delete on the first tap alone.
- **SC-004**: The operator can find and correctly use the admin-only actions
  (broadcast, view statistics) after a single help request, without prior
  undocumented knowledge of their existence.
- **SC-005**: 100% of existing typed commands continue to behave exactly as
  before this feature, with zero regressions for subscribers who never use
  the new buttons.

## Assumptions

- This feature only changes how subscribers and the operator reach existing
  capabilities (add, remove, list, pause, resume, help, broadcast, view
  statistics); it introduces no new underlying capability and no change to
  notification matching or delivery behavior.
- The persistent button menu is shown to subscribers only; the operator
  does not receive additional admin-only buttons in this feature — admin
  actions remain reached by typing, with only their discoverability (via
  help) improved.
- Blocking, unblocking, and identifying a specific subscriber by an
  operator-supplied identifier remain typed-only actions; no picker or list
  of subscribers is introduced for the operator in this feature.
- Permanently deleting an account remains a typed-only action (existing
  typed `/deleteme` is unchanged). It is deliberately excluded from the
  persistent button menu — an account deletion is rare enough that it does
  not need one-tap access, and keeping it out of the menu avoids surfacing
  a destructive, irreversible action alongside routine ones.
- The native "/" command list subscribers see in their client is unchanged
  by this feature.
