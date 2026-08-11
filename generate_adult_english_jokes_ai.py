#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from joke_content_policy import contains_hard_banned_content


OUTPUT_PATH = Path(__file__).resolve().parent / "daily-jokes-en-adult-generated-170.csv"
CHECKPOINT_PATH = Path(__file__).resolve().parent / "data" / "generated_adult_english_jokes.json"

CATEGORIES = [
    ("adult_dating", "Dating apps, first dates, flirting, attraction, and awkward romantic moments between consenting adults."),
    ("adult_relationships", "Playful long-term partner and married-life humor without gender stereotypes, humiliation, or hostility."),
    ("adult_wordplay", "Suggestive but non-graphic adult double meanings and wordplay with varied setups."),
    ("adult_after_dark", "Tasteful bedroom, honeymoon, lingerie, kissing, and intimacy humor that stays non-explicit."),
    ("adult_dialogue", "Short conversations between consenting adults about dating, romance, attraction, or intimacy."),
]
TARGET_COUNTS = {
    "adult_dating": 20,
    "adult_relationships": 35,
    "adult_wordplay": 50,
    "adult_after_dark": 45,
    "adult_dialogue": 20,
}

FORBIDDEN_CONTEXT = re.compile(
    r"\b(?:child\w*|kid\w*|teen\w*|minor\w*|school\w*|student\w*|teacher\w*|"
    r"daughter\w*|son\b|mom\b|mother\w*|dad\b|father\w*|sister\w*|brother\w*|cousin\w*|"
    r"force\w*|coerc\w*|assault\w*|abuse\w*|drug\w*|drunk\w*|unconscious|cheat\w*|adulter\w*)\b",
    re.I,
)
ADULT_SIGNAL = re.compile(
    r"\b(?:adult\w*|date\w*|dating|partner\w*|couple\w*|spouse\w*|wife|husband|"
    r"girlfriend|boyfriend|sex\w*|sexy|naked|bedroom|kiss\w*|flirt\w*|condom\w*|virgin\w*|"
    r"honeymoon\w*|lingerie|attract\w*|romance|romantic|marriage|married|lover\w*|intimacy|intimate|"
    r"relationship\w*|anniversary|engage\w*|fianc\w*|proposal|wedding|match\w*|swipe\w*|profile|"
    r"single\w*|crush|chemistry|phone number|coffee|dinner|restaurant|reservation|hotel|privacy|"
    r"candle\w*|mattress|sheets|pillow|clothes|undress\w*|passion\w*|desire\w*)\b",
    re.I,
)

