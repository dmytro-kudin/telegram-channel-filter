# Phase 0 Research: Channel Keyword Filter

All Technical Context items were already decided during the brainstorming
session (see `docs/superpowers/specs/2026-09-10-telegram-channel-filter-design.md`),
so there are no unresolved `NEEDS CLARIFICATION` markers. This document
records the supporting rationale and alternatives for each technology
choice and integration pattern, per Phase 0 requirements.

## 1. Running a userbot and a bot in one process

**Decision**: Run Telethon's client and aiogram's polling dispatcher
concurrently in a single `asyncio` event loop via `asyncio.gather`, started
only after the initial automaton build completes.

**Rationale**: Both are native `asyncio` libraries; a single event loop
avoids inter-process communication (queues, sockets, or a broker) for
passing detected matches from the listener to the sender, which is
unnecessary complexity at this scale (≤100 subscribers, ≤2 posts/sec).

**Alternatives considered**: Two separate processes (listener + bot)
communicating over a local queue/socket — rejected as needless operational
complexity (two processes to supervise, restart, and keep in sync) for a
workload this small; a message broker (Redis/RabbitMQ) — rejected for the
same reason, and it would also violate the <150MB RAM / single-core
resource constraint for no corresponding benefit.

## 2. Why a userbot is required at all

**Decision**: Telethon (MTProto) joined to the source channel as an
ordinary subscriber is required for detection; the bot cannot receive
`channel_post` updates or use `forwardMessage` for a channel it hasn't
joined, even though the channel is public.

**Rationale**: Confirmed against reported Telegram Bot API behavior:
`forwardMessage` returns "message to forward not found" for channels the
bot isn't a member of, a restriction present since Bot API 3.4, and there is
no Bot API mechanism to subscribe to an arbitrary channel's posts without
membership. Since the operator cannot add the bot to this channel, a
userbot is the only way to detect posts in real time.

**Alternatives considered**: Bot-only polling of the public channel preview
page (`t.me/s/<channel>`) — rejected as fragile HTML scraping, against
typical ToS expectations, and unnecessary given Telethon already solves
this cleanly; asking the channel owner to add the bot — rejected, out of
the operator's control per the feature's stated constraint.

## 3. Delivering matches without native forward

**Decision**: Re-post the captured text as a new bot message with an inline
"🔗 View original" button linking to `https://t.me/<channel_username>/<message_id>`.

