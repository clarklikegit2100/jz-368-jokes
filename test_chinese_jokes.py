from __future__ import annotations

import csv
import re
import tempfile
import unittest
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
        self.assertEqual(len({(row["title"], row["body"]) for row in rows}), 500)
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
        self.assertTrue(all(joke.source_id.startswith("zh-") for joke in jokes))


if __name__ == "__main__":
    unittest.main()
