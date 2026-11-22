# Daily project report (project agent)

A small "project assistant" that reminds you every morning where each of your projects stands.
It runs on your Windows 11 PC from Task Scheduler (like the joke bot) and sends one Telegram message:

- **Status per project**: last commit and how long ago, commits in 24h / 7 days, uncommitted files,
  commits not yet pushed, open GitHub PRs/issues, and a status icon (🔥 ≤3 days, 🟢 active, 🟡 cooling, 🔴 stale).
- **Sleeping projects** in one line, so nothing is forgotten.
- **Analysis**: momentum, risks (uncommitted/unpushed work, focus projects falling behind).
- **Today's plan**: the 3 most useful next actions, using each project's `CHANGELOG.md`
  ("Future improvements" and "Known issues") plus git state.

The analysis is written by Claude when `ANTHROPIC_API_KEY` is set; otherwise a rule-based version is used,
so the report always arrives.

## Which projects

By default it reads `..\projects.csv` (your project registry) and checks every local folder listed there.
Projects with commits in the last 14 days get a full block (at least 3, at most 10); the rest go in the
"Sleeping" line. To change this, edit `project_agent\config.json`:

| Setting | Meaning |
| --- | --- |
| `focus` | Names/IDs/GitHub names always shown in full and marked ⭐, e.g. `["GMorpho", "BSGMorpho"]` |
| `exclude` | Names/IDs to skip completely, e.g. `["cell-tracker-gnn-test"]` |
| `projects` | Optional explicit list instead of the CSV: `["F:\\GitHub\\GMorpho", {"path": "F:\\GitHub\\X", "name": "X", "github": "X"}]` |
| `active_days` / `stale_days` | Thresholds for 🟢 and 🔴 (default 14 / 30) |
| `report_language` | Language of the Claude analysis, e.g. `"Chinese"` |
| `use_llm`, `use_github` | Turn Claude analysis or GitHub API calls off |

## Setup (once)

1. **Secrets**: the script reuses `F:\GitHub\jz-368-jokes\.env` (same `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
   as the jokes). Optional extra lines:

   ```
   # Claude analysis (https://console.anthropic.com -> API keys)
   ANTHROPIC_API_KEY=sk-ant-...
   # Open PRs/issues of private repos (GitHub -> Settings -> Developer settings -> fine-grained token, read-only)
   GITHUB_TOKEN=github_pat_...
   # Send the report to a different chat than the jokes
   # REPORT_TELEGRAM_CHAT_ID=
   ```

2. **Claude package** (only for the Claude analysis): `py -3 -m pip install anthropic`
3. **Preview**: double-click `project_agent\windows\preview_report.bat` (prints the report, sends nothing).
4. **Send a test**: double-click `project_agent\windows\send_report_now.bat`.
5. **Schedule**: double-click `project_agent\windows\install_report_task.bat` (daily 07:30, before the 08:00 joke).
   Other time: `powershell -ExecutionPolicy Bypass -File project_agent\windows\install_report_task.ps1 -At 07:00`.
   Remove: `project_agent\windows\uninstall_report_task.ps1`.

Logs: `data\logs\project-report-YYYY-MM.log`. Git must be on PATH (Git for Windows).

## Tip

The "Today's plan" gets much better when each project's `CHANGELOG.md` keeps its
"Future improvements" and "Known issues" sections current (your rules01.md already asks for that).
