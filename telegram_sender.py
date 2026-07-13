from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable


TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_TEXT_LIMIT = 4096


class TelegramSendError(RuntimeError):
    """Raised when Telegram rejects or cannot receive a message."""


def send_message(
    *,
    token: str,
    chat_id: str,
    text: str,
    api_base: str = TELEGRAM_API_BASE,
    timeout: float = 20,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    token = token.strip()
    chat_id = str(chat_id).strip()
    if not token:
        raise ValueError("Telegram bot token is required")
    if not chat_id:
        raise ValueError("Telegram chat ID is required")
    if not text:
        raise ValueError("Telegram message text is required")
    if len(text) > TELEGRAM_TEXT_LIMIT:
        raise ValueError(f"Telegram message exceeds {TELEGRAM_TEXT_LIMIT} characters")

    url = f"{api_base.rstrip('/')}/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with opener(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            details = exc.read().decode("utf-8")
        except Exception:
            details = str(exc)
        raise TelegramSendError(f"Telegram HTTP error {exc.code}: {details}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TelegramSendError(f"Could not reach Telegram: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TelegramSendError("Telegram returned an invalid response") from exc

    if not result.get("ok"):
        description = result.get("description", "unknown Telegram API error")
        raise TelegramSendError(str(description))
    return result
