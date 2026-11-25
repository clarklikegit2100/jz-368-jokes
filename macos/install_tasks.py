"""Install two per-user launchd jobs. Run with --uninstall to remove them."""
import argparse
from pathlib import Path
import plistlib
import subprocess
import sys
import os
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--prepare', action='store_true', help='Only generate reviewable plists')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    runtime = Path.home() / 'Library/Application Support/JZJokes'
    domain = f'gui/{os.getuid()}'
    agents = Path.home() / 'Library/LaunchAgents'
    logs = runtime / 'data/logs'
    if not args.prepare and not args.uninstall:
        runtime.mkdir(parents=True, exist_ok=True)
        runtime.chmod(0o700)
        for name in ['send_scheduled_joke.py', 'send_telegram_joke.py',
                     'send_daily_jokes.py', 'telegram_sender.py', 'joke_store.py',
                     'joke_filters.py', 'joke_content_policy.py', 'daily-jokes-zh-500.csv',
                     'env', '.env']:
            source = root / name
            if source.exists():
                shutil.copy2(source, runtime / name)
                (runtime / name).chmod(0o600)
        logs.mkdir(parents=True, exist_ok=True)
        for name in ['jokes-zh.db', 'selection_state-zh.json']:
            source = root / 'data' / name
            target = runtime / 'data' / name
            if source.exists() and not target.exists():
                shutil.copy2(source, target)
    for phase, hour in [('morning', 8), ('evening', 20)]:
        label = f'com.jz368.jokes.{phase}'
        destination = agents / f'{label}.plist'
        if args.uninstall:
            subprocess.run(['launchctl', 'bootout', f'{domain}/{label}'], capture_output=True)
            destination.unlink(missing_ok=True)
            print(f'Removed {label}')
            continue
        config = {
            'Label': label,
            'ProgramArguments': [sys.executable, str(runtime / 'send_scheduled_joke.py'), phase],
            'WorkingDirectory': str(runtime),
            'StartCalendarInterval': {'Hour': hour, 'Minute': 0},
            'StandardOutPath': str(logs / f'{phase}.log'),
            'StandardErrorPath': str(logs / f'{phase}.error.log'),
            'ProcessType': 'Background',
        }
        prepared = root / 'macos' / f'{label}.plist'
        prepared.write_bytes(plistlib.dumps(config))
        if args.prepare:
            print(prepared)
            continue
        agents.mkdir(parents=True, exist_ok=True)
        subprocess.run(['launchctl', 'bootout', f'{domain}/{label}'], capture_output=True)
        destination.write_bytes(prepared.read_bytes())
        destination.chmod(0o600)
        subprocess.run(['launchctl', 'enable', f'{domain}/{label}'], check=True)
        subprocess.run(['launchctl', 'bootstrap', domain, str(destination)], check=True)
        subprocess.run(['launchctl', 'print', f'{domain}/{label}'], check=True)


if __name__ == '__main__':
    main()
