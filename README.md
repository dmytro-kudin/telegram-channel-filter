# telegram-channel-filter

A Telegram bot that watches one public channel and notifies each subscriber
only about the posts they actually care about — matched against their own
personal keyword list — instead of every post in the channel.

## What it does

Subscribers talk to a Telegram bot (`@BotFather`-issued bot) and register
keywords (e.g. `sale`, `discount`). A separate account ("userbot") is
subscribed to the monitored source channel and watches every new post in
real time. When a post arrives, it's run through an ordered set of rules:

1. **Jar-link broadcast** — a post containing a fixed donation-jar link
   (`send.monobank.ua/jar/...`) is sent to *every* active subscriber,
   regardless of their keywords.
2. **Bare-number suppression** — a post whose entire content is just a
   number (digits and common punctuation, nothing else) is dropped for
   everyone — numeric noise isn't useful on its own.
3. **Keyword matching** — otherwise, the post is scanned (case-insensitively)
   for every active subscriber's keywords; each subscriber with at least one
   match gets exactly one notification for that post, with a button linking
   back to the original message in the channel.

Subscribers manage everything through bot commands or a persistent reply
keyboard: add/remove keywords, list their keywords, pause/resume
notifications, or permanently delete their data. One configured operator
account gets extra commands: block/unblock a subscriber, broadcast an
arbitrary message, and view subscriber stats. All bot-authored text is in
Ukrainian (subscriber-supplied keywords and re-posted channel content are
left as-is).

The three long-running parts of the bot (channel listening, command
handling, notification delivery) each run under their own supervisor: an
unhandled failure in one is logged and that part alone restarts a couple of
seconds later, without affecting the other two or losing queued
notifications for anyone else.

See `specs/001-channel-keyword-filter`, `specs/002-button-driven-ux`, and
`specs/003-error-resilience` for the full, authoritative behavior
specifications this implementation follows.

## Architecture

Two Telegram clients share one SQLite database and one in-process
notification queue, all run concurrently inside a single Python process:

```
┌─────────────────────┐        ┌──────────────────────────┐
│   Source channel     │        │   Subscribers (Telegram) │
│   (public, read-only) │        │  /start /add /list ...   │
└─────────┬────────────┘        └─────────────┬─────────────┘
          │ new posts                          │ commands / taps
          ▼                                    ▼
 ┌────────────────────┐              ┌──────────────────────┐
 │ Telethon "userbot"  │              │ aiogram Bot + Router  │
 │   listener.py       │              │   bot.py               │
 │ (reads the channel) │              │ (answers subscribers   │
 │                      │              │  and the operator)     │
 └─────────┬────────────┘              └──────────┬────────────┘
           │ ChannelPost                            │ reads/writes
           ▼                                        ▼
   ┌───────────────┐                        ┌───────────────────┐
   │  pipeline.py   │──rebuild on change──▶ │ matcher.py          │
   │ ordered rule   │◀── AutomatonManager ──│ Aho-Corasick        │
   │   stages       │   (keyword matching)  │ automaton over all  │
   └──────┬─────────┘                        │ active keywords     │
          │ Outcome (Skip / BroadcastAll /   └───────────────────┘
          │           MatchedUsers)
          ▼
   ┌───────────────┐        ┌─────────────────┐        ┌──────────────┐
   │ notifier.py    │──────▶│ asyncio.Queue    │──────▶│ Telegram Bot  │
   │ enqueue jobs   │       │ + rate limiter   │       │ API send call │
   └───────────────┘        │ (25 msg/s cap)   │       └──────────────┘
                             └─────────────────┘

                       ┌─────────────────────────┐
                       │      db.py (aiosqlite)   │
                       │ subscribers + keywords    │
                       │  (single SQLite file)     │
                       └─────────────────────────┘
```

- **`listener.py`** — a Telethon client logged in as a regular Telegram
  account, subscribed to `SOURCE_CHANNEL`. On every new message it builds a
  `ChannelPost` and runs it through the pipeline.
- **`pipeline.py`** — an ordered, short-circuiting list of stages
  (`jar_link_stage`, `pure_number_stage`, `keyword_match_stage`). The first
  stage that doesn't return `Continue()` decides the outcome; new rules can
  be inserted without touching existing ones.
