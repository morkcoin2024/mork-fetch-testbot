#!/usr/bin/env bash
set -euo pipefail
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export PYTHONUNBUFFERED=1

# Start the web app in the background
export FETCH_ENABLE_SCANNERS=1
gunicorn app:app --bind 0.0.0.0:5000 --workers=1 &

# Run the poller in the FOREGROUND so Replit keeps it alive and shows its logs
export FETCH_ENABLE_SCANNERS=0
exec python3 -u simple_polling_bot.py