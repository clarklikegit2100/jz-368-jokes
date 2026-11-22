"""Daily project report: scan your local git projects, analyse progress, send it to Telegram.

Runs on the PC where the projects live (Windows Task Scheduler calls it every morning).

  python project_agent/project_report.py --dry-run     # print the report, send nothing
  python project_agent/project_report.py               # build and send to Telegram
  python project_agent/project_report.py --no-llm      # skip the Claude analysis

Data sources (all optional except local git):
  * local git      : last commit, commits in 24h / 7 days, uncommitted files, unpushed commits
  * CHANGELOG.md   : latest version, "Known issues" and "Future improvements" bullets -> next steps
  * GitHub API     : open pull requests and issues (GITHUB_TOKEN for private repos)
  * Claude API     : short analysis + today's plan (ANTHROPIC_API_KEY); rule-based fallback otherwise

Settings live in project_agent/config.json (copy config.example.json). Secrets come from the
environment (.env in the repo root is loaded by windows/run_report.ps1, or by this script).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CONFIG = {
    "registry_csv": "../projects.csv",
    "projects": [],
    "focus": [],
    "exclude": [],
    "active_days": 14,
    "stale_days": 30,
    "min_detailed": 3,
    "max_detailed": 10,
    "github_owner": "clarklikegit2100",
    "use_github": True,
    "use_llm": True,
    "llm_model": "claude-opus-5-5",
    "report_language": "English",
    "git_exe": "git",
    "path_map": {},
}

DAY = 86400


# --------------------------------------------------------------------------------------- config
def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines without overriding variables that are already set."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def load_config(path: Path) -> dict:
    config = dict(DEFAULT_CONFIG)
    if path.exists():
        config.update(json.loads(path.read_text(encoding="utf-8-sig")))
    return config


@dataclass
class Project:
    name: str
    path: str
    github: str = ""
    ids: list[str] = field(default_factory=list)
    version: str = ""
    description: str = ""
    focus: bool = False
    # filled by scan
    exists: bool = False
    is_git: bool = False
    branch: str = ""
    last_commit_ts: int = 0
    last_commit_msg: str = ""
    commits_24h: int = 0
    commits_7d: int = 0
    recent_msgs: list[str] = field(default_factory=list)
    uncommitted: int = 0
    unpushed: int = 0
    behind: int = 0
    has_upstream: bool = False
    changelog_version: str = ""
    known_issues: list[str] = field(default_factory=list)
    future: list[str] = field(default_factory=list)
    gh_open_prs: list[str] = field(default_factory=list)
    gh_open_issues: int | None = None
    gh_note: str = ""
    error: str = ""

    @property
    def days_idle(self) -> float | None:
        if not self.last_commit_ts:
            return None
        return (time.time() - self.last_commit_ts) / DAY

    def key_names(self) -> set[str]:
        return {n.lower() for n in [self.name, self.github, *self.ids] if n}


def map_path(path: str, path_map: dict) -> str:
    for src, dst in path_map.items():
        if path.lower().startswith(src.lower()):
            rest = path[len(src):].replace("\\", "/").lstrip("/")
            return str(Path(dst) / rest)
    return path


def load_projects(config: dict) -> list[Project]:
    """Projects from config["projects"] if given, else from the registry CSV (deduplicated by path)."""
    projects: dict[str, Project] = {}
    entries = config.get("projects") or []
    if entries:
        for entry in entries:
            if isinstance(entry, str):
                entry = {"path": entry}
            path = entry["path"]
            name = entry.get("name") or Path(path.replace("\\", "/")).name
            projects[path.lower()] = Project(name=name, path=path, github=entry.get("github", Path(path.replace("\\", "/")).name))
    else:
        csv_path = (HERE / config["registry_csv"]).resolve()
        if not csv_path.exists():
            raise SystemExit(f"No projects configured and registry not found: {csv_path}")
        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                path = (row.get("Path") or "").strip()
                if not path:
                    continue
                name = (row.get("Project Name") or row.get("ID") or path).strip()
                key = path.lower()
                if key in projects:
                    projects[key].name += " / " + name
                    projects[key].ids.append(row.get("ID", ""))
                    continue
                projects[key] = Project(
                    name=name,
                    path=path,
                    github=(row.get("GitHub Name") or "").strip(),
                    ids=[(row.get("ID") or "").strip()],
                    version=(row.get("Version") or "").strip(),
                    description=(row.get("Note") or row.get("Description") or "").strip()[:200],
                )
    exclude = {e.lower() for e in config.get("exclude", [])}
    focus = {f.lower() for f in config.get("focus", [])}
    result = []
    for p in projects.values():
        if p.key_names() & exclude:
            continue
        p.focus = bool(p.key_names() & focus)
        result.append(p)
    return result


# ------------------------------------------------------------------------------------ local git
def git(config: dict, cwd: str, *args: str, timeout: int = 60) -> str:
    out = subprocess.run(
        [config["git_exe"], "-c", "core.quotepath=off", *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git {' '.join(args)} failed")
    return out.stdout


def scan_git(p: Project, config: dict) -> None:
    local = map_path(p.path, config.get("path_map") or {})
    p.exists = Path(local).is_dir()
    if not p.exists:
        p.error = "folder not found"
        return
    try:
        git(config, local, "rev-parse", "--git-dir")
        p.is_git = True
    except Exception:
        p.error = "not a git repository"
        return
    def step(fn):
        try:
            fn()
        except Exception as exc:  # keep going with whatever we have
            first = (str(exc).strip().splitlines() or [exc.__class__.__name__])[0]
            p.error = p.error or f"git: {first}"[:160]

    def branch():
        p.branch = git(config, local, "rev-parse", "--abbrev-ref", "HEAD").strip()

    def history():
        if not git(config, local, "rev-list", "-n", "1", "--all").strip():
            return  # empty repository, no commits yet
        log = git(config, local, "log", "-1", "--format=%ct%x1f%s").strip()
        if log:
            ts, msg = log.split("\x1f", 1)
            p.last_commit_ts, p.last_commit_msg = int(ts), msg.strip()
        now = time.time()
        for line in git(config, local, "log", "--since=7.days", "--format=%ct%x1f%s").strip().splitlines():
            ts, msg = line.split("\x1f", 1)
            p.commits_7d += 1
            if now - int(ts) <= DAY:
                p.commits_24h += 1
            if len(p.recent_msgs) < 3:
                p.recent_msgs.append(msg.strip())

    def status():
        out = git(config, local, "status", "--porcelain", timeout=120)
        p.uncommitted = len([l for l in out.splitlines() if l.strip()])

    def upstream():
        try:
            counts = git(config, local, "rev-list", "--left-right", "--count", "@{u}...HEAD").split()
            p.behind, p.unpushed = int(counts[0]), int(counts[1])
            p.has_upstream = True
        except Exception:
            p.has_upstream = False

    for fn in (branch, history, status, upstream):
        step(fn)
    read_changelog(p, Path(local))


# ------------------------------------------------------------------------------------ changelog
def read_changelog(p: Project, root: Path) -> None:
    for name in ("CHANGELOG.md", "changelog.md", "Changelog.md"):
        path = root / name
        if path.exists():
            break
    else:
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    sections = re.split(r"^## ", text, flags=re.M)
    if len(sections) < 2:
        return
    latest = sections[1]
    p.changelog_version = latest.splitlines()[0].strip()[:60]
    sub = re.split(r"^### ", latest, flags=re.M)
    for block in sub[1:]:
        title, _, body = block.partition("\n")
        bullets = [re.sub(r"\s+", " ", b).strip() for b in re.findall(r"^[-*] (.+(?:\n  +.+)*)", body, flags=re.M)]
        title = title.strip().lower()
        if "known issue" in title:
            p.known_issues = bullets[:3]
        elif "future" in title or "todo" in title or "next" in title:
            p.future = bullets[:3]


# --------------------------------------------------------------------------------------- GitHub
def gh_get(url: str, token: str):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "project-report-bot"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def scan_github(p: Project, config: dict, token: str) -> None:
    owner = config.get("github_owner")
    if not owner or not p.github:
        return
    base = f"https://api.github.com/repos/{owner}/{p.github}"
    try:
        repo = gh_get(base, token)
        pulls = gh_get(base + "/pulls?state=open&per_page=20", token)
        p.gh_open_prs = [f"#{pr['number']} {pr['title']}" for pr in pulls]
        p.gh_open_issues = max(0, int(repo.get("open_issues_count", 0)) - len(pulls))
    except urllib.error.HTTPError as exc:
        p.gh_note = "not found on GitHub (private repo needs GITHUB_TOKEN)" if exc.code == 404 else f"GitHub HTTP {exc.code}"
    except Exception as exc:
        p.gh_note = f"GitHub unreachable ({exc.__class__.__name__})"


# ------------------------------------------------------------------------------------- analysis
def fmt_age(days: float | None) -> str:
    if days is None:
        return "no commits"
    if days < 1:
        hours = int(days * 24)
        return f"{hours}h ago" if hours else "just now"
    return f"{int(days)}d ago"


def status_icon(p: Project, config: dict) -> str:
    d = p.days_idle
    if d is None:
        return "⚪"
    if d <= 3:
        return "🔥"
    if d <= config["active_days"]:
        return "🟢"
    if d <= config["stale_days"]:
        return "🟡"
    return "🔴"


def pick_detailed(projects: list[Project], config: dict) -> tuple[list[Project], list[Project]]:
    ok = [p for p in projects if p.is_git]
    ok.sort(key=lambda p: p.last_commit_ts, reverse=True)
    detailed = [p for p in ok if p.focus]
    for p in ok:
        if p in detailed:
            continue
        recent = p.days_idle is not None and p.days_idle <= config["active_days"]
        if recent or len(detailed) < config["min_detailed"]:
            detailed.append(p)
    detailed = detailed[: max(config["max_detailed"], len([p for p in detailed if p.focus]))]
    rest = [p for p in ok if p not in detailed]
    return detailed, rest


def next_steps(p: Project, config: dict) -> list[str]:
    steps = []
    if p.unpushed:
        steps.append(f"push {p.unpushed} local commit(s) to GitHub")
    if p.uncommitted:
        age = p.days_idle or 0
        tail = f" (last commit {int(age)}d ago)" if age >= 3 else ""
        steps.append(f"review and commit {p.uncommitted} changed file(s){tail}")
    if p.behind:
        steps.append(f"pull {p.behind} new commit(s) from GitHub")
    if p.gh_open_prs:
        steps.append(f"review/merge PR {p.gh_open_prs[0]}")
    if p.future:
        steps.append("next from CHANGELOG: " + p.future[0])
    elif p.known_issues:
        steps.append("fix known issue: " + p.known_issues[0])
    if p.focus and (p.days_idle or 0) > config["active_days"]:
        steps.append(f"focus project idle {int(p.days_idle)}d: continue, or pause it on purpose")
    return steps[:3]


def rule_based_analysis(detailed: list[Project], rest: list[Project], all_ok: list[Project], config: dict) -> str:
    week_commits = sum(p.commits_7d for p in all_ok)
    active_week = [p for p in all_ok if p.commits_7d]
    dirty = [p for p in all_ok if p.uncommitted]
    unpushed = [p for p in all_ok if p.unpushed]
    stale = [p for p in all_ok if (p.days_idle or 1e9) > config["stale_days"]]
    lines = [
        f"• {week_commits} commits in the last 7 days across {len(active_week)} of {len(all_ok)} projects.",
    ]
    if active_week:
        top = max(active_week, key=lambda p: p.commits_7d)
        lines.append(f"• Most momentum: {top.name} ({top.commits_7d} commits this week).")
    else:
        lines.append("• No commits this week. Pick one project and make a small step today.")
    if dirty:
        lines.append(f"• {len(dirty)} project(s) have uncommitted work: " + ", ".join(p.name for p in dirty[:5]) + ("…" if len(dirty) > 5 else ""))
    if unpushed:
        lines.append(f"• {len(unpushed)} project(s) have commits not pushed to GitHub: " + ", ".join(p.name for p in unpushed[:5]))
    if stale:
        lines.append(f"• {len(stale)} project(s) idle more than {config['stale_days']} days.")
    focus_idle = [p for p in all_ok if p.focus and (p.days_idle or 1e9) > config["active_days"]]
    if focus_idle:
        lines.append("• Focus projects falling behind: " + ", ".join(p.name for p in focus_idle))

    plan: list[str] = []
    candidates = sorted(detailed, key=lambda p: (not p.focus, -(p.commits_7d), p.days_idle or 1e9))
    for p in candidates:
        for step in next_steps(p, config)[:1]:
            plan.append(f"{p.name}: {step}")
        if len(plan) >= 3:
            break
    out = "🧠 Analysis\n" + "\n".join(lines)
    if plan:
        out += "\n\n🎯 Today's plan\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(plan, 1))
    return out


def project_facts(p: Project, config: dict) -> dict:
    return {
        "name": p.name,
        "focus": p.focus,
        "branch": p.branch,
        "days_since_last_commit": None if p.days_idle is None else round(p.days_idle, 1),
        "last_commit": p.last_commit_msg,
        "commits_24h": p.commits_24h,
        "commits_7d": p.commits_7d,
        "recent_commit_messages": p.recent_msgs,
        "uncommitted_files": p.uncommitted,
        "unpushed_commits": p.unpushed,
        "behind_remote": p.behind,
        "changelog_latest": p.changelog_version,
        "known_issues": p.known_issues,
        "future_improvements": p.future,
        "open_prs": p.gh_open_prs,
        "open_issues": p.gh_open_issues,
        "description": p.description,
    }


def llm_analysis(detailed: list[Project], rest: list[Project], config: dict, log) -> str | None:
    if not config.get("use_llm") or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        log("anthropic package not installed (pip install anthropic); using rule-based analysis")
        return None
    facts = {
        "today": datetime.now().strftime("%A %Y-%m-%d"),
        "active_days_threshold": config["active_days"],
        "stale_days_threshold": config["stale_days"],
        "projects": [project_facts(p, config) for p in detailed],
        "sleeping_projects": [{"name": p.name, "days_idle": None if p.days_idle is None else int(p.days_idle),
                               "uncommitted_files": p.uncommitted} for p in rest],
    }
    prompt = (
        "You are my personal project assistant. Every morning you read the status of my software and "
        "research projects (data below, collected from local git, CHANGELOG.md and GitHub) and remind me "
        "where I stand, because I juggle many projects and forget their progress.\n\n"
        f"Write in {config.get('report_language', 'English')}, plain text for Telegram (no Markdown, no tables), "
        "at most about 1200 characters, in exactly two parts:\n"
        "🧠 Analysis: 3-5 short bullets (start each with •) on momentum, risks (uncommitted or unpushed work, "
        "stalled focus projects, open PRs), and what the commit messages say I was doing.\n"
        "🎯 Today's plan: a numbered list of the 3 most valuable concrete actions for today, each naming the project. "
        "Prefer finishing in-progress work over starting new things; use CHANGELOG future improvements and known issues. "
        "Only use facts from the data; do not invent features or numbers.\n\n"
        "DATA:\n" + json.dumps(facts, ensure_ascii=False, indent=1)
    )
    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=config.get("llm_model", "claude-opus-5-5"),
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError as exc:
        log(f"Claude API unreachable ({exc}); using rule-based analysis")
        return None
    except anthropic.APIStatusError as exc:
        log(f"Claude API error {exc.status_code}: {str(exc.message)[:200]}; using rule-based analysis")
        return None
    except Exception as exc:  # old SDK without these params, etc.
        log(f"Claude call failed ({exc.__class__.__name__}: {exc}); using rule-based analysis")
        return None
    if response.stop_reason == "refusal":
        log("Claude declined the request; using rule-based analysis")
        return None
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()
    return text or None


# --------------------------------------------------------------------------------------- report
def render_project(p: Project, config: dict) -> str:
    head = f"{status_icon(p, config)} {p.name}"
    version = p.changelog_version.split(" ")[0].strip("[]") if p.changelog_version else ""
    if not version or version.lower() == "unreleased":
        version = p.version or version
    tags = [t for t in (version, p.branch) if t]
    if tags:
        head += f"  [{' · '.join(tags)}]"
    if p.focus:
        head += " ⭐"
    lines = [head]
    if p.last_commit_ts:
        lines.append(f"   Last commit {fmt_age(p.days_idle)}: {p.last_commit_msg[:80]}")
    stats = [f"24h: {p.commits_24h}", f"7d: {p.commits_7d} commits"]
    if p.uncommitted:
        stats.append(f"⚠️ {p.uncommitted} uncommitted")
    if p.unpushed:
        stats.append(f"⬆️ {p.unpushed} unpushed")
    if p.behind:
        stats.append(f"⬇️ {p.behind} behind")
    if not p.has_upstream:
        stats.append("no upstream")
    lines.append("   " + " | ".join(stats))
    if p.gh_open_prs or p.gh_open_issues:
        gh = f"   GitHub: {len(p.gh_open_prs)} open PR(s), {p.gh_open_issues or 0} open issue(s)"
        if p.gh_open_prs:
            gh += f" — {p.gh_open_prs[0][:60]}"
        lines.append(gh)
    steps = next_steps(p, config)
    if steps:
        lines.append("   ➡️ " + steps[0][:140])
    if p.error:
        lines.append(f"   ({p.error})")
    return "\n".join(lines)


def build_report(projects: list[Project], config: dict, use_llm: bool, log) -> str:
    all_ok = [p for p in projects if p.is_git]
    detailed, rest = pick_detailed(projects, config)
    missing = [p for p in projects if not p.is_git]
    parts = [f"📋 Daily Project Report — {datetime.now().strftime('%a %Y-%m-%d')}"]
    active = len([p for p in all_ok if (p.days_idle or 1e9) <= config["active_days"]])
    parts.append(f"{len(all_ok)} projects tracked · {active} active in the last {config['active_days']} days")
    parts.append("\n".join(render_project(p, config) for p in detailed))
    if rest:
        sleepers = ", ".join(f"{p.name} {fmt_age(p.days_idle).replace(' ago', '')}" + (" ⚠️" if p.uncommitted else "") for p in rest)
        parts.append("😴 Sleeping: " + sleepers)
    if missing:
        names = ", ".join(f"{p.name} ({p.error})" for p in missing[:8])
        more = f" and {len(missing) - 8} more" if len(missing) > 8 else ""
        parts.append(f"❓ Not checked: {names}{more}")
    cfg = dict(config, use_llm=config.get("use_llm") and use_llm)
    analysis = llm_analysis(detailed, rest, cfg, log)
    parts.append(analysis or rule_based_analysis(detailed, rest, all_ok, config))
    parts.append("🔥 ≤3d  🟢 active  🟡 cooling  🔴 stale  ⭐ focus")
    return "\n\n".join(parts)


def split_message(text: str, limit: int = 4000) -> list[str]:
    chunks, current = [], ""
    for block in text.split("\n\n"):
        while len(block) > limit:
            chunks.append(block[:limit])
            block = block[limit:]
        if current and len(current) + 2 + len(block) > limit:
            chunks.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        chunks.append(current)
    return chunks


# ----------------------------------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(HERE / "config.json"))
    parser.add_argument("--dry-run", action="store_true", help="print the report instead of sending it")
    parser.add_argument("--no-llm", action="store_true", help="use the rule-based analysis only")
    parser.add_argument("--no-github", action="store_true", help="skip GitHub API calls")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(HERE / ".env")
    config = load_config(Path(args.config))

    def log(msg: str) -> None:
        print(f"[info] {msg}", file=sys.stderr)

    projects = load_projects(config)
    for p in projects:
        scan_git(p, config)
    if config.get("use_github") and not args.no_github:
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        detailed, _ = pick_detailed(projects, config)
        for p in detailed:
            scan_github(p, config, token)
    report = build_report(projects, config, use_llm=not args.no_llm, log=log)

    if args.dry_run:
        print(report)
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("REPORT_TELEGRAM_CHAT_ID", "").strip() or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id or token.startswith("replace_with"):
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set (see .env.example)", file=sys.stderr)
        return 2
    from telegram_sender import TelegramSendError, send_message

    try:
        for chunk in split_message(report):
            send_message(token=token, chat_id=chat_id, text=chunk)
    except TelegramSendError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Sent report ({len(report)} chars, {len(projects)} projects).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
