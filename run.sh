#!/usr/bin/env bash
set -euo pipefail
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export PYTHONUNBUFFERED=1
pkill -f quick_poll.py || true
nohup python3 quick_poll.py >> polling_bot.log 2>&1 &
exec gunicorn app:app --bind 0.0.0.0:5000 --workers 1