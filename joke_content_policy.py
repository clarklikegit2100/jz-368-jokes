from __future__ import annotations

import re


HARD_BANNED_PATTERNS = (
    re.compile(r"\b(?:fuck\w*|shit\w*|bitch\w*|cunt\w*|asshole\w*|motherfucker\w*|bastard\w*)\b", re.I),
    re.compile(r"\b(?:nigg\w*|chink\w*|spic(?:s)?|fagg\w*|retard\w*|racist\w*)\b", re.I),
    re.compile(r"\b(?:rape\w*|masturb\w*|blowjob\w*|handjob\w*|penis\w*|vagina\w*|semen\w*|ejaculat\w*|porn\w*|orgasm\w*|prostitut\w*|incest\w*|pedoph\w*|molest\w*)\b", re.I),
    re.compile(r"\b(?:suicide\w*|terroris\w*|nazi\w*|hitler\w*|school shooting)\b", re.I),
    re.compile(r"\b(?:[1-9]|1[0-7])[ -]year[ -]old\b", re.I),
)


def contains_hard_banned_content(value: str) -> bool:
    return any(pattern.search(value) for pattern in HARD_BANNED_PATTERNS)
