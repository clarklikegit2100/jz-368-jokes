#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from joke_filters import FilterConfig
from joke_store import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, DEFAULT_STATE_PATH, JokeStore
from send_daily_jokes import build_message
from telegram_sender import send_message


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Select and send one unique joke through a Telegram bot.")
    parser.add_argument("--phase", choices=["morning", "afternoon", "evening"], required=True)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--recent-limit", type=int, default=500)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-chars", type=int, default=800)
    parser.add_argument("--min-score", type=int, default=50)
    parser.add_argument("--allow-banned-terms", action="store_true")
    parser.add_argument("--include-links", action="store_true")
    parser.add_argument("--intro", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print without sending or changing history")
    args = parser.parse_args()

    store = JokeStore(db_path=args.db, state_path=args.state)
    if not args.db.exists():
        store.migrate_from_csv(csv_path=args.csv)

    jokes = store.get_random_unique_jokes(
        count=1,
        recent_limit=args.recent_limit,
        seed=args.seed,
        filter_config=FilterConfig(
            max_chars=args.max_chars,
            min_score=args.min_score,
            exclude_banned_terms=not args.allow_banned_terms,
        ),
        record_selection=False,
    )
    message = build_message(
        phase=args.phase,
        jokes=jokes,
        include_links=args.include_links,
        intro=args.intro,
    )

    if args.dry_run:
        print(message)
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        parser.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set unless --dry-run is used")

    result = send_message(token=token, chat_id=chat_id, text=message)
    store.remember_jokes(jokes, recent_limit=args.recent_limit)
    message_id = result.get("result", {}).get("message_id", "unknown")
    print(f"Telegram message sent successfully (message_id={message_id}, phase={args.phase})")


if __name__ == "__main__":
    main()
