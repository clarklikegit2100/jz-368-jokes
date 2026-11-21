# Changelog

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