CURATED_FILL_INS = {
    "adult_dating": [
        ("The Honest Profile", "My dating profile says I enjoy long walks. It leaves out that they are usually toward the restaurant after I park too far away."),
        ("Perfect Match", "My date said we had amazing chemistry. I agreed; neither of us understood what was happening, but there were definitely sparks."),
        ("Coffee Commitment", "We agreed to keep the first date casual, so we only discussed coffee, dessert, and where our future dog would sleep."),
        ("Swipe Management", "I deleted my dating app after meeting someone special. I needed the storage space for all the photos we now take of our dinners."),
        ("Dinner Signals", "My date asked whether I believed in love at first sight. I said, 'I ordered dessert before the main course, so clearly I believe in commitment.'"),
        ("Table for Two", "The restaurant asked if our date was a special occasion. I said, 'Yes, we both arrived looking like our profile pictures.'"),
        ("First Date Forecast", "My date promised a night full of chemistry. The forecast was accurate: warm conversation, light flirting, and a strong chance of sharing dessert."),
        ("The Second Date", "I knew the first date went well when we both stopped pretending we had early meetings the next morning."),
        ("Flirting in Person", "Online I had a perfect opening line. In person I said, 'Hi.' Fortunately, my date was attracted to concise writing."),
        ("Romantic Reservation", "I booked the quietest table for our date. We spent dinner whispering, mostly because neither of us could pronounce the menu."),
    ],
    "adult_dialogue": [
        ("Bedroom Lighting", "'Should we dim the bedroom lights?' my partner asked. 'Absolutely,' I said. 'Confidence looks great in energy-saving mode.'"),
        ("A Little Chemistry", "'Do you feel that chemistry between us?' my date asked. 'Yes,' I said. 'And unlike my last experiment, this one deserves a second trial.'"),
        ("The Kiss Review", "'How was that kiss?' my partner asked. 'Promising,' I said. 'I'd approve another round for quality control.'"),
        ("Anniversary Memory", "'Do you remember our anniversary?' my spouse asked. 'Of course,' I said. 'My calendar, florist, and restaurant all remember it with me.'"),
        ("Hotel Privacy", "'Why did you request a hotel room far from the elevator?' my partner asked. 'Privacy,' I said, 'and fewer witnesses to my vacation snoring.'"),
        ("Candlelight Plans", "'I bought candles for tonight,' my partner said. 'Romantic,' I replied. 'Also practical if your cooking trips the breaker again.'"),
        ("The Flirt Test", "'Are you flirting with me?' my date asked. 'I'm trying,' I said. 'The polished version should arrive by our second date.'"),
        ("Attraction Clause", "'What first attracted you to me?' my partner asked. 'Your confidence,' I said. 'It convinced me you might overlook my opening line.'"),
        ("Pillow Talk Agenda", "'What should we discuss during pillow talk?' my partner asked. 'Nothing urgent,' I said. 'The pillow has already heard enough about work.'"),
        ("Romantic Dinner", "'Did you make this dinner to impress me?' my date asked. 'Yes,' I said. 'The smoke alarm is providing the standing ovation.'"),
        ("Relationship Status", "'How serious is this relationship?' my partner asked. 'I gave you my streaming password,' I said. 'Emotionally, that is a joint account.'"),
        ("The Lingerie Surprise", "'Do you like the new lingerie?' my partner asked. 'Very much,' I said. 'Though the price tag was the part that truly took my breath away.'"),
        ("Morning After", "'Was last night unforgettable?' my partner asked. 'Definitely,' I said. 'The hotel pillow made sure my neck would remember it all week.'"),
        ("A Private Question", "'Can I ask you something intimate?' my date said. 'Certainly,' I replied. 'But if it is my credit score, buy me dinner first.'"),
        ("Marriage Proposal", "'Would you marry me all over again?' my spouse asked. 'In a heartbeat,' I said. 'This time we already know which relatives need separate tables.'"),
        ("The Sexy Voice", "'Do you like my sexy voice?' my partner whispered. 'I do,' I said, 'but the neighbors may think our audiobook subscription got interesting.'"),
        ("Date Night Dress Code", "'Is this outfit too much for date night?' my partner asked. 'No,' I said. 'But my old T-shirt has suddenly requested formal retirement.'"),
        ("Bedroom Temperature", "'Is the bedroom too warm?' my partner asked. 'Possibly,' I said. 'Either that or your flirting finally passed inspection.'"),
        ("The Romantic Playlist", "'Did you make this romantic playlist for us?' my date asked. 'Yes,' I said. 'It lasts three hours, which is two hours and fifty minutes longer than my confidence.'"),
        ("Privacy Settings", "'Should we turn off our phones for date night?' my partner asked. 'Yes,' I said. 'Let the algorithms wonder what true intimacy looks like.'"),
    ],
}

