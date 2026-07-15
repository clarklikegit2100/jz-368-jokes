#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path


OUTPUT_PATH = Path(__file__).resolve().parent / "daily-jokes-zh-500.csv"
CHECKPOINT_PATH = Path(__file__).resolve().parent / "data" / "generated_chinese_jokes.json"

CATEGORIES = [
    ("cold_pun", "冷笑话与谐音梗。答案要有明确文字游戏，但不要只替换一个名词批量套模板。"),
    ("brain_teaser", "脑筋急转弯。问题与答案逻辑要成立，答案出人意料但能理解。"),
    ("programmer", "程序员、软件、网络与人工智能。兼顾非技术读者也能看懂。"),
    ("workplace", "职场、会议、加班与同事相处。轻松友善，不攻击具体职业或群体。"),
    ("campus", "校园、老师、学生、考试与学习。适合全年龄阅读。"),
    ("daily_life", "家庭与日常生活观察。使用多种叙事方式，不写夫妻刻板印象。"),
    ("animals", "动物主题拟人笑话。不同动物使用不同笑点，不批量套同一句式。"),
    ("food", "食物、做饭、餐厅主题。包含谐音、反转和短故事等多种结构。"),
    ("dialogue", "原创短对话段子。人物关系和场景要多样，每条有清楚的包袱。"),
    ("mini_story", "两到四句的荒诞反转小故事。结尾要有意外但合理的笑点。"),
]

