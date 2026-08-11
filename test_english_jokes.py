from __future__ import annotations

import csv
import re
import unittest
from collections import Counter
from pathlib import Path

from joke_content_policy import contains_hard_banned_content
from generate_adult_english_jokes_ai import ADULT_SIGNAL, FORBIDDEN_CONTEXT


class EnglishJokePoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.csv_path = Path(__file__).resolve().parent / "daily-jokes-en-720.csv"
        with cls.csv_path.open("r", encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    @staticmethod
    def duplicate_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    def test_pool_is_balanced_unique_and_english(self) -> None:
        self.assertEqual(len(self.rows), 720)
        self.assertEqual([int(row["joke_id"]) for row in self.rows], list(range(1, 721)))
        self.assertEqual(len({row["source_id"] for row in self.rows}), 720)
        self.assertEqual(len({self.duplicate_key(row["title"]) for row in self.rows}), 720)
        self.assertEqual(len({self.duplicate_key(row["body"]) for row in self.rows}), 720)
        counts = Counter(row["category"] for row in self.rows)
        self.assertEqual(len(counts), 16)
        self.assertEqual(counts["adult_mild"], 10)
        self.assertTrue(all(counts[category] >= 50 for category in counts if not category.startswith("adult_")))
        adult_rows = [row for row in self.rows if row["category"].startswith("adult_")]
        self.assertEqual(len(adult_rows), 180)
        self.assertEqual(len(adult_rows) / len(self.rows), 0.25)
        self.assertTrue(all(re.search(r"[A-Za-z]", row["title"] + row["body"]) for row in self.rows))
        self.assertFalse(any(re.search(r"[\u4e00-\u9fff]", row["title"] + row["body"]) for row in self.rows))
        self.assertFalse(any(contains_hard_banned_content(row["title"] + " " + row["body"]) for row in self.rows))

    def test_brain_teasers_include_answers(self) -> None:
        teasers = [row for row in self.rows if row["category"] == "brain_teaser"]
        self.assertEqual(len(teasers), 50)
        self.assertFalse(any(row["body"].rstrip().endswith("?") for row in teasers))

    def test_generated_adult_jokes_keep_safe_adult_context(self) -> None:
        generated_adult = [
            row for row in self.rows
            if row["category"].startswith("adult_") and row["category"] != "adult_mild"
        ]
        self.assertEqual(len(generated_adult), 170)
        combined = [row["title"] + " " + row["body"] for row in generated_adult]
        self.assertTrue(all(ADULT_SIGNAL.search(text) for text in combined))
        self.assertFalse(any(FORBIDDEN_CONTEXT.search(text) for text in combined))


if __name__ == "__main__":
    unittest.main()
