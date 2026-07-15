from __future__ import annotations

import csv
import re
import unittest
from collections import Counter
from pathlib import Path

from generate_english_jokes_ai import contains_banned_term


class EnglishJokePoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.csv_path = Path(__file__).resolve().parent / "daily-jokes-en-500.csv"
        with cls.csv_path.open("r", encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    @staticmethod
    def duplicate_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    def test_pool_is_balanced_unique_and_english(self) -> None:
        self.assertEqual(len(self.rows), 500)
        self.assertEqual([int(row["joke_id"]) for row in self.rows], list(range(1, 501)))
        self.assertEqual(len({row["source_id"] for row in self.rows}), 500)
        self.assertEqual(len({self.duplicate_key(row["title"]) for row in self.rows}), 500)
        self.assertEqual(len({self.duplicate_key(row["body"]) for row in self.rows}), 500)
        counts = Counter(row["category"] for row in self.rows)
        self.assertEqual(len(counts), 10)
        self.assertEqual(set(counts.values()), {50})
        self.assertTrue(all(re.search(r"[A-Za-z]", row["title"] + row["body"]) for row in self.rows))
        self.assertFalse(any(re.search(r"[\u4e00-\u9fff]", row["title"] + row["body"]) for row in self.rows))
        self.assertFalse(any(contains_banned_term(row["title"] + " " + row["body"]) for row in self.rows))

    def test_brain_teasers_include_answers(self) -> None:
        teasers = [row for row in self.rows if row["category"] == "brain_teaser"]
        self.assertEqual(len(teasers), 50)
        self.assertFalse(any(row["body"].rstrip().endswith("?") for row in teasers))


if __name__ == "__main__":
    unittest.main()