**Rationale**: True `forwardMessage`/`copyMessage` both require bot
membership in the source chat (see #2), which isn't available. Because the
channel is public, its permalink format works for any user without
requiring channel membership, fully satisfying the "navigate to source"
need established in the design phase.

**Alternatives considered**: Have the Telethon account itself message
users — rejected because it would expose the operator's personal account
to end users, breaking the "bridge" design where subscribers only ever
interact with the official bot.

## 4. Aho-Corasick automaton rebuild strategy

**Decision**: On every keyword mutation, build a brand-new
`ahocorasick.Automaton` off to the side from a fresh DB read, call
`make_automaton()`, then reassign the manager's single object reference.
Serialize rebuild triggers with an `asyncio.Lock` so concurrent `/add`/
`/remove` calls don't waste redundant work.

**Rationale**: `pyahocorasick` doesn't support safe incremental removal of
words from a built automaton; a full rebuild is the documented pattern for
mutable keyword sets. At ≤2000 total keywords, a full rebuild is
sub-millisecond, so a from-scratch rebuild per mutation is simpler and just
as fast as any incremental scheme would be at this scale. A single
attribute reassignment is safe under CPython's GIL, so readers never
observe a partially-built automaton without needing an explicit read lock.

**Alternatives considered**: Incremental automaton patching — rejected,
not supported by the library and unnecessary at this scale; a read-write
lock around every match lookup — rejected as unneeded overhead given the
atomic-reference-swap approach already avoids torn reads.

**Constitution compliance note**: `make_automaton()` is a synchronous,
CPU-bound C call. Per Coding Standards ("Async code... MUST NOT perform
blocking I/O or CPU-bound work directly; blocking calls MUST be dispatched
via `asyncio.to_thread`"), the build step MUST run as
`await asyncio.to_thread(automaton.make_automaton)` rather than being
called directly from the async rebuild coroutine. The rule has no
scale-based exception — sub-millisecond cost doesn't exempt it — and
wrapping it costs nothing but a single coroutine hop, so there's no reason
to take the direct-call shortcut even though it would be imperceptible at
this scale.

## 5. Rate limiting and flood-wait handling

**Decision**: A single global `asyncio.Queue` feeding one sender task that
enforces a token bucket capped at ~25 messages/sec. On aiogram's
`TelegramRetryAfter` exception, sleep for `retry_after` and requeue the
item rather than dropping it.

**Rationale**: Telegram's Bot API imposes a ~30 msg/sec bot-wide cap; aiogram
doesn't include a built-in global throttle, so the common pattern is a
hand-rolled queue + token bucket that explicitly stays under the cap and
reacts to `TelegramRetryAfter` when it does occur. Because each subscriber
gets at most one notification per source post (deduped in the keyword
stage) and posts arrive at ≤2/sec, the shared global throttle is sufficient
without separate per-chat pacing logic.

**Alternatives considered**: A third-party throttling middleware — rejected
as an extra dependency for a few dozen lines of well-understood logic;
per-chat rate limiters — rejected as unneeded complexity given the traffic
profile (§7 of the design doc).

## 6a. Filtering out paused/blocked subscribers in the automaton (added after clarify session)

**Decision**: The automaton rebuild query joins `keywords` to `subscribers`
and only includes rows where `active = 1 AND blocked = 0`. Rebuilds are
triggered not just on keyword add/remove, but on any subscriber
active/paused/blocked state change and on self-service deletion.

**Rationale**: This makes the keyword-match stage's `MatchedUsers` result
correct by construction — it only ever contains eligible subscriber IDs, so
no extra per-notification eligibility check is needed at match time. It
directly satisfies FR-012 (no notification to paused), FR-021 (blocked
overrides own state), and FR-024 (deleted subscribers stop matching)
without adding a second filtering pass.

**Alternatives considered**: Keep the automaton keyed on all keywords
regardless of eligibility, and filter the matched set against a live
eligibility check before enqueueing — rejected as an unnecessary extra
DB round-trip per matched post when the rebuild-time filter achieves the
same correctness for free at this scale.

## 6b. Operator authorization as a single decorator

**Decision**: One `require_operator` decorator in `auth.py`, applied to the
three admin-only aiogram handlers (`/broadcast`, `/stats`, `/block`,
`/unblock`), comparing the incoming `chat_id` against the single configured
`ADMIN_CHAT_ID` and replying with a Ukrainian "not authorized" message
(FR-018) before the handler body runs otherwise.

**Rationale**: Constitution Principle IV requires cross-cutting concerns
(here, authorization) to live outside business logic as a reusable
decorator rather than an `if chat_id != ADMIN_CHAT_ID: ...` check repeated
in each of the four admin handlers.

**Alternatives considered**: A separate aiogram filter/middleware scoped to
an admin-only router — functionally equivalent; the decorator was chosen
for locality and simplicity given there are only four admin handlers, but
either satisfies the constitution's requirement equally well.

## 6c. Broadcast is not part of the channel-post pipeline

**Decision**: `/broadcast` is a distinct data flow from the jar-link/
pure-number/keyword pipeline (FR-016). It doesn't originate from a
`ChannelPost` at all — the operator's admin handler queries the DB directly
for all currently eligible (`active=1, blocked=0`) subscriber IDs and
enqueues a `NotificationJob` per subscriber straight onto the same
`notifier.py` queue used for pipeline-driven deliveries.

**Rationale**: Keeps the pipeline's contract (`Stage: ChannelPost -> Outcome`)
unchanged and honest — a manual broadcast has no source post to evaluate
rules against, so forcing it through the pipeline would mean inventing a
fake `ChannelPost` for no benefit. Reusing the same delivery queue still
gets broadcast messages the same rate-limiting and flood-wait retry
behavior as every other notification.

**Alternatives considered**: Model broadcast as a synthetic `ChannelPost`
that always short-circuits at a new first pipeline stage — rejected as
indirection with no payoff; it would also make `BroadcastAll` overload two
different meanings (jar-link-triggered vs. operator-triggered) for no
gain in testability or clarity.

## 7. Session and configuration management

**Decision**: `.env` file (gitignored) for `API_ID`/`API_HASH`/`BOT_TOKEN`/
`SOURCE_CHANNEL`/`ADMIN_CHAT_ID`/`DB_PATH`; Telethon's default local
`.session` file for
the one-time interactive login, persisted across restarts.

**Rationale**: Matches the single-server deployment profile — no need for
the session to be portable across hosts. Simplest possible setup for a
single operator running one instance.

**Alternatives considered**: `StringSession` stored as an environment
variable for a fully stateless/portable deployment — rejected as
unnecessary given this is a single, long-running instance, not a
horizontally-scaled or frequently-redeployed service.

## 8. Deployment target: Oracle Cloud Infrastructure Always Free tier (added after initial plan)

**Decision**: Deploy to a single Oracle Cloud Always-Free VM. Default to
the `VM.Standard.E2.1.Micro` x86_64 shape (1/8 OCPU, 1GB RAM) with the
SQLite file, `.session` file, and `.env` all stored on the VM's persistent
boot volume, and the process supervised by a systemd unit
(`Restart=on-failure`, `WantedBy=multi-user.target`) so it survives both
crashes and VM reboots without manual intervention.

**Rationale**: The E2.1.Micro shape's 1GB RAM / 1/8 OCPU already exceeds
plan.md's stated steady-state budget (<150MB RAM, single core), so no
resource-driven redesign is needed. Always Free carves out 2 such
instances plus up to 200GB of block storage at no cost, which is more than
this single-process bot needs. Because the bot only opens outbound
connections (Telethon's MTProto client, aiogram's long-polling to the Bot
API) and never listens for inbound traffic, Oracle's default VCN security
list (which allows all outbound, denies inbound by default) requires no
changes — no port needs to be opened. Continuous 24/7 operation of the VM
and its bot process also avoids Oracle's idle-resource reclamation policy,
which targets stopped/unused Always Free resources, not actively running
ones.

**Alternatives considered**: The Ampere A1 Always-Free shape (ARM64, up to
4 OCPU / 24GB, can be split across instances) — more headroom than this
workload needs, and left as an optional upgrade path rather than the
default, since `pyahocorasick`'s C extension would need its `aarch64` wheel
availability (or successful source build via `pip`, which requires a C
toolchain to be present on the image) confirmed before relying on it;
`x86_64` has no such open question. A managed container platform (Oracle
Container Instances, or a Kubernetes-based approach) — rejected as
unnecessary operational overhead for a single always-on process with no
scaling or multi-service requirements, and it would complicate persisting
the SQLite file and `.session` file across restarts for no benefit at this
scale.
