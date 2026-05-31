#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from joke_store import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, JokeStore


PHASE_LABELS = {
    "morning": "早晨笑话",
    "afternoon": "下午笑话",
    "evening": "晚间笑话",
    "daily": "今日笑话",
}


def build_message(*, phase: str, jokes: list, include_links: bool = True, intro: str | None = None) -> str:
    title = PHASE_LABELS.get(phase, PHASE_LABELS["daily"])
    lines = [f"{title} 🃏", ""]
    if intro:
        lines.append(intro.strip())
        lines.append("")

    for index, joke in enumerate(jokes, start=1):
        lines.append(f"{index}. {joke.title.strip()}")
        body = joke.body.strip()
        if body:
            lines.append(body)
        if include_links and joke.permalink:
            lines.append(f"链接: {joke.permalink}")
        if index != len(jokes):
            lines.append("")

    return "\n".join(lines).strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Telegram-friendly daily jokes message from the local SQLite joke store."
    )
    parser.add_argument("--count", type=int, default=1, help="Number of jokes to include in the message")
    parser.add_argument(
        "--phase",
        choices=["morning", "afternoon", "evening", "daily"],
        default="daily",
        help="Message label to use",
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="CSV source to import if DB is missing")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--recent-limit", type=int, default=None, help="How many recent jokes to avoid repeating")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible tests")
    parser.add_argument("--no-links", action="store_true", help="Do not include joke source links")
    parser.add_argument("--intro", default=None, help="Optional intro line to add under the phase title")
    args = parser.parse_args()

    store = JokeStore(db_path=args.db)
    if not args.db.exists():
        store.migrate_from_csv(csv_path=args.csv)

    jokes = store.get_random_unique_jokes(
        count=args.count,
        recent_limit=args.recent_limit,
        seed=args.seed,
    )
    print(build_message(phase=args.phase, jokes=jokes, include_links=not args.no_links, intro=args.intro))


if __name__ == "__main__":
    main()
