#!/usr/bin/env bash
set -euo pipefail
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export PYTHONUNBUFFERED=1

# Start the web app (scanners ON only for web)
export FETCH_ENABLE_SCANNERS=1
gunicorn app:app --bind 0.0.0.0:5000 --workers 1 &

# Start the poller (scanners OFF for poller)
export FETCH_ENABLE_SCANNERS=0
nohup python3 simple_polling_bot.py >> polling_bot.log 2>&1 &

# Keep script alive by waiting on the first child
wait -n