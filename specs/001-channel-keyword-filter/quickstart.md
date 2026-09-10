# Quickstart: Channel Keyword Filter

Validation guide for confirming the feature works end-to-end. For automated
verification, see the test suite (`tests/unit`, `tests/integration`) — this
guide is for the pieces that require real Telegram credentials and can't be
unit-tested (per plan.md's Testing note).

## Prerequisites

- Python 3.11+
- A Telegram account that can join the public source channel (for the
  userbot) — its `api_id`/`api_hash` from https://my.telegram.org
- A bot token from `@BotFather`
- The source channel's public `@username`

## Setup

1. Install dependencies (see `tasks.md` for the exact dependency list once
   generated).
2. Create a `.env` file in the repo root:
   ```
   API_ID=...
   API_HASH=...
   BOT_TOKEN=...
   SOURCE_CHANNEL=@your_channel_username
   ADMIN_CHAT_ID=your_own_chat_id
   DB_PATH=./channel_filter.db
   ```
   `ADMIN_CHAT_ID` is your own Telegram chat ID (message `@userinfobot` or
   similar to find it) — this is the one account that can use the admin
   commands in scenario 8 below.
3. Run the app once interactively: `python -m channel_filter.main`. On first
   run, Telethon prompts for the phone number and login code for the
   account joining the source channel — this happens once; a local
   `.session` file persists it afterward.

## Validation scenarios

Each scenario below maps to an acceptance scenario in `spec.md`.

### 1. Core keyword match and delivery (User Story 1)

1. Message the bot `/start`, then `/add sale`.
2. Publish a post to the source channel containing "Sale" (any case).
3. **Expected**: within a few seconds, the bot sends a message containing
   the post's text and a "🔗 View original" button linking to the post.
4. Publish a post containing "sale" twice, or containing both "sale" and
   another of your keywords.
5. **Expected**: exactly one notification is received for that post, not
   one per match.

### 2. Keyword list management (User Story 2)

1. `/add discount`, then `/list` — both `sale` and `discount` appear.
2. `/remove sale`, then `/list` — only `discount` remains.
3. `/remove sale` again — bot replies that it wasn't found.
4. `/add discount` again — bot confirms it's already saved, no duplicate.
5. Add keywords until 20 are saved, then attempt a 21st — bot explains the
   limit.

### 3. Pause and resume (User Story 3)

1. With `discount` saved and active, `/stop`.
2. Publish a post containing "discount".
3. **Expected**: no notification arrives.
4. `/start` again.
5. Publish another post containing "discount".
6. **Expected**: notification arrives, with no need to re-add the keyword.

### 4. Jar-link broadcast (User Story 4)

1. With at least two subscribers, one with no matching keywords, publish a
   post containing `https://send.monobank.ua/jar/...`.
2. **Expected**: every active subscriber receives it, including the one
   with no matching keywords. A paused subscriber receives nothing.

### 5. Bare-number suppression (User Story 5)

1. With a subscriber whose keyword is `280` (numeric), publish a post whose
   entire content is `2800`.
2. **Expected**: no notification is sent to anyone.
3. Publish a post `2800 UAH raised`.
4. **Expected**: normal keyword/jar-link handling applies (this post is not
   suppressed, since it isn't *only* a number).

### 6. Permanent data deletion (User Story 6)

1. With `discount` saved, send `/deleteme`.
2. **Expected**: bot confirms full deletion.
3. Publish a post containing "discount".
4. **Expected**: no notification (this chat is no longer a subscriber).
5. Send `/start` again, then `/list`.
6. **Expected**: treated as a brand-new subscriber — empty keyword list.

### 7. Operator blocks and unblocks a subscriber (User Story 7)

1. As a non-operator test subscriber, note your `chat_id`.
2. As the operator (the account matching `ADMIN_CHAT_ID`), send
   `/block <that chat_id>`.
3. Publish a post containing that subscriber's keyword, and separately a
   jar-link post.
4. **Expected**: the blocked subscriber receives neither.
5. As the blocked subscriber, try `/add somethingnew`.
6. **Expected**: refused with a "you are blocked" reply.
7. As the blocked subscriber, send `/deleteme`.
8. **Expected**: succeeds anyway (blocking never restricts self-deletion).
9. As a still-blocked (undeleted) test subscriber instead, as the operator
   send `/unblock <chat_id>`.
10. **Expected**: that subscriber's prior active/paused state and normal
    command access are restored.
11. As a non-operator subscriber, attempt `/block <any chat_id>`.
12. **Expected**: refused — admin commands are operator-only.

### 8. Operator broadcast and stats (User Story 8, 9)

1. As the operator, send `/broadcast Тестове повідомлення`.
2. **Expected**: every active, non-blocked subscriber receives that exact
   text; a paused or blocked subscriber does not.
3. As the operator, send `/stats`.
4. **Expected**: the reply shows the total subscriber count and the
   active/paused/blocked breakdown, matching what you'd expect from the
   subscribers exercised in the scenarios above.
5. As a non-operator subscriber, attempt `/broadcast` or `/stats`.
6. **Expected**: refused for both.

## Automated test run

```bash
pytest tests/unit
pytest tests/integration
```

All pipeline-stage, matcher, DB, and bot-command behavior above is covered
by these suites without needing live Telegram credentials; only the setup
steps and manual scenarios above require a real account/channel/bot.
