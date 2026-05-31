from pathlib import Path
import tempfile
import unittest

from joke_store import JokeStore


class JokeStoreTests(unittest.TestCase):
    def test_migrate_and_sample_unique_jokes(self) -> None:
        repo_dir = Path(__file__).resolve().parent
        csv_path = repo_dir / "daily-jokes-1000.csv"

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


if __name__ == "__main__":
    unittest.main()