- **`matcher.py`** — an Aho-Corasick automaton (`pyahocorasick`) built over
  every active, non-blocked subscriber's keywords, mapping each substring to
  the set of subscribers who saved it. Rebuilt (and atomically swapped) any
  time a keyword or subscriber state changes, so matching itself stays O(text
  length) regardless of subscriber count.
- **`notifier.py`** — a single `asyncio.Queue` plus one sender task,
  throttled to a safe rate for the Telegram Bot API. A delivery failure
  because a subscriber blocked the bot marks them `blocked` in the DB; any
  other delivery failure is logged and skipped — neither stops the queue.
- **`bot.py`** — the aiogram `Router` with all subscriber and operator
  command handlers, plus the guided "add a keyword" conversation (aiogram
  FSM) and the inline keyword-list/delete-confirmation flow.
- **`auth.py`** — cross-cutting `@require_operator` / `@refuse_if_blocked`
  decorators so authorization never has to be re-checked inside individual
  handlers.
- **`db.py`** — schema + all subscriber/keyword CRUD over a single SQLite
  file via `aiosqlite`. `subscribers` and `keywords` are the only two tables.
- **`main.py`** — startup wiring. Runs the Telethon listener, the aiogram
  poller, and the notifier concurrently, each wrapped in its own
  `supervise()` loop that catches any unhandled exception, logs it, and
  restarts just that component after a fixed delay. If something escapes
  every supervisor, the process exits immediately (`os._exit(1)`) instead of
  hanging, so the OS-level restart policy (systemd `Restart=on-failure`) is
  the real last resort.

### Why one process, two Telegram clients

A bot account (`BOT_TOKEN`) can never read the contents of a channel it
merely administers via the Bot API in real time the way this project needs;
a regular account added to the channel can. So a userbot (Telethon) does the
reading, and a bot (aiogram) does the talking to subscribers — sharing the
same SQLite connection and matcher instance in one process keeps the whole
system simple to run and reason about at this project's scale (~100
subscribers).

## Tech stack

