#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export POLLING_ENABLED=1   # WORKSPACE runs the poller
# Safety: make sure no other pollers/gunicorn leftovers exist
pkill -f 'production_polling_bot\.py|working_polling_bot\.py|simple_polling_bot\.py' || true
pkill -f gunicorn || true
# Ensure polling mode (no webhook)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook" >/dev/null 2>&1 || true
fi
# Start a single gunicorn worker (integrated poller lives inside the app)
exec gunicorn app:app --workers=1 --bind 0.0.0.0:5000