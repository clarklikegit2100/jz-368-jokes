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
- A small state file at `data/selection_state.json` remembers recent joke IDs.
- Sampling avoids recent joke IDs first, then falls back to the full pool only if needed.
- Within a single run, selected jokes are always unique.

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
