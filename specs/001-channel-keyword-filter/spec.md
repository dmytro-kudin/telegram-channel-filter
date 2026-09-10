# Feature Specification: Channel Keyword Filter

**Feature Branch**: `001-channel-keyword-filter`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Use this doc docs/superpowers/specs/2026-09-10-telegram-channel-filter-design.md to create specification. Break it in multiple stories, not one big story"

## Clarifications

### Session 2026-09-10

- Q: Does this system need any operator/admin-only capability beyond what individual subscribers can do for themselves? → A: Yes — manual broadcast, subscriber stats, and blocking a subscriber.
- Q: Should a subscriber be able to permanently delete their account and all their keywords, beyond just pausing? → A: Yes, add a delete-my-data command; re-subscribing later starts with an empty keyword list.
- Q: What language should the bot's own reply messages (confirmations, errors, help text) be in? → A: Ukrainian.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get Notified When a Post Matches Your Keyword (Priority: P1)

A subscriber registers with the bot and adds a keyword they care about. From
then on, whenever the monitored channel publishes a post containing that
keyword, the subscriber receives a notification with the post's text and a
way to open the original post.

**Why this priority**: This is the entire reason the product exists. Without
detection and delivery, nothing else in the system has value.

**Independent Test**: Register a fresh subscriber, add one keyword, publish a
channel post containing that keyword, and confirm the subscriber receives a
notification referencing that post. Delivers the core value on its own.

**Acceptance Scenarios**:

1. **Given** a new subscriber with no keywords, **When** they add a keyword
   at least 3 characters long, **Then** the keyword is saved to their list.
2. **Given** a subscriber with a saved keyword, **When** a channel post is
   published containing that keyword (any letter case), **Then** the
   subscriber receives a notification containing the post's text and a link
   to view the original post.
3. **Given** a subscriber with a saved keyword, **When** a channel post is
   published that does not contain that keyword, **Then** the subscriber
   receives no notification for that post.
4. **Given** a subscriber whose keyword matches multiple times in the same
   post, or matches together with another of their keywords in the same
   post, **When** that post is published, **Then** the subscriber receives
   exactly one notification for that post, not one per match.
5. **Given** a subscriber attempts to add a keyword shorter than 3
   characters, **When** they submit it, **Then** the system rejects it and
   explains the minimum length.

---

### User Story 2 - Manage Your Personal Keyword List (Priority: P2)

A subscriber views their current list of keywords and removes ones they no
longer want to be notified about.

**Why this priority**: Necessary for the service to stay useful over time —
without it, subscribers can only ever accumulate keywords, never correct
mistakes or drop stale ones. Depends on User Story 1 existing but is
independently valuable on top of it.

**Independent Test**: With a subscriber that already has two saved keywords,
request the list and confirm both appear; remove one and confirm the list
now shows only the other, and that keyword no longer triggers notifications.

**Acceptance Scenarios**:

1. **Given** a subscriber with saved keywords, **When** they request their
   list, **Then** they see every keyword currently saved for them.
2. **Given** a subscriber with a saved keyword, **When** they remove it,
   **Then** it no longer appears in their list and no longer triggers
   notifications for future posts.
3. **Given** a subscriber tries to remove a keyword they never added,
   **When** they submit the removal, **Then** the system tells them it
   wasn't found rather than failing silently or with an error.
4. **Given** a subscriber already has a keyword saved, **When** they try to
   add the same keyword again, **Then** the system treats it as already
   saved (no duplicate entry) and confirms rather than erroring.
5. **Given** a subscriber already has 20 saved keywords, **When** they try
   to add a 21st, **Then** the system rejects it and explains the limit.

---

### User Story 3 - Pause and Resume Alerts (Priority: P2)

A subscriber temporarily stops receiving notifications — for example while
on vacation — without losing their saved keyword list, then resumes later
with everything intact.

**Why this priority**: Gives subscribers control without forcing them to
lose configuration, which is what makes pausing actually useful. Builds on
Story 1's delivery mechanism.

**Independent Test**: With a subscriber that has saved keywords and is
actively receiving matches, pause their notifications, publish a matching
post and confirm nothing is delivered, then resume and confirm delivery
restarts for the same keyword list with no re-entry needed.

**Acceptance Scenarios**:

1. **Given** an active subscriber with saved keywords, **When** they pause
   notifications, **Then** they receive no further notifications, keyword or
   otherwise, until they resume.
2. **Given** a paused subscriber, **When** a channel post is published that
   would otherwise match one of their keywords, **Then** no notification is
   sent to them.
3. **Given** a paused subscriber, **When** they resume, **Then** their full
   previously saved keyword list is immediately active again and no
   reconfiguration is required.

