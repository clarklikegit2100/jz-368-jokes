from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from joke_store import JokeStore
from telegram_sender import TELEGRAM_TEXT_LIMIT, TelegramSendError, send_message


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class TelegramTests(unittest.TestCase):
    def test_send_message_posts_expected_payload(self) -> None:
        captured = {}

        def fake_open(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"ok": True, "result": {"message_id": 42}})

        result = send_message(
            token="secret-token",
            chat_id="-12345",
            text="hello",
            opener=fake_open,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(captured["url"], "https://api.telegram.org/botsecret-token/sendMessage")
        self.assertEqual(captured["payload"]["chat_id"], "-12345")
        self.assertEqual(captured["payload"]["text"], "hello")
        self.assertTrue(captured["payload"]["disable_web_page_preview"])

    def test_send_message_rejects_api_error(self) -> None:
        def fake_open(request, timeout):
            return FakeResponse({"ok": False, "description": "chat not found"})

        with self.assertRaisesRegex(TelegramSendError, "chat not found"):
            send_message(token="token", chat_id="123", text="hello", opener=fake_open)

    def test_send_message_rejects_oversized_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "exceeds"):
            send_message(token="token", chat_id="123", text="x" * (TELEGRAM_TEXT_LIMIT + 1))

    def test_unrecorded_selection_is_only_remembered_after_success(self) -> None:
        repo_dir = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            state_path = temp_path / "selection_state.json"
            store = JokeStore(db_path=temp_path / "jokes.db", state_path=state_path)
            store.migrate_from_csv(repo_dir / "daily-jokes-en-500.csv")

            jokes = store.get_random_unique_jokes(
                count=1,
                recent_limit=30,
                seed=123,
                record_selection=False,
            )
            self.assertFalse(state_path.exists())

            store.remember_jokes(jokes, recent_limit=30)
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["recent_joke_ids"], [jokes[0].joke_id])


if __name__ == "__main__":
    unittest.main()
