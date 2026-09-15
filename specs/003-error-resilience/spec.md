# Feature Specification: Runtime Error Resilience

**Feature Branch**: `003-error-resilience`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Error resilience for the bot's long-running processes (notifier, Telethon listener, aiogram polling). Incident: notifier crashed sending a notification to a subscriber who had blocked the bot, which took down the entire bot process; the process then hung instead of exiting, so it never restarted, leaving the bot silently non-functional for ~8 hours. Approved design: per-component supervisors that log and restart a failed component after a fixed ~2s delay; the notifier must never let one subscriber's failure stop delivery to the rest of the queue; a subscriber who has blocked the bot must be marked blocked automatically instead of crashing anything; a top-level safety net must guarantee the process actually exits if something escapes all supervision, so systemd's restart-on-failure is a real last resort."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One failed delivery never stops the rest of the queue (Priority: P1)

A channel post matches keywords for many subscribers. One of those subscribers has blocked the bot in Telegram. Today, that single failed delivery crashes the entire bot process and every other subscriber silently stops receiving notifications — sometimes for hours — until someone notices and manually restarts it.

**Why this priority**: This is the exact incident that just happened in production and is the most damaging failure mode: a single, routine, expected event (a user blocking the bot) causes total, silent service loss for every other subscriber.

**Independent Test**: Queue notifications for several subscribers where one is known to have blocked the bot; verify every other subscriber still receives their notification and the bot keeps running afterward.

**Acceptance Scenarios**:

1. **Given** a notification queue containing jobs for multiple subscribers, **When** delivery to one subscriber fails because that subscriber has blocked the bot, **Then** the bot marks that subscriber as blocked and continues delivering to all remaining subscribers in the queue without interruption.
2. **Given** a notification queue containing jobs for multiple subscribers, **When** delivery to one subscriber fails for any other reason (e.g. an unexpected/unrecognized delivery error), **Then** the bot logs the failure, skips that job, and continues delivering to all remaining subscribers without crashing.
3. **Given** a subscriber has just been marked blocked after a failed delivery, **When** a future channel post matches that subscriber's keywords, **Then** the bot does not attempt delivery to that subscriber again.

---

### User Story 2 - A failed component recovers on its own (Priority: P1)

The bot is made of independent long-running parts: it listens to the source channel, it answers subscriber commands, and it delivers queued notifications. Today, an unexpected failure in any one part brings down the whole bot, and worse, can leave it in a state where the operating system still reports it "running" while it does nothing at all. Nobody should have to notice and manually restart the bot for it to keep working.

**Why this priority**: Equal in importance to User Story 1 — this is the general mechanism that makes the whole bot self-healing rather than fragile to any single unexpected error, and it directly addresses why the last incident went undetected for hours (the bot appeared "running" but was completely dead).

**Independent Test**: Deliberately fail one part of the bot (e.g. simulate a channel-listening failure) while leaving the others untouched; verify that part recovers on its own within seconds and the other parts were never interrupted.

**Acceptance Scenarios**:

1. **Given** the bot is running normally, **When** the channel-listening component fails unexpectedly, **Then** it is automatically restarted within a few seconds, without operators being paged and without interrupting command-answering or notification delivery.
2. **Given** the bot is running normally, **When** the command-answering component fails unexpectedly, **Then** it is automatically restarted within a few seconds, without interrupting channel listening or notification delivery.
3. **Given** the bot is running normally, **When** the notification-delivery component fails unexpectedly for a reason not already covered by User Story 1, **Then** it is automatically restarted within a few seconds, without interrupting the other components.
4. **Given** a component keeps failing repeatedly (e.g. a persistent misconfiguration), **When** each restart attempt also fails, **Then** the bot keeps retrying at a steady, bounded pace rather than failing permanently or overwhelming the system with rapid retries.

---

### User Story 3 - A total failure is never invisible (Priority: P2)

If something goes so wrong that it escapes recovery entirely (a scenario the operator hopes never happens, but must be protected against), the bot must not end up in the same "looks alive, does nothing" state that caused the last incident to go unnoticed for 8 hours. It must stop in a way that visibly triggers the existing automatic restart safety net.

**Why this priority**: Lower priority than User Stories 1-2 because it's a last-resort backstop expected to rarely trigger — but it's what makes the difference between a brief blip and another multi-hour silent outage, so it must exist.