---

### User Story 4 - Guaranteed Delivery of Jar-Link Announcements (Priority: P3)

Certain posts that link to a donation jar are important enough that every
subscriber should see them, whether or not the post matches any of their
personal keywords.

**Why this priority**: A narrow but explicit business rule layered on top of
the personal-keyword system; valuable on its own but not required for the
core product to function.

**Independent Test**: With multiple subscribers who have no keywords that
would otherwise match, publish a post containing the designated jar link and
confirm every active (non-paused) subscriber receives it, while a paused
subscriber does not.

**Acceptance Scenarios**:

1. **Given** any set of active subscribers regardless of their personal
   keyword lists, **When** a channel post containing the designated jar link
   is published, **Then** every active subscriber receives a notification
   for that post.
2. **Given** a paused subscriber, **When** a jar-link post is published,
   **Then** they receive no notification until they resume.

---

### User Story 5 - Suppress Bare-Number Noise (Priority: P3)

Posts whose entire content is just a number carry no useful context on their
own, so no one should be notified about them, even if the digits happen to
overlap with someone's keyword.

**Why this priority**: A quality safeguard that keeps the notification
stream meaningful; narrow in scope and independent of the rest of the
matching logic.

**Independent Test**: With a subscriber whose keyword happens to be a
numeric string, publish a channel post whose entire content is just a
number and confirm no one is notified, then publish a post that contains
that same number alongside other text and confirm normal matching still
applies.

**Acceptance Scenarios**:

1. **Given** any set of subscribers, **When** a channel post is published
   whose entire content is only a number (with or without common numeric
   punctuation such as commas or spaces), **Then** no notification is sent
   to anyone for that post.
2. **Given** the same conditions, **When** a channel post contains a number
   alongside other text, **Then** normal keyword matching and jar-link
   detection still apply to that post.

---

### User Story 6 - Permanently Delete My Data (Priority: P2)

A subscriber who no longer wants any trace of their data in the system
permanently erases their account and all their keywords, rather than just
pausing.

**Why this priority**: A privacy safeguard subscribers should be able to
trust exists; distinct from pausing, which keeps data intact.

**Independent Test**: With a subscriber that has saved keywords, request
deletion, confirm their keywords no longer exist and a matching post
triggers no notification for them, then interact with the bot again and
confirm they're treated as a brand-new subscriber with no prior keywords.

**Acceptance Scenarios**:

1. **Given** a subscriber with saved keywords, **When** they request
   permanent deletion, **Then** their subscriber record and all their
   keywords are removed entirely.
2. **Given** a subscriber has deleted their data, **When** a post is
   published that would have matched their old keywords, **Then** they
   receive nothing, since they are no longer a subscriber.
3. **Given** a subscriber who previously deleted their data, **When** they
   interact with the bot again, **Then** they are registered as a new
   subscriber with an empty keyword list — nothing carries over.
4. **Given** a blocked subscriber, **When** they request deletion of their
   own data, **Then** the deletion succeeds regardless of their blocked
   status — deleting one's own data is never restricted by a block.

---

### User Story 7 - Operator Blocks an Abusive Subscriber (Priority: P2)

The operator stops a specific subscriber from receiving anything or using
the bot at all, overriding that subscriber's own settings, then later
reverses this if needed.

**Why this priority**: Protects the service and other subscribers from
abuse; more important than the operator's convenience-oriented tools
(broadcast, stats) because it's a safeguard for the system's integrity.

**Independent Test**: As the operator, block a test subscriber, confirm
they receive no notifications (even ones that would normally reach every
active subscriber) and that their commands are refused with an
explanation; unblock them and confirm normal behavior returns.

**Acceptance Scenarios**:

1. **Given** a subscriber the operator has blocked, **When** a post would
   otherwise notify them (keyword match, jar-link, or broadcast), **Then**
   they receive nothing, regardless of their own active/paused state.
2. **Given** a blocked subscriber, **When** they issue any bot command,
   **Then** the system refuses it and tells them they've been blocked.
3. **Given** a previously blocked subscriber, **When** the operator unblocks
   them, **Then** their prior active/paused state and normal command access
   are restored.
4. **Given** a non-operator subscriber, **When** they attempt to block or
   unblock anyone, **Then** the system refuses.

---

### User Story 8 - Operator Sends a Manual Broadcast (Priority: P3)

The operator sends a message to every active, non-blocked subscriber on
demand, independent of any channel post (e.g. a maintenance notice).

**Why this priority**: Useful operational tooling, but not required for the
core filtering product to function.

**Independent Test**: As the operator, send a broadcast with test text and
confirm every active, non-blocked subscriber receives it while a paused or
blocked subscriber does not; confirm a non-operator subscriber cannot
trigger a broadcast.

