#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from joke_store import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, JokeStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Import jokes from CSV into a local SQLite database.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="Path to source CSV file")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    args = parser.parse_args()

    store = JokeStore(db_path=args.db)
    count = store.migrate_from_csv(csv_path=args.csv)
    print(f"Imported {count} jokes into {args.db}")


if __name__ == "__main__":
    main()