**Independent Test**: Force a failure that bypasses per-component recovery entirely; verify the bot process actually terminates (rather than hanging) so the existing service-restart mechanism takes over.

**Acceptance Scenarios**:

1. **Given** a failure occurs that is not recoverable by any individual component's automatic restart, **When** that failure reaches the top of the bot, **Then** the bot process terminates promptly rather than continuing to run in a non-functional state.

---

### Edge Cases

- What happens when a subscriber blocks the bot, then later unblocks it and sends `/start` again? (Existing subscriber-reactivation behavior should apply; being marked blocked must not be permanent or prevent the subscriber from resubscribing.)
- What happens when the notification queue itself is empty and idle for a long time — does the recovery mechanism ever fire unnecessarily? It must not: recovery only activates on an actual failure, never during normal idle waiting.
- What happens if a component fails immediately again right after being restarted (a fast, repeating failure)? Restarts continue at the same steady pace rather than escalating or giving up, per User Story 2's acceptance scenario 4.
- What happens if two or more components fail around the same time? Each recovers independently; one component's failure and restart must have no effect on the others' operation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST continue delivering queued notifications to all other subscribers when delivery to one subscriber fails, regardless of the reason for that failure.
- **FR-002**: The system MUST detect when a subscriber has blocked the bot and automatically mark that subscriber as blocked so no further delivery attempts are made to them.
- **FR-003**: The system MUST NOT lose or silently drop notifications for subscribers other than the one whose delivery failed (the negative-framing complement of FR-001: FR-001 states the continuity guarantee, FR-003 states the corresponding non-loss guarantee it implies).
- **FR-004**: The system MUST treat each of the following as an independently recoverable component: channel listening, subscriber command handling, and notification delivery.
- **FR-005**: The system MUST automatically restart a failed component on its own, without manual/operator intervention, within a bounded, short amount of time of the failure being detected.
- **FR-006**: A failure in one component MUST NOT interrupt or degrade the operation of the other components.
- **FR-007**: The system MUST retry a repeatedly failing component at a steady, bounded pace rather than stopping permanently or retrying without any pause.
- **FR-008**: The system MUST record (log) every component failure and every automatic recovery action so operators can review what happened after the fact.
- **FR-009**: If a failure occurs that is not handled by a component's own automatic recovery, the system MUST terminate the bot process rather than leaving it running in a non-functional state.
- **FR-010**: A subscriber previously marked blocked MUST be able to resume receiving notifications through the existing resubscription flow, unaffected by this feature.

### Key Entities

- **Subscriber block status**: Whether a given subscriber has blocked the bot; once known, delivery attempts to that subscriber stop until they resubscribe. This reuses the subscriber's existing blocked/active status rather than introducing a new concept.
- **Bot component**: One of the bot's independent long-running responsibilities (channel listening, command handling, notification delivery) that can fail and recover on its own without affecting the others.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A subscriber blocking the bot never causes any interruption in notification delivery to other subscribers — 100% of unaffected subscribers continue receiving matching notifications.
- **SC-002**: Any single-component failure is automatically recovered from within 10 seconds, with zero required operator action.
- **SC-003**: Time between a total service failure occurring and the bot resuming normal operation drops from ~8 hours (the incident that prompted this feature) to under 1 minute.
- **SC-004**: Across a rolling 30-day window, zero incidents require an operator to manually notice and restart the bot due to an unhandled runtime error.

## Assumptions

- The existing subscriber "blocked" status (already used to skip blocked subscribers in broadcasts and to refuse blocked subscribers' commands) is the correct mechanism to reuse for automatically-detected blocks — no new subscriber state is introduced.
- "A bounded, short amount of time" for component recovery (FR-005) and "steady, bounded pace" for repeated retries (FR-007) means a fixed, small delay (on the order of a couple of seconds) rather than escalating backoff — confirmed with the feature owner during design.
- The bot already runs under a process supervisor (systemd) configured to restart it on failure; this feature is responsible for making sure the process actually reaches that "failed and needs restarting" state instead of hanging, not for replacing that outer supervisor.
- Notification ordering across subscribers is not a requirement this feature needs to preserve beyond what already exists today.
- This feature governs the bot's runtime behavior only; it does not change what triggers a notification or who is eligible to receive one.
