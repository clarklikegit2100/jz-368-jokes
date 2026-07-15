from __future__ import annotations

import csv
import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from joke_store import JokeStore


class ChineseJokePoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.csv_path = Path(__file__).resolve().parent / "daily-jokes-zh-500.csv"

    def test_pool_has_exactly_500_unique_chinese_jokes(self) -> None:
        with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 500)
        self.assertEqual([int(row["joke_id"]) for row in rows], list(range(1, 501)))
        self.assertEqual(len({row["source_id"] for row in rows}), 500)
        self.assertEqual(len({row["title"] for row in rows}), 500)
        self.assertEqual(len({row["body"] for row in rows}), 500)
        category_counts = Counter(row["category"] for row in rows)
        self.assertEqual(len(category_counts), 10)
        self.assertEqual(set(category_counts.values()), {50})
        self.assertTrue(all(row["title"].strip() and row["body"].strip() for row in rows))
        self.assertTrue(all(re.search(r"[\u4e00-\u9fff]", row["title"] + row["body"]) for row in rows))

    def test_pool_migrates_and_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            store = JokeStore(
                db_path=temp / "jokes-zh.db",
                state_path=temp / "selection_state.json",
            )
            self.assertEqual(store.migrate_from_csv(self.csv_path), 500)
            jokes = store.get_random_unique_jokes(count=3, recent_limit=500, seed=123)

        self.assertEqual(len(jokes), 3)
        self.assertTrue(all(joke.category for joke in jokes))
        self.assertTrue(all(joke.source_id.startswith("zh-") for joke in jokes))

    def test_shuffled_deck_is_random_and_has_no_repeats_in_a_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            state_path = temp / "selection_state.json"
            store = JokeStore(db_path=temp / "jokes-zh.db", state_path=state_path)
            store.migrate_from_csv(self.csv_path)

            drawn_categories = []
            drawn_ids = []
            for _ in range(500):
                jokes = store.get_from_shuffled_deck(count=1, seed=123)
                drawn_categories.append(jokes[0].category)
                drawn_ids.append(jokes[0].joke_id)
                store.remember_jokes(jokes, recent_limit=500)

            self.assertEqual(len(drawn_ids), 500)
            self.assertEqual(len(set(drawn_ids)), 500)
            self.assertEqual(len(set(drawn_categories)), 10)
            self.assertTrue(all(a != b for a, b in zip(drawn_categories, drawn_categories[1:])))

            self.assertNotEqual(drawn_ids, list(range(1, 501)))

            next_joke = store.get_from_shuffled_deck(count=1, seed=456)
            self.assertNotEqual(next_joke[0].category, drawn_categories[-1])
            self.assertNotEqual(next_joke[0].joke_id, drawn_ids[-1])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["deck_cycle"], 2)

    def test_shuffled_deck_does_not_consume_before_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            state_path = temp / "selection_state.json"
            store = JokeStore(db_path=temp / "jokes-zh.db", state_path=state_path)
            store.migrate_from_csv(self.csv_path)

            first = store.get_from_shuffled_deck(count=1, seed=123)
            retry = store.get_from_shuffled_deck(count=1, seed=999)
            self.assertEqual(first[0].joke_id, retry[0].joke_id)

            store.remember_jokes(first, recent_limit=500)
            second = store.get_from_shuffled_deck(count=1)
            self.assertNotEqual(first[0].joke_id, second[0].joke_id)

    def test_shuffled_deck_preview_does_not_create_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            state_path = temp / "selection_state.json"
            store = JokeStore(db_path=temp / "jokes-zh.db", state_path=state_path)
            store.migrate_from_csv(self.csv_path)

            store.get_from_shuffled_deck(count=1, seed=123, persist_deck=False)
            self.assertFalse(state_path.exists())


if __name__ == "__main__":
    unittest.main()