**Acceptance Scenarios**:

1. **Given** a mix of active, paused, and blocked subscribers, **When** the
   operator sends a broadcast, **Then** only active, non-blocked
   subscribers receive it.
2. **Given** a non-operator subscriber, **When** they attempt to send a
   broadcast, **Then** the system refuses.

---

### User Story 9 - Operator Views Subscriber Stats (Priority: P3)

The operator checks how many subscribers are registered and their
active/paused/blocked breakdown.

**Why this priority**: Useful operational visibility, not required for the
core filtering product to function.

**Independent Test**: Register a few subscribers, pause one and block
another, then request stats as the operator and confirm the counts match.

**Acceptance Scenarios**:

1. **Given** a known mix of active, paused, and blocked subscribers,
   **When** the operator requests stats, **Then** they see the total count
   and the breakdown by state.
2. **Given** a non-operator subscriber, **When** they attempt to request
   stats, **Then** the system refuses.

---

### Edge Cases

- What happens when a post contains both the designated jar link and is
  otherwise composed only of digits? The jar-link rule takes precedence —
  the post is still delivered to all active subscribers.
- What happens when a subscriber pauses and then adds or removes keywords
  while paused? The changes are saved normally; they simply take effect
  once the subscriber resumes.
- What happens when many posts match many subscribers' keywords in a short
  burst? Every matching subscriber still eventually receives their
  notification; delivery may be briefly queued but is never dropped.
- What happens when a subscriber who has never registered tries to add a
  keyword? Registration happens automatically as part of their first
  interaction with the bot.
- What happens when a new content-handling rule is added later (beyond
  jar-link detection, bare-number suppression, and keyword matching)? It is
  inserted into the ordered rule sequence at the appropriate position;
  existing rules and their outcomes are unaffected.
- What happens when a blocked subscriber requests deletion of their own
  data? It succeeds regardless of block status (FR-023) — the block only
  restricts notifications and other commands, never the ability to erase
  one's own data.
- What happens if the operator tries to block or unblock themselves, or
  broadcast/view stats using a subscriber identity? The operator is
  identified by a fixed configuration value distinct from any Subscriber
  record (FR-017), so this scenario doesn't arise.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a person register as a subscriber through
  their first interaction with the bot, with no separate signup step.
- **FR-002**: System MUST let a subscriber add a personal keyword, rejecting
  any keyword shorter than 3 characters with an explanatory message.
- **FR-003**: System MUST cap each subscriber at 20 saved keywords,
  rejecting further additions past that limit with an explanatory message.
- **FR-004**: System MUST treat keyword matching and storage as
  case-insensitive, and MUST NOT create a duplicate entry when a subscriber
  adds a keyword they already have saved.
- **FR-005**: System MUST let a subscriber view the complete list of their
  currently saved keywords.
- **FR-006**: System MUST let a subscriber remove a previously saved
  keyword, and MUST inform them clearly if the keyword they tried to remove
  was not found.
- **FR-007**: System MUST detect, in real time, when a new post to the
  monitored channel contains one or more of a subscriber's active keywords
  as a substring, regardless of letter case.
- **FR-008**: System MUST deliver exactly one notification per matching post
  per subscriber, even when multiple of that subscriber's keywords match
  the same post.
- **FR-009**: Each notification MUST include the matched post's text and a
  way for the subscriber to open the original post in the channel.
- **FR-010**: System MUST let a subscriber pause notifications at any time
  without deleting their saved keyword list.
- **FR-011**: System MUST let a paused subscriber resume notifications,
  immediately restoring delivery against their existing keyword list with
  no reconfiguration required.
- **FR-012**: System MUST NOT deliver any notification, of any kind, to a
  paused subscriber.
- **FR-013**: System MUST deliver every post containing the designated
  jar-link pattern to all active, non-blocked subscribers, regardless of
  their personal keyword lists.
- **FR-014**: System MUST NOT deliver a notification to anyone for a post
  whose entire content consists only of a number (digits and common numeric
  punctuation, with no other text).
- **FR-015**: System MUST persist each subscriber's keyword list and
  paused/active state so that it survives a restart of the service with no
  data loss and no required reconfiguration.
- **FR-016**: System MUST evaluate every channel post against its
  content-handling rules (jar-link detection, bare-number suppression,
  keyword matching, and any rules added later) as an ordered, extensible
  sequence: rules are checked in a fixed order, the first rule that applies
  determines the outcome for that post, and no further rules are checked
  once one applies. It MUST be possible to add a new rule to this sequence
  in the future without changing the behavior of any existing rule.