- Python 3.11+, `asyncio`
- [Telethon](https://docs.telethon.dev/) — userbot client reading the source channel
- [aiogram 3](https://docs.aiogram.dev/) — subscriber/operator-facing bot
- [pyahocorasick](https://github.com/WojciechMula/pyahocorasick) — keyword matching automaton
- [aiosqlite](https://github.com/omnilib/aiosqlite) — async SQLite access
- [python-dotenv](https://github.com/theskumar/python-dotenv) — `.env` loading
- [uv](https://docs.astral.sh/uv/) — dependency management and running
- `pytest` / `pytest-asyncio` — test suite

## Getting started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A Telegram account that can see the source channel — its `api_id`/`api_hash`
  from https://my.telegram.org
- A bot token from [@BotFather](https://t.me/BotFather)
- The source channel's public `@username`
- Your own Telegram chat ID (e.g. via [@userinfobot](https://t.me/userinfobot)) to use as `ADMIN_CHAT_ID`

### Setup

```bash
git clone <this-repo>
cd telegram-channel-filter
uv sync
cp .env.example .env
# then edit .env with your real values
```

`.env` fields (see `.env.example` for the annotated template):

| Variable | Description |
| --- | --- |
| `API_ID` / `API_HASH` | Telethon app credentials from my.telegram.org, for the account that reads the source channel |
| `BOT_TOKEN` | Bot token from @BotFather, for the subscriber-facing bot |
| `SOURCE_CHANNEL` | Public `@username` of the single monitored channel |
| `ADMIN_CHAT_ID` | Your chat ID — the one account allowed to run operator commands |
| `DB_PATH` | Path to the SQLite file (created automatically) |

### Run it

```bash
uv run python -m channel_filter.main
```

On first run, Telethon prompts interactively for the phone number and login
code of the account joining the source channel — this happens once; the
resulting `channel_filter.session` file persists the login for every
subsequent run.

### Run the tests

```bash
uv run pytest            # everything
uv run pytest tests/unit
uv run pytest tests/integration
```

The full behavior spec — including manual scenarios that need real Telegram
credentials and can't be unit-tested — is in
`specs/001-channel-keyword-filter/quickstart.md`.

## Bot commands

**Subscribers** (also available as reply-keyboard buttons):

| Command | Effect |
| --- | --- |
| `/start` | Register (if new) and (re)activate notifications |
| `/add <word>` | Add one or more comma-separated keywords (min 3 chars, max 20 total) |
| `/list` | Show saved keywords, tap one to remove it |
| `/remove <word>` | Remove a specific keyword |
| `/stop` | Pause notifications without losing keywords |
| `/deleteme` | Permanently delete the subscriber record and all keywords |
| `/help` | Show help text |

**Operator only** (matched against `ADMIN_CHAT_ID`):

| Command | Effect |
| --- | --- |
| `/block <chat_id>` | Stop all delivery and command access for that subscriber |
| `/unblock <chat_id>` | Restore their prior state and access |
| `/broadcast <text>` | Send a message to every active, non-blocked subscriber |
| `/stats` | Show total subscriber count and active/paused/blocked breakdown |

## Hosting / deployment

This project deploys as a single long-running process managed by `systemd`,
with a GitHub Actions pipeline handling test-then-deploy over SSH.

### Manual deployment (any Linux host with systemd)

```bash
# on the server
sudo mkdir -p /opt/channel-filter
cd /opt/channel-filter
git clone <this-repo> .
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv isn't installed yet
uv sync
cp .env.example .env && nano .env                  # fill in real values

sudo cp deploy/channel-filter.service /etc/systemd/system/channel-filter.service
sudo systemctl daemon-reload
sudo systemctl enable --now channel-filter
```

The unit file (`deploy/channel-filter.service`) runs
`/opt/channel-filter/.venv/bin/python -m channel_filter.main` with
`/opt/channel-filter/.env` as its environment file, and restarts it
automatically on failure (`Restart=on-failure`) — the outer safety net behind
the app's own per-component supervisors.

Useful commands on the server:

```bash
sudo systemctl status channel-filter
sudo systemctl restart channel-filter
journalctl -u channel-filter -f
```

The Telethon `.session` file and the SQLite `.db` file live in the working
directory (`/opt/channel-filter`) and must persist across deploys — they are
already excluded from `git` via `.gitignore`, so a `git pull` never touches
them.

### CI/CD (GitHub Actions)

`.github/workflows/deploy.yml` defines two jobs:

- **`test`** — on every push/PR to `main`: installs `uv`, runs `uv sync`,
  then `uv run pytest`.
- **`deploy`** — only on a manual `workflow_dispatch` run, and only after
  `test` passes: SSHes into the host (via `secrets.DEPLOY_HOST` /
  `DEPLOY_USER` / `DEPLOY_SSH_KEY`), `git pull --ff-only`, `uv sync`, restarts
  the `channel-filter` systemd service, then verifies it's active.

To deploy, configure those three repository secrets, do the one-time manual
setup above on the target host, then trigger the workflow from the Actions
tab (`Run workflow`) whenever you want to ship `main`.

## Project layout

```
src/channel_filter/
  main.py       startup wiring + component supervisors
  config.py     .env loading (Config dataclass)
  listener.py   Telethon client watching the source channel
  pipeline.py   ordered content-handling rule stages
  matcher.py    Aho-Corasick keyword automaton
  notifier.py   delivery queue + rate limiter
  bot.py        aiogram router: subscriber + operator commands
  auth.py       @require_operator / @refuse_if_blocked decorators
  db.py         SQLite schema + subscriber/keyword CRUD
  keyboards.py  reply/inline keyboard builders
  messages.py   Ukrainian bot copy
  types.py      domain value types (Outcome, AddKeywordOutcome, ...)
tests/
  unit/         pipeline, matcher, db, auth, bot-command, and supervisor tests
  integration/  pipeline-to-notifier integration test
specs/          Spec Kit feature specs, plans, and tasks (source of truth for behavior)
deploy/         systemd unit file
.github/workflows/  CI/CD pipeline
```

## Contributing

This project follows Spec-Driven Development via [Spec Kit](https://github.com/github/spec-kit):
`.specify/memory/constitution.md` and each feature's `specs/<feature>/spec.md`
/ `plan.md` / `tasks.md` are the source of truth for behavior — see
`CLAUDE.md` for the governing workflow before making product changes.
