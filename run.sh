#!/usr/bin/env bash
set -euo pipefail
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export PYTHONUNBUFFERED=1

# Safety: ensure polling mode (remove webhook every boot; idempotent)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook" >/dev/null 2>&1 || true
fi

# Start the web app in the background (scanners ON only for web)
export FETCH_ENABLE_SCANNERS=1
gunicorn app:app --bind 0.0.0.0:5000 --workers=1 &

# Run the poller in the FOREGROUND with an auto-restart loop (scanners OFF)
export FETCH_ENABLE_SCANNERS=0
while true; do
  echo "[run] starting poller..."
  python3 -u simple_polling_bot.py
  code=$?
  echo "[run] poller exited with code=$code; restarting in 2s"
  sleep 2
done