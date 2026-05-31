# Cron / OpenClaw Integration Examples

This project now includes a delivery-ready joke generator for scheduled jobs.

## Local shell usage

Morning:

```bash
./run_daily_joke.sh morning 1
```

Morning without links and with a custom intro:

```bash
python3 send_daily_jokes.py --phase morning --count 1 --no-links --intro "给你今天的一条笑话"
```

Afternoon:

```bash
./run_daily_joke.sh afternoon 1
```

Evening:

```bash
./run_daily_joke.sh evening 1
```

Three jokes in one message:

```bash
./run_daily_joke.sh daily 3
```

## Direct Python usage

```bash
python3 send_daily_jokes.py --phase morning --count 1
python3 send_daily_jokes.py --phase afternoon --count 1
python3 send_daily_jokes.py --phase evening --count 1
python3 send_daily_jokes.py --phase daily --count 3
```

## OpenClaw cron integration pattern

OpenClaw cron jobs cannot directly execute local shell scripts as cron payloads. The practical pattern is:

1. generate the joke text with this project
2. pass that text into your messaging or reminder layer

For example, your automation wrapper can run:

```bash
MESSAGE=$(python3 /home/clark/Documents/GitHub/jz-368-jokes/send_daily_jokes.py --phase morning --count 1)
echo "$MESSAGE"
```

Then send `$MESSAGE` through your Telegram / OpenClaw delivery step.

## Suggested phase mapping

- `morning` → 8:00 AM
- `afternoon` → 12:00 PM
- `evening` → 11:00 PM
- `daily` → use when you want one message containing 3 jokes

## Notes

- SQLite database file: `data/jokes.db`
- Recent-repeat state: `data/selection_state.json`
- If the DB does not exist yet, `send_daily_jokes.py` will import from the CSV automatically.
