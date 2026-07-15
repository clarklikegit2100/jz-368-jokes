from __future__ import annotations

import csv
import hashlib
import json
import random
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from joke_filters import FilterConfig, is_clean_enough


DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "daily-jokes-1000.csv"
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "jokes.db"
DEFAULT_STATE_PATH = Path(__file__).resolve().parent / "data" / "selection_state.json"


@dataclass(frozen=True)
class Joke:
    joke_id: int
    source_id: str
    category: str
    title: str
    body: str
    score: int
    permalink: str

    def format_text(self, include_link: bool = True) -> str:
        parts = [self.title.strip()]
        body = self.body.strip()
        if body:
            parts.append(body)
        if include_link and self.permalink:
            parts.append(f"Source: {self.permalink}")
        return "\n\n".join(parts)


class JokeStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH, state_path: Path | str = DEFAULT_STATE_PATH) -> None:
        self.db_path = Path(db_path)
        self.state_path = Path(state_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def migrate_from_csv(self, csv_path: Path | str = DEFAULT_CSV_PATH) -> int:
        csv_path = Path(csv_path)
        with closing(self.connect()) as conn:
            conn.execute("DROP TABLE IF EXISTS jokes")
            conn.execute(
                """
                CREATE TABLE jokes (
                    joke_id INTEGER PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    permalink TEXT NOT NULL
                )
                """
            )
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = [
                    (
                        int(row["joke_id"]),
                        row["source_id"],
                        (row.get("category") or "general").strip(),
                        row["title"],
                        row["body"],
                        int(row["score"]),
                        row["permalink"],
                    )
                    for row in reader
                ]
            conn.executemany(
                "INSERT INTO jokes (joke_id, source_id, category, title, body, score, permalink) VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jokes_score ON jokes(score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jokes_source_id ON jokes(source_id)")
            conn.commit()
        return len(rows)

    def needs_migration(self, csv_path: Path | str = DEFAULT_CSV_PATH) -> bool:
        """Return whether the SQLite copy is missing, stale, or uses an old schema."""
        csv_path = Path(csv_path)
        if not self.db_path.exists():
            return True
        try:
            with closing(self.connect()) as conn:
                columns = {
                    row["name"] for row in conn.execute("PRAGMA table_info(jokes)").fetchall()
                }
        except sqlite3.DatabaseError:
            return True
        return "category" not in columns or csv_path.stat().st_mtime > self.db_path.stat().st_mtime

    def count(self) -> int:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM jokes").fetchone()
            return int(row["total"])

    def get_random_unique_jokes(
        self,
        count: int = 3,
        recent_limit: int | None = None,
        seed: int | None = None,
        filter_config: FilterConfig | None = None,
        record_selection: bool = True,
    ) -> list[Joke]:
        if count <= 0:
            return []

        total = self.count()
        if total == 0:
            raise RuntimeError("No jokes found in database. Run migrate first.")

        state = self._load_state()
        recent_ids: list[int] = state.get("recent_joke_ids", [])
        if recent_limit is None:
            recent_limit = min(max(count * 10, 30), max(total - count, 0))
        recent_ids = recent_ids[-recent_limit:] if recent_limit > 0 else []

        rng = random.Random(seed)
        filter_config = filter_config or FilterConfig()
        with closing(self.connect()) as conn:
            placeholders = ",".join("?" for _ in recent_ids)
            if recent_ids:
                rows = conn.execute(
                    f"SELECT joke_id, source_id, category, title, body, score, permalink FROM jokes WHERE joke_id NOT IN ({placeholders})"
                    ,
                    recent_ids,
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT joke_id, source_id, category, title, body, score, permalink FROM jokes"
                ).fetchall()

            if len(rows) < count:
                rows = conn.execute(
                    "SELECT joke_id, source_id, category, title, body, score, permalink FROM jokes"
                ).fetchall()
                recent_ids = []

        filtered_rows = [
            row for row in rows
            if is_clean_enough(
                title=row["title"],
                body=row["body"],
                score=int(row["score"]),
                config=filter_config,
            )
        ]
        candidate_rows = filtered_rows if len(filtered_rows) >= count else rows

        selected_rows = rng.sample(candidate_rows, k=min(count, len(candidate_rows)))
        jokes = [self._row_to_joke(row) for row in selected_rows]
        if record_selection:
            self._save_state(recent_ids + [j.joke_id for j in jokes], recent_limit=max(recent_limit, count))
        return jokes

    def get_from_shuffled_deck(
        self,
        count: int = 1,
        seed: int | None = None,
        filter_config: FilterConfig | None = None,
        persist_deck: bool = True,
    ) -> list[Joke]:
        """Draw from a shuffled deck so every eligible joke appears once per cycle."""
        if count <= 0:
            return []

        with closing(self.connect()) as conn:
            rows = conn.execute(
                "SELECT joke_id, source_id, category, title, body, score, permalink FROM jokes"
            ).fetchall()
        if not rows:
            raise RuntimeError("No jokes found in database. Run migrate first.")

        filter_config = filter_config or FilterConfig()
        filtered_rows = [
            row for row in rows
            if is_clean_enough(
                title=row["title"],
                body=row["body"],
                score=int(row["score"]),
                config=filter_config,
            )
        ]
        candidate_rows = filtered_rows if filtered_rows else rows
        row_by_id = {int(row["joke_id"]): row for row in candidate_rows}
        signature_source = "\n".join(sorted(
            f"{row['source_id']}\0{row['category']}\0{row['title']}\0{row['body']}"
            for row in candidate_rows
        ))
        pool_signature = hashlib.sha256(signature_source.encode("utf-8")).hexdigest()

        state = self._load_state()
        stored_deck = state.get("shuffled_deck_ids", [])
        deck = [
            int(joke_id)
            for joke_id in stored_deck
            if int(joke_id) in row_by_id
        ] if state.get("deck_pool_signature") == pool_signature else []

        if not deck:
            rng = random.Random(seed)
            groups: dict[str, list[int]] = {}
            for joke_id, row in row_by_id.items():
                groups.setdefault(row["category"], []).append(joke_id)
            for joke_ids in groups.values():
                rng.shuffle(joke_ids)

            last_sent_ids = state.get("recent_joke_ids", [])
            previous_category = None
            if last_sent_ids and last_sent_ids[-1] in row_by_id:
                previous_category = row_by_id[last_sent_ids[-1]]["category"]

            deck = []
            while groups:
                available = [
                    category for category, joke_ids in groups.items()
                    if joke_ids and category != previous_category
                ]
                if not available:
                    available = [category for category, joke_ids in groups.items() if joke_ids]
                largest_group = max(len(groups[category]) for category in available)
                choices = [category for category in available if len(groups[category]) == largest_group]
                category = rng.choice(choices)
                deck.append(groups[category].pop())
                previous_category = category
                if not groups[category]:
                    del groups[category]

            state["shuffled_deck_ids"] = deck
            state["deck_pool_signature"] = pool_signature
            state["deck_cycle"] = int(state.get("deck_cycle", 0)) + 1
            if persist_deck:
                self._write_state(state)

        selected_ids = deck[:count]
        return [self._row_to_joke(row_by_id[joke_id]) for joke_id in selected_ids]

    def remember_jokes(self, jokes: Sequence[Joke], recent_limit: int | None = None) -> None:
        """Record jokes after a delivery succeeds."""
        if not jokes:
            return

        total = self.count()
        if recent_limit is None:
            recent_limit = min(max(len(jokes) * 10, 30), max(total - len(jokes), 0))
        recent_limit = max(recent_limit, len(jokes))
        state = self._load_state()
        sent_ids = [joke.joke_id for joke in jokes]
        recent_ids = state.get("recent_joke_ids", [])
        state["recent_joke_ids"] = (recent_ids + sent_ids)[-recent_limit:]
        state["shuffled_deck_ids"] = [
            joke_id for joke_id in state.get("shuffled_deck_ids", []) if joke_id not in sent_ids
        ]
        self._write_state(state)

    def _row_to_joke(self, row: sqlite3.Row) -> Joke:
        return Joke(
            joke_id=int(row["joke_id"]),
            source_id=row["source_id"],
            category=row["category"],
            title=row["title"],
            body=row["body"],
            score=int(row["score"]),
            permalink=row["permalink"],
        )

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return {"recent_joke_ids": []}
        with self.state_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save_state(self, recent_joke_ids: Sequence[int], recent_limit: int) -> None:
        payload = self._load_state()
        payload["recent_joke_ids"] = list(recent_joke_ids)[-recent_limit:]
        self._write_state(payload)

    def _write_state(self, payload: dict) -> None:
        with self.state_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)


def ensure_database(csv_path: Path | str = DEFAULT_CSV_PATH, db_path: Path | str = DEFAULT_DB_PATH) -> JokeStore:
    store = JokeStore(db_path=db_path)
    if store.needs_migration(csv_path):
        store.migrate_from_csv(csv_path)
    return store