BANNED_TERMS = {
    "色情", "强奸", "自杀", "纳粹", "恐怖袭击", "种族", "残疾人",
    "傻子", "弱智", "妓女", "出轨", "家暴", "未成年人性",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def duplicate_key(value: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", value).lower()


def parse_response(raw: str) -> list[dict[str, str]]:
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("```") or "|||" not in line:
            continue
        title, body = line.split("|||", 1)
        title = re.sub(r"^\s*\d+[.、)）]\s*", "", title).strip()
        items.append({"title": title, "body": body.strip()})
    if not items:
        raise ValueError("response did not contain delimiter-formatted jokes")
    return items


def validate_batch(category: str, items: list[dict[str, str]], existing: list[dict[str, str]], requested_count: int) -> list[dict[str, str]]:
    minimum_count = max(1, requested_count - 3)
    if len(items) < minimum_count:
        raise ValueError(f"{category}: requested {requested_count} jokes, got only {len(items)}")
    if len(items) > requested_count:
        items = items[:requested_count]

    existing_titles = {duplicate_key(item["title"]) for item in existing}
    existing_bodies = {duplicate_key(item["body"]) for item in existing}
    cleaned = []
    seen_titles, seen_bodies = set(), set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{category} #{index}: item is not an object")
        title = normalize_text(str(item.get("title", "")))
        body = normalize_text(str(item.get("body", "")))
        if not (3 <= len(title) <= 24):
            raise ValueError(f"{category} #{index}: title length is {len(title)}")
        if not (10 <= len(body) <= 180):
            raise ValueError(f"{category} #{index}: body length is {len(body)}")
        if not re.search(r"[\u4e00-\u9fff]", title + body):
            raise ValueError(f"{category} #{index}: no Chinese characters")
        if any(term in title + body for term in BANNED_TERMS):
            raise ValueError(f"{category} #{index}: contains a banned term")
        title_key, body_key = duplicate_key(title), duplicate_key(body)
        if title_key in seen_titles or title_key in existing_titles:
            raise ValueError(f"{category} #{index}: duplicate title")
        if body_key in seen_bodies or body_key in existing_bodies:
            raise ValueError(f"{category} #{index}: duplicate body")
        seen_titles.add(title_key)
        seen_bodies.add(body_key)
        cleaned.append({"category": category, "title": title, "body": body})

    title_counts = Counter(duplicate_key(item["title"]) for item in cleaned)
    if max(title_counts.values()) > 1:
        raise ValueError(f"{category}: duplicate title")
    return cleaned


def prompt_for(category: str, guidance: str, requested_count: int, previous_error: str | None = None) -> str:
    retry = f"\n上一次输出未通过校验：{previous_error}\n请修正全部问题并重新输出完整 {requested_count} 条。" if previous_error else ""
    return f"""
你正在为一个每天推送笑话的项目编写高质量中文笑话库。

类别：{category}
类别说明：{guidance}

请只输出正好 {requested_count} 行，每行格式必须是：
标题|||完整笑话正文
不要输出表头、编号、JSON、Markdown或额外说明；标题和正文内部都不能出现 |||。

严格要求：
1. 每条必须是独立创作的完整笑话，不能用主角×地点、名词替换等批量组合模板。
2. 同一种句式或叙事骨架最多使用 3 次；混合问答、对话、短故事、反转、双关等结构。
3. 以简体中文为主，正文约 15到120字，有明确笑点，不写只有励志句而没有包袱的内容。
4. 家庭友好，不含色情、暴力、自杀、政治、歧视、疾病嘲讽或冒犯性内容。
5. 不重复标题、包袱、谐音或核心设定；严格遵守每行一个“标题|||正文”。
6. 不照抄长篇网络段子；可以使用常见语言现象，但表达要重新创作。
{retry}
""".strip()


def generate_category(category: str, guidance: str, existing: list[dict[str, str]], requested_count: int) -> list[dict[str, str]]:
    last_error = None
    for attempt in range(1, 4):
        prompt = prompt_for(category, guidance, requested_count, last_error)
        try:
            completed = subprocess.run(
                [
                    "claude", "-p", "严格按照标准输入要求输出指定行数的标题三竖线正文，不要任何额外内容。",
                    "--model", "haiku", "--output-format", "text",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=150,
                check=False,
            )
        except subprocess.TimeoutExpired:
            last_error = "generation timed out after 150 seconds"
            print(f"{category}: attempt {attempt} command failed: {last_error}", flush=True)
            continue
        if completed.returncode != 0:
            last_error = completed.stderr.strip() or f"claude exit code {completed.returncode}"
            print(f"{category}: attempt {attempt} command failed: {last_error}", flush=True)
            continue
        try:
            return validate_batch(category, parse_response(completed.stdout), existing, requested_count)
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            print(f"{category}: attempt {attempt} validation failed: {last_error}")
    raise RuntimeError(f"{category}: generation failed after 3 attempts: {last_error}")


def load_checkpoint() -> list[dict[str, str]]:
    if not CHECKPOINT_PATH.exists():
        return []
    value = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        return []

    deduped = []
    seen_titles, seen_bodies = set(), set()
    for item in value:
        title_key = duplicate_key(item["title"])
        body_key = duplicate_key(item["body"])
        if title_key in seen_titles or body_key in seen_bodies:
            continue
        seen_titles.add(title_key)
        seen_bodies.add(body_key)
        deduped.append(item)
    if len(deduped) != len(value):
        print(f"checkpoint: removed {len(value) - len(deduped)} duplicate entries", flush=True)
    return deduped


def save_checkpoint(jokes: list[dict[str, str]]) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(jokes, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(jokes: list[dict[str, str]]) -> None:
    if len(jokes) != 500:
        raise RuntimeError(f"refusing to write {len(jokes)} jokes; expected 500")
    category_counts = Counter(joke["category"] for joke in jokes)
    if set(category_counts.values()) != {50} or len(category_counts) != 10:
        raise RuntimeError(f"category counts are not balanced: {category_counts}")
    if len({duplicate_key(joke["title"]) for joke in jokes}) != 500:
        raise RuntimeError("titles are not globally unique")
    if len({duplicate_key(joke["body"]) for joke in jokes}) != 500:
        raise RuntimeError("bodies are not globally unique")
    temp_path = OUTPUT_PATH.with_suffix(".csv.tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["joke_id", "source_id", "category", "title", "body", "score", "permalink"],
        )
        writer.writeheader()
        for index, joke in enumerate(jokes, start=1):
            writer.writerow({
                "joke_id": index,
                "source_id": f"zh-{joke['category']}-{index:04d}",
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
    for category, guidance in CATEGORIES:
        category_count = sum(item["category"] == category for item in jokes)
        if category_count > 50:
            raise RuntimeError(f"{category}: checkpoint contains {category_count} jokes")
        if category_count == 50:
            print(f"{category}: using complete checkpoint")
            continue
        while category_count < 50:
            requested_count = min(25, 50 - category_count)
            print(f"{category}: generating up to {requested_count}; current={category_count}/50", flush=True)
            batch = generate_category(category, guidance, jokes, requested_count)
            jokes.extend(batch)
            category_count += len(batch)
            save_checkpoint(jokes)
            print(f"{category}: checkpointed {category_count}/50; total={len(jokes)}", flush=True)

    expected = {category for category, _ in CATEGORIES}
    actual = {item["category"] for item in jokes}
    if actual != expected:
        raise RuntimeError(f"category mismatch: expected={expected}, actual={actual}")
    write_csv(jokes)
    print(f"Wrote {len(jokes)} jokes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
