# Changelog

## [Unreleased] - 2026-11-21

### New features
- `project_agent/`: daily project report sent to Telegram every morning from Windows Task Scheduler.
  - `project_report.py`: reads the project registry `projects.csv`, checks each local git repo (last commit,
    commits in 24h/7d, uncommitted files, unpushed commits), each repo's `CHANGELOG.md` (Known issues /
    Future improvements), open GitHub PRs/issues, then writes an analysis and today's top-3 plan
    (Claude API if `ANTHROPIC_API_KEY` is set, rule-based otherwise). `--dry-run`, `--no-llm`, `--no-github`.
  - `config.json`: focus/exclude lists, thresholds, language.
  - `windows/`: `run_report.ps1`, `install_report_task.ps1/.bat` (daily 07:30), `send_report_now.bat`,
    `preview_report.bat`, `uninstall_report_task.ps1`. Logs to `data/logs/project-report-*.log`.

### Modifications
- `.env.example`: optional `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `REPORT_TELEGRAM_CHAT_ID`, `REPORT_PYTHON`.

### Known issues
- Not yet run on Windows itself; verify with `project_agent/windows/preview_report.bat`.
- The Claude analysis was tested up to authentication only (no API key in the test environment).
- Without `GITHUB_TOKEN`, private repos show no PR/issue counts.

### Future improvements
- Remember yesterday's report to show what changed day over day.
- Move `project_agent/` to its own repository if it grows.

## [Unreleased] - 2026-11-20

### New features
- `windows/` scripts to send jokes from a Windows 11 PC with Task Scheduler:
  - `run_joke.ps1`: sends one joke for a slot, loads secrets from `.env`, logs to `data/logs/`.
  - `install_tasks.ps1` / `install_tasks.bat`: register daily tasks at 08:00, 12:30, 20:00
    (configurable, optional `-RunWhenSignedOut`); missed runs start when the PC is back.
  - `uninstall_tasks.ps1`: remove the tasks.
  - `send_joke_now.bat`: send one joke immediately for testing.

### Modifications
- `.env.example`: documents optional `JOKE_PYTHON`.
- `README.md`: Windows Task Scheduler setup section.

### Bug fixes
- Diagnosed why jokes stopped: GitHub auto-disabled the scheduled workflow
  "Telegram daily jokes" (state `disabled_inactivity`) after 60 days without repo
  activity. Last successful run: 2026-10-11. Delivery now can run from the local PC.

### Known issues
- Windows scripts were written without a Windows test run; verify with `send_joke_now.bat`.
- Local deck state (`data/selection_state-*.json`) is separate from the GitHub Actions cache,
  so the PC starts a fresh shuffled cycle.
- The PC must be on (or wake) for jokes to send.

### Future improvements
- Optionally re-enable the GitHub workflow as a backup only if the PC tasks are removed.
