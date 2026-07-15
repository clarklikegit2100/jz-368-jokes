# JZ 368 Jokes

Daily joke reference data and lightweight local tooling for automation that sends unique jokes at 8:00 AM, 12:00 PM, and 11:00 PM.

## Files

- `daily-jokes-1000.csv` contains the active joke pool used by the automation.
- `one-million-reddit-jokes.csv` is the original large source dataset and is intentionally not committed because it is too large for normal GitHub uploads.
- `joke_store.py` provides a SQLite-backed joke store and recent-repeat protection.
- `migrate_jokes.py` imports the CSV into a local SQLite database.
- `sample_jokes.py` prints one or more unique random jokes from the database.
- `send_daily_jokes.py` builds a delivery-ready message for morning / afternoon / evening cron jobs.
- `test_joke_store.py` runs a small sanity test suite.
- `run_daily_joke.sh` is a tiny shell wrapper for scheduled usage.
- `cron_examples.md` shows shell and OpenClaw integration patterns.

## Current Joke Pool

- 1500 jokes currently stored in `daily-jokes-1000.csv` (the filename is legacy)
- CSV columns: `joke_id`, `source_id`, `title`, `body`, `score`, `permalink`

## Quick Start

### 1. Build the SQLite database

```bash
python3 migrate_jokes.py
```

By default this creates `data/jokes.db`.

### 2. Sample three unique jokes

```bash
python3 sample_jokes.py --count 3
```

### 3. Build a delivery-ready cron message

```bash
python3 send_daily_jokes.py --phase morning --count 1
python3 send_daily_jokes.py --phase afternoon --count 1
python3 send_daily_jokes.py --phase evening --count 1
python3 send_daily_jokes.py --phase morning --count 1 --no-links --intro "给你今天的一条笑话"
python3 send_daily_jokes.py --phase morning --count 1 --max-chars 300 --min-score 200 --no-links
```

If you want one job to send multiple jokes at once:

```bash
python3 send_daily_jokes.py --phase daily --count 3
```

### 4. Run the sanity test

```bash
python3 -m unittest test_joke_store.py
```

## How uniqueness works

- Jokes are stored in SQLite for faster repeated access than reparsing the CSV every time.
- Telegram delivery shuffles every eligible joke ID into a deck at the start of each cycle.
- The deck interleaves categories, so two consecutive deliveries do not use the same joke type.
- Each successful delivery removes only the top joke, so all 500 appear once before reshuffling.
- Failed deliveries and dry runs do not consume a joke from the deck.
- A new cycle is reshuffled and cannot start with the previous cycle's final joke.

## Quality filtering

`send_daily_jokes.py` now supports soft quality filtering before sampling.

- `--max-chars` prefers shorter jokes for chat delivery
- `--min-score` prefers higher-scoring jokes
- banned-term filtering is on by default for safer Telegram output
- if filtering becomes too strict and leaves too few jokes, the sampler safely falls back to the broader pool

## Integration idea

For cron jobs or bot delivery, call `send_daily_jokes.py` from the scheduled task and pass the output to your messaging layer.

Examples:

```bash
python3 send_daily_jokes.py --phase morning --count 1
python3 send_daily_jokes.py --phase afternoon --count 1
python3 send_daily_jokes.py --phase evening --count 1
```

Or if your automation wants three jokes in one message:

```bash
python3 send_daily_jokes.py --phase daily --count 3
```

There is also a shell wrapper:

```bash
./run_daily_joke.sh morning 1
./run_daily_joke.sh afternoon 1
./run_daily_joke.sh evening 1
./run_daily_joke.sh daily 3
```

For more examples, see `cron_examples.md`.

## Telegram delivery

The repository can send one non-repeating joke in each time slot through the
official Telegram Bot API.

### Required secrets

Create a bot with `@BotFather`, send the bot `/start`, and obtain the target
chat ID from the Bot API `getUpdates` response. Keep both values out of Git.

For local use, set these environment variables:

```powershell
$env:TELEGRAM_BOT_TOKEN="your-bot-token"
$env:TELEGRAM_CHAT_ID="your-chat-id"
```

For GitHub Actions, add repository secrets named `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` under **Settings → Secrets and variables → Actions**.

### Preview and send

A preview does not send a message or consume a joke from recent history:

```bash
python send_telegram_joke.py --phase morning --dry-run
```

Send one joke:

```bash
python send_telegram_joke.py --phase morning
python send_telegram_joke.py --phase afternoon
python send_telegram_joke.py --phase evening
```

The workflow in `.github/workflows/telegram-daily-jokes.yml` sends Chinese at
08:00, English at 12:30, and Chinese at 20:00, giving a daily Chinese-to-English
ratio of 2:1 in the `America/New_York` timezone. Chinese and English use separate
shuffled-deck state files, so each language completes its own non-repeating cycle.
Change all three
`timezone` values if another IANA timezone is required, such as
`Asia/Shanghai`. The workflow can also be run manually from the Actions tab.

The shuffled-deck state is restored and saved through the GitHub Actions cache.
A joke is removed from the deck only after Telegram confirms delivery. If the
cache is deleted or expires, the workflow starts a fresh shuffled cycle.

## Chinese joke pool

- `daily-jokes-zh-500.csv` contains exactly 500 family-friendly Chinese jokes.
- The pool has 10 categories with 50 jokes each: cold puns, brain teasers,
  programmers, workplace, campus, daily life, animals, food, dialogue, and
  mini-stories.
- Titles and bodies are unique, and the old repeated scenario template has been removed.
- The Telegram workflow uses this Chinese pool by default.
- English jokes remain available in `daily-jokes-1000.csv`.
- Chinese and English databases use separate SQLite files.
- When the CSV changes or its schema is upgraded, the sender automatically rebuilds
  its local SQLite copy. No manual database deletion is needed.

To regenerate the Chinese pool, install and authenticate the Claude CLI, then run:

```bash
python generate_chinese_jokes_ai.py
```

Generation is checkpointed under `data/` and validates the category counts and
global title/body uniqueness before replacing the CSV.
