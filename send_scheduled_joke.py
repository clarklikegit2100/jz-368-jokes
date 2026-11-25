"""Send the scheduled Chinese joke using local credentials without printing them."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["morning", "evening"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    environment = os.environ.copy()
    for name in ("env", ".env"):
        path = root / name
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
                    environment[key.strip()] = value.strip().strip("\"'")
    command = [sys.executable, str(root / "send_telegram_joke.py"),
               "--phase", args.phase, "--csv", "daily-jokes-zh-500.csv",
               "--db", "data/jokes-zh.db", "--state", "data/selection_state-zh.json"]
    if args.dry_run:
        command.append("--dry-run")
    result = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)
    if result.returncode:
        # Network exceptions can contain the bot token in the request URL.
        print("Joke delivery failed; check local credentials and network.", file=sys.stderr)
    else:
        print(result.stdout, end="")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
