#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE="${1:-daily}"
COUNT="${2:-1}"

python3 "$SCRIPT_DIR/send_daily_jokes.py" --phase "$PHASE" --count "$COUNT"
