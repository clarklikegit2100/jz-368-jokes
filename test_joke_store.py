from pathlib import Path
import tempfile
import unittest

from joke_filters import FilterConfig, is_clean_enough
from joke_store import JokeStore
from send_daily_jokes import build_message


class JokeStoreTests(unittest.TestCase):
    def test_migrate_and_sample_unique_jokes(self) -> None:
        repo_dir = Path(__file__).resolve().parent
        csv_path = repo_dir / "daily-jokes-en-500.csv"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            store = JokeStore(
                db_path=temp_path / "jokes.db",
                state_path=temp_path / "selection_state.json",
            )
            imported = store.migrate_from_csv(csv_path)
            self.assertGreater(imported, 0)
            self.assertEqual(store.count(), imported)

            jokes = store.get_random_unique_jokes(count=3, recent_limit=30, seed=123)
            self.assertEqual(len(jokes), 3)
            self.assertEqual(len({j.joke_id for j in jokes}), 3)

            next_jokes = store.get_random_unique_jokes(count=3, recent_limit=30, seed=456)
            self.assertEqual(len(next_jokes), 3)
            self.assertTrue({j.joke_id for j in jokes}.isdisjoint({j.joke_id for j in next_jokes}))

    def test_build_message_formats_output(self) -> None:
        repo_dir = Path(__file__).resolve().parent
        csv_path = repo_dir / "daily-jokes-en-500.csv"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            store = JokeStore(
                db_path=temp_path / "jokes.db",
                state_path=temp_path / "selection_state.json",
            )
            store.migrate_from_csv(csv_path)
            jokes = store.get_random_unique_jokes(count=2, recent_limit=20, seed=123)
            message = build_message(phase="morning", jokes=jokes, include_links=False, intro="给你今天的测试笑话")
            self.assertIn("早晨笑话", message)
            self.assertIn("给你今天的测试笑话", message)
            self.assertIn("1. ", message)
            self.assertIn("2. ", message)

    def test_filter_blocks_banned_and_long_content(self) -> None:
        config = FilterConfig(max_chars=20, min_score=100)
        self.assertFalse(is_clean_enough(title="ok", body="this is way too long for the tiny limit", score=200, config=config))
        self.assertFalse(is_clean_enough(title="ok", body="contains rape term", score=200, config=FilterConfig()))
        self.assertFalse(is_clean_enough(title="ok", body="short", score=1, config=FilterConfig(min_score=10)))
        self.assertTrue(is_clean_enough(title="short title", body="clean body", score=200, config=FilterConfig(max_chars=1000, min_score=10)))


if __name__ == "__main__":
    unittest.main()
