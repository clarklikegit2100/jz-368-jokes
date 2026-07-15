#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from joke_store import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, JokeStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch random unique jokes from the local SQLite store.")
    parser.add_argument("--count", type=int, default=3, help="Number of jokes to select")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="CSV source to import if DB is missing")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--recent-limit", type=int, default=None, help="How many recent joke IDs to avoid repeating")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible tests")
    parser.add_argument("--no-link", action="store_true", help="Do not include source links in output")
    args = parser.parse_args()

    store = JokeStore(db_path=args.db)
    if store.needs_migration(args.csv):
        imported = store.migrate_from_csv(csv_path=args.csv)
        print(f"Database missing. Imported {imported} jokes into {args.db}.\n")

    jokes = store.get_random_unique_jokes(
        count=args.count,
        recent_limit=args.recent_limit,
        seed=args.seed,
    )

    for index, joke in enumerate(jokes, start=1):
        print(f"=== Joke {index} / {len(jokes)} ===")
        print(joke.format_text(include_link=not args.no_link))
        print()


if __name__ == "__main__":
    main()