# Avoid title collisions with the established clean/legacy English pool.
TITLE_REWRITES = {
    "Rise and Shine": "The Morning Misread",
    "The Gym Excuse": "Stamina for the To-Do List",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def duplicate_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def parse_response(raw: str) -> list[dict[str, str]]:
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("```") or "|||" not in line:
            continue
        title, body = line.split("|||", 1)
        title = re.sub(r"^\s*\d+[.)]\s*", "", title).strip()
        items.append({"title": title, "body": body.strip()})
    if not items:
        raise ValueError("response did not contain delimiter-formatted jokes")
    return items


def validate_batch(
    category: str,
    items: list[dict[str, str]],
    existing: list[dict[str, str]],
    requested_count: int,
) -> list[dict[str, str]]:
    if len(items) < max(1, requested_count - 4):
        raise ValueError(f"{category}: requested {requested_count}, got only {len(items)}")
    items = items[:requested_count]
    existing_titles = {duplicate_key(item["title"]) for item in existing}
    existing_bodies = {duplicate_key(item["body"]) for item in existing}
    cleaned = []
    seen_titles, seen_bodies = set(), set()
    for index, item in enumerate(items, start=1):
        title = normalize_text(str(item.get("title", "")))
        body = normalize_text(str(item.get("body", "")))
        combined = f"{title} {body}"
        if not (4 <= len(title) <= 80):
            raise ValueError(f"{category} #{index}: title length is {len(title)}")
        if not (15 <= len(body) <= 350):
            raise ValueError(f"{category} #{index}: body length is {len(body)}")
        if not re.search(r"[A-Za-z]", combined) or re.search(r"[\u4e00-\u9fff]", combined):
            raise ValueError(f"{category} #{index}: must be English")
        if contains_hard_banned_content(combined):
            raise ValueError(f"{category} #{index}: contains hard-banned content")
        if FORBIDDEN_CONTEXT.search(combined):
            raise ValueError(f"{category} #{index}: contains a forbidden context")
        if not ADULT_SIGNAL.search(combined):
            raise ValueError(f"{category} #{index}: lacks a clear adult context")
        title_key, body_key = duplicate_key(title), duplicate_key(body)
        if title_key in seen_titles or title_key in existing_titles:
            raise ValueError(f"{category} #{index}: duplicate title")
        if body_key in seen_bodies or body_key in existing_bodies:
            raise ValueError(f"{category} #{index}: duplicate body")
        seen_titles.add(title_key)
        seen_bodies.add(body_key)
        cleaned.append({"category": category, "title": title, "body": body})
    return cleaned


def prompt_for(category: str, guidance: str, count: int, previous_error: str | None) -> str:
    retry = f"\nPrevious validation error: {previous_error}\nCorrect it and return all {count} lines." if previous_error else ""
    return f"""
Create tasteful mild-adult English jokes for an adults-only section of a daily joke bot.

Category: {category}
Guidance: {guidance}

Return exactly {count} lines in this format:
Short unique title|||Complete joke text
Do not output numbering, headers, JSON, Markdown, explanations, or the delimiter inside a joke.

Requirements:
1. Every character is clearly an adult and every romantic or intimate interaction is consensual.
2. Mild sexual suggestion, dating humor, bedroom double meanings, and adult relationship humor are allowed.
3. Keep it tasteful and non-graphic: no anatomy descriptions, sex acts, pornography, bodily fluids, coercion, violence, or humiliation.
4. No profanity, slurs, discrimination, politics, protected-group stereotypes, family-member sexual situations, minors, schools, substances, or intoxication.
5. Avoid spouse/gender stereotypes and hostility. Both people should retain dignity and agency.
6. Every joke needs a clear punchline. Vary question-answer, dialogue, short story, reversal, observation, and wordplay structures.
7. Do not repeat titles, punchlines, core premises, or mass-produce a noun-swapping template.
{retry}
""".strip()


def generate_category(category: str, guidance: str, existing: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    last_error = None
    for attempt in range(1, 5):
        try:
            completed = subprocess.run(
                [
                    "claude", "-p",
                    "Follow stdin exactly. Output only title-triple-pipe-joke lines.",
                    "--model", "haiku", "--output-format", "text",
                ],
                input=prompt_for(category, guidance, count, last_error),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            last_error = "generation timed out"
            print(f"{category}: attempt {attempt} failed: {last_error}", flush=True)
            continue
        if completed.returncode != 0:
            last_error = completed.stderr.strip() or f"claude exit code {completed.returncode}"
            print(f"{category}: attempt {attempt} failed: {last_error}", flush=True)
            continue
        try:
            return validate_batch(category, parse_response(completed.stdout), existing, count)
        except ValueError as exc:
            last_error = str(exc)
            print(f"{category}: attempt {attempt} validation failed: {last_error}", flush=True)
    raise RuntimeError(f"{category}: generation failed: {last_error}")


def load_checkpoint() -> list[dict[str, str]]:
    if not CHECKPOINT_PATH.exists():
        return []
    value = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    accepted = []
    seen_titles, seen_bodies = set(), set()
    for item in value if isinstance(value, list) else []:
        combined = f"{item['title']} {item['body']}"
        title_key, body_key = duplicate_key(item["title"]), duplicate_key(item["body"])
        if contains_hard_banned_content(combined) or FORBIDDEN_CONTEXT.search(combined):
            continue
        if not ADULT_SIGNAL.search(combined) or title_key in seen_titles or body_key in seen_bodies:
            continue
        seen_titles.add(title_key)
        seen_bodies.add(body_key)
        accepted.append(item)
    return accepted


def save_checkpoint(jokes: list[dict[str, str]]) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(jokes, ensure_ascii=False, indent=2), encoding="utf-8")


def add_curated_fill_ins(jokes: list[dict[str, str]]) -> list[dict[str, str]]:
    for category, pairs in CURATED_FILL_INS.items():
        missing = TARGET_COUNTS[category] - sum(item["category"] == category for item in jokes)
        if missing <= 0:
            continue
        candidates = [{"title": title, "body": body} for title, body in pairs[:missing]]
        jokes.extend(validate_batch(category, candidates, jokes, missing))
        print(f"{category}: added {missing} human-reviewed fill-ins", flush=True)
    return jokes


def write_csv(jokes: list[dict[str, str]]) -> None:
    jokes = [
        {**joke, "title": TITLE_REWRITES.get(joke["title"], joke["title"])}
        for joke in jokes
    ]
    counts = Counter(joke["category"] for joke in jokes)
    if len(jokes) != 170 or counts != Counter(TARGET_COUNTS):
        raise RuntimeError(f"invalid adult category counts: {counts}")
    if len({duplicate_key(joke["title"]) for joke in jokes}) != 170:
        raise RuntimeError("adult titles are not globally unique")
    if len({duplicate_key(joke["body"]) for joke in jokes}) != 170:
        raise RuntimeError("adult bodies are not globally unique")
    temp_path = OUTPUT_PATH.with_suffix(".csv.tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "joke_id", "source_id", "category", "title", "body", "score", "permalink",
        ])
        writer.writeheader()
        for index, joke in enumerate(jokes, start=1):
            writer.writerow({
                "joke_id": index,
                "source_id": f"en-{joke['category']}-{index:04d}",
                "category": joke["category"],
                "title": joke["title"],
                "body": joke["body"],
                "score": 100,
                "permalink": "",
            })
    temp_path.replace(OUTPUT_PATH)


def main() -> None:
    if shutil.which("claude") is None:
        raise RuntimeError("claude CLI is not available")
    jokes = add_curated_fill_ins(load_checkpoint())
    save_checkpoint(jokes)
    while True:
        pending = []
        snapshot = list(jokes)
        for category, guidance in CATEGORIES:
            category_count = sum(item["category"] == category for item in jokes)
            target_count = TARGET_COUNTS[category]
            if category_count < target_count:
                pending.append((category, guidance, min(10, target_count - category_count)))
        if not pending:
            break
        for category, _, count in pending:
            print(f"{category}: requesting {count}", flush=True)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(generate_category, category, guidance, snapshot, count): category
                for category, guidance, count in pending
            }
            for future in as_completed(futures):
                category = futures[future]
                try:
                    result = future.result()
                    batch = validate_batch(category, result, jokes, len(result))
                except (RuntimeError, ValueError) as exc:
                    print(f"{category}: batch skipped after retries: {exc}", flush=True)
                    continue
                jokes.extend(batch)
                save_checkpoint(jokes)
                current = sum(item["category"] == category for item in jokes)
                print(f"{category}: checkpointed {current}/50; total={len(jokes)}", flush=True)
    write_csv(jokes)
    print(f"Wrote {len(jokes)} jokes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
