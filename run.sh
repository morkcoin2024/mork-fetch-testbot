#!/usr/bin/env bash
set -euo pipefail

export LOG_LEVEL=${LOG_LEVEL:-INFO}
export PYTHONUNBUFFERED=1

# Kill any old poller (safe if none)
pkill -f simple_polling_bot.py || true

# Start the poller in the background (your lock prevents duplicates)
nohup python3 simple_polling_bot.py >> polling_bot.log 2>&1 &

# Start the web app in the foreground
exec gunicorn app:app --bind 0.0.0.0:5000 --workers 1