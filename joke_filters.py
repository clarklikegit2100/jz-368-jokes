from __future__ import annotations

from dataclasses import dataclass


DEFAULT_MAX_CHARS = 800
DEFAULT_MIN_SCORE = 50

BANNED_TERMS = {
    "nigger",
    "rape",
    "rapes",
    "raped",
    "hitler",
    "terrorist",
    "terrorists",
    "suicide",
    "blowjob",
    "masturbating",
    "premature ejaculation",
    "fucking goofy",
    "school shooting",
}


@dataclass(frozen=True)
class FilterConfig:
    max_chars: int = DEFAULT_MAX_CHARS
    min_score: int = DEFAULT_MIN_SCORE
    exclude_banned_terms: bool = True


def joke_text(title: str, body: str) -> str:
    return f"{title}\n{body}".strip().lower()


def is_clean_enough(*, title: str, body: str, score: int, config: FilterConfig) -> bool:
    text = joke_text(title, body)
    if len(text) > config.max_chars:
        return False
    if score < config.min_score:
        return False
    if config.exclude_banned_terms and any(term in text for term in BANNED_TERMS):
        return False
    return True