- **FR-017**: System MUST recognize exactly one operator, identified by a
  fixed configuration value for the deployment (not a role a subscriber can
  request or be granted at runtime).
- **FR-018**: System MUST refuse any admin-only action (broadcast, stats,
  block, unblock) attempted by anyone other than the operator, with an
  explanatory message.
- **FR-019**: System MUST let the operator send a broadcast message that is
  delivered to every active, non-blocked subscriber, independent of any
  channel post.
- **FR-020**: System MUST let the operator view the total number of
  registered subscribers and their breakdown by state (active, paused,
  blocked).
- **FR-021**: System MUST let the operator block a specific subscriber,
  which immediately stops all delivery to them (keyword, jar-link, and
  broadcast) regardless of their own active/paused state, and causes their
  subsequent commands to be refused with an explanatory message.
- **FR-022**: System MUST let the operator unblock a previously blocked
  subscriber, immediately restoring their prior active/paused state and
  normal command access.
- **FR-023**: System MUST let any subscriber permanently delete their own
  subscriber record and all their keywords on request. This MUST succeed
  even if the subscriber is currently blocked — deleting one's own data is
  never restricted by a block.
- **FR-024**: Once a subscriber's data is deleted, System MUST NOT deliver
  any further notification tied to their old identity, and MUST treat their
  next interaction with the bot as a new registration with no keywords
  carried over.
- **FR-025**: All bot-authored text (confirmations, errors, help text,
  admin replies) MUST be written in Ukrainian. This does not affect
  re-posted channel content or subscriber-supplied keywords, which are
  always shown/matched as-is regardless of language.

### Key Entities

- **Subscriber**: A person interacting with the bot. Has an identity, an
  active/paused state, a blocked/unblocked state (set only by the
  operator, and overriding active/paused while set), and a personal list
  of keywords. Deletion is a terminal action: the record and all its
  keywords are removed entirely, not merely marked inactive; a later
  interaction creates a brand-new Subscriber record.
- **Operator**: The single administrator of the deployment, identified by a
  fixed configuration value rather than a per-subscriber flag. Can
  broadcast, view stats, and block/unblock subscribers; is not itself a
  Subscriber record.
- **Keyword**: A short text fragment (minimum 3 characters) a subscriber
  wants to be alerted about. Belongs to exactly one subscriber; a
  subscriber may have up to 20.
- **Channel Post**: A message published to the single monitored source
  channel; the content being scanned for keyword matches, jar-link
  detection, and bare-number suppression.
- **Notification**: An alert delivered to a subscriber, referencing exactly
  one channel post, containing that post's text and a way to reach the
  original.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A subscriber receives a notification for a matching post
  within 5 seconds of that post being published, under normal operation.
- **SC-002**: The system supports at least 100 concurrent subscribers with
  up to 20 keywords each without missing or measurably delaying deliveries.
- **SC-003**: Subscribers never receive more than one notification for the
  same post, regardless of how many of their keywords match it.
- **SC-004**: 100% of posts containing the designated jar link reach every
  active subscriber.
- **SC-005**: 100% of posts whose entire content is just a number result in
  zero notifications sent.
- **SC-006**: A paused subscriber receives zero notifications until they
  resume, and upon resuming, 100% of their previously saved keywords are
  immediately active again with no manual re-entry.
- **SC-007**: All subscriber configuration (keywords, pause state) survives
  a service restart with zero data loss.
- **SC-008**: A new content-handling rule can be added to the system's
  rule sequence without modifying or re-testing the behavior of existing
  rules.
- **SC-009**: 100% of operator broadcasts reach every active, non-blocked
  subscriber and no one else.
- **SC-010**: A blocked subscriber receives zero notifications and cannot
  successfully run any command until the operator unblocks them.
- **SC-011**: 100% of subscribers who request data deletion have their
  record and keywords fully removed, with zero subsequent notifications
  tied to that old identity.

## Assumptions

- The monitored source channel is fixed for this deployment; selecting or
  monitoring multiple channels is out of scope for this version.
- The source channel's posts are plain text; matching against media
  captions or media-only posts is out of scope for this version.
- The jar-link pattern that triggers guaranteed delivery is a single, fixed,
  known pattern for this version, not a user- or subscriber-configurable
  value.
- Subscribers interact with the system exclusively through the bot; no
  other interface is in scope.
- Expected scale for this version is roughly 100 subscribers with up to 20
  keywords each, consistent with the source channel's posting volume.
- There is exactly one operator for this deployment, identified by a fixed
  configuration value set up alongside the source channel configuration;
  there is no multi-admin or role-request flow in this version.
- The bot's audience is Ukrainian-speaking; all bot-authored UI text is in
  Ukrainian, with no multi-language/subscriber-selectable option in this
  version.
