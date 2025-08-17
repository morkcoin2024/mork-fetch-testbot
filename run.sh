#!/usr/bin/env bash
set -euo pipefail
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export PYTHONUNBUFFERED=1
export FETCH_ENABLE_SCANNERS=1
gunicorn app:app --bind 0.0.0.0:5000 --workers 1 &
export FETCH_ENABLE_SCANNERS=0
nohup python3 simple_polling_bot.py >> polling_bot.log 2>&1 &
wait