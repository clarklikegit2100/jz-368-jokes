#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


OUTPUT_PATH = Path(__file__).resolve().parent / "daily-jokes-en-500.csv"
CHECKPOINT_PATH = Path(__file__).resolve().parent / "data" / "generated_english_jokes.json"

CATEGORIES = [
    ("wordplay_pun", "Wordplay and clean puns with varied setups and genuinely different punchlines."),
    ("brain_teaser", "Light riddles and lateral-thinking jokes whose answers make sense."),
    ("tech_programming", "Technology, programming, software, the internet, and friendly AI humor accessible to non-experts."),
    ("workplace", "Meetings, offices, remote work, deadlines, and coworkers without insulting professions."),
    ("school_learning", "School, teachers, students, books, tests, and learning for an all-ages audience."),
    ("everyday_life", "Clean observations about errands, hobbies, home life, weather, and ordinary mishaps."),
    ("animals", "Animal humor with distinct species, situations, structures, and punchlines."),
    ("food", "Food, cooking, cafés, groceries, and restaurants using varied joke structures."),
    ("dialogue", "Short original dialogues with varied characters, settings, and clear punchlines."),
    ("mini_story", "Two-to-four-sentence absurd or surprising stories with concise, logical reversals."),
]

BANNED_TERMS = {
    "fuck", "shit", "bitch", "damn", "sex", "sexy", "naked", "penis", "vagina",
    "rape", "suicide", "murder", "kill", "terrorist", "hitler", "nazi", "racist",
    "slut", "whore", "porn", "blowjob", "masturb", "ejaculat", "drugged",
    "wife", "husband", "girlfriend", "boyfriend", "therap", "anxiety",
    "dead", "death", "dying", "shoot", "shot", "gun", "hang", "fight",
    "wine", "beer", "drunk", "alcohol", "drug", "crazy", "idiot", "stupid",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def duplicate_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def contains_banned_term(value: str) -> bool:
    text = value.lower()
    return any(term in text for term in BANNED_TERMS)


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
    if len(items) < max(1, requested_count - 3):
        raise ValueError(f"{category}: requested {requested_count}, got only {len(items)}")
    items = items[:requested_count]
    existing_titles = {duplicate_key(item["title"]) for item in existing}
    existing_bodies = {duplicate_key(item["body"]) for item in existing}
    cleaned = []
    seen_titles, seen_bodies = set(), set()
    for index, item in enumerate(items, start=1):
        title = normalize_text(str(item.get("title", "")))
        body = normalize_text(str(item.get("body", "")))
        if not (4 <= len(title) <= 70):
            raise ValueError(f"{category} #{index}: title length is {len(title)}")
        if not (15 <= len(body) <= 400):
            raise ValueError(f"{category} #{index}: body length is {len(body)}")
        if not re.search(r"[A-Za-z]", title + body):
            raise ValueError(f"{category} #{index}: no English text")
        if re.search(r"[\u4e00-\u9fff]", title + body):
            raise ValueError(f"{category} #{index}: contains Chinese text")
        if contains_banned_term(title + " " + body):
            raise ValueError(f"{category} #{index}: contains a banned term")
        if category == "brain_teaser" and body.rstrip().endswith("?"):
            raise ValueError(f"{category} #{index}: question has no explicit answer")
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
    retry = f"\nThe previous output failed validation: {previous_error}\nCorrect the problem and return all {count} lines." if previous_error else ""
    return f"""
Create a high-quality English joke library for a bot that sends one joke each day.

Category: {category}
Guidance: {guidance}

Return exactly {count} lines in this format:
Short unique title|||Complete joke text
Do not output numbering, a header, JSON, Markdown, explanations, or the delimiter inside a title or joke.

Requirements:
1. Every joke must stand alone and have a clear punchline. Do not mass-produce a template by swapping nouns, places, or characters.
2. Use varied structures: question-and-answer, dialogue, short setup/reversal, observation, and wordplay. One structural skeleton may appear at most three times.
3. Keep each joke concise, natural, and understandable to a general English-speaking audience.
4. Be family-friendly: no profanity, sexual content, violence, politics, substances, discrimination, protected-group stereotypes, illness jokes, or spouse/gender stereotypes.
5. Do not repeat a title, punchline, core premise, or wordplay mechanism.
6. Write original wording rather than copying long internet jokes.
7. For brain_teaser, every line must contain both the question and its explicit answer/punchline in the body.
{retry}
""".strip()


def generate_category(
    category: str,
    guidance: str,
    existing: list[dict[str, str]],
    count: int,
) -> list[dict[str, str]]:
    last_error = None
    for attempt in range(1, 5):
        try:
            completed = subprocess.run(
                [
                    "claude", "-p",
                    "Follow stdin exactly. Output only the requested title-triple-pipe-joke lines.",
                    "--model", "haiku", "--output-format", "text",
                ],
                input=prompt_for(category, guidance, count, last_error),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=180,
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
    deduped = []
    seen_titles, seen_bodies = set(), set()
    rejected = 0
    for item in value if isinstance(value, list) else []:
        combined = item["title"] + " " + item["body"]
        if contains_banned_term(combined):
            rejected += 1
            continue
        if item["category"] == "brain_teaser" and item["body"].rstrip().endswith("?"):
            rejected += 1
            continue
        title_key, body_key = duplicate_key(item["title"]), duplicate_key(item["body"])
        if title_key in seen_titles or body_key in seen_bodies:
            rejected += 1
            continue
        seen_titles.add(title_key)
        seen_bodies.add(body_key)
        deduped.append(item)
    if rejected:
        print(f"checkpoint: removed {rejected} entries that failed current quality rules", flush=True)
    return deduped


def save_checkpoint(jokes: list[dict[str, str]]) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(jokes, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(jokes: list[dict[str, str]]) -> None:
    counts = Counter(joke["category"] for joke in jokes)
    if len(jokes) != 500 or len(counts) != 10 or set(counts.values()) != {50}:
        raise RuntimeError(f"invalid category counts: total={len(jokes)}, categories={counts}")
    if len({duplicate_key(joke["title"]) for joke in jokes}) != 500:
        raise RuntimeError("titles are not globally unique")
    if len({duplicate_key(joke["body"]) for joke in jokes}) != 500:
        raise RuntimeError("bodies are not globally unique")
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
    jokes = load_checkpoint()
    rebuild_category = os.environ.get("REBUILD_CATEGORY")
    if rebuild_category:
        jokes = [joke for joke in jokes if joke["category"] != rebuild_category]
        print(f"{rebuild_category}: removed old checkpoint entries for regeneration", flush=True)
    while True:
        pending = []
        snapshot = list(jokes)
        for category, guidance in CATEGORIES:
            category_count = sum(item["category"] == category for item in jokes)
            if category_count < 50:
                pending.append((category, guidance, min(25, 50 - category_count)))
        if not pending:
            break

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for category, guidance, requested in pending:
                print(f"{category}: generating {requested}", flush=True)
                future = executor.submit(generate_category, category, guidance, snapshot, requested)
                futures[future] = category
            for future in as_completed(futures):
                category = futures[future]
                batch = future.result()
                # Revalidate against batches that completed earlier in this wave.
                batch = validate_batch(category, batch, jokes, len(batch))
                jokes.extend(batch)
                save_checkpoint(jokes)
                category_count = sum(item["category"] == category for item in jokes)
                print(f"{category}: checkpointed {category_count}/50; total={len(jokes)}", flush=True)
    write_csv(jokes)
    print(f"Wrote {len(jokes)} jokes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
