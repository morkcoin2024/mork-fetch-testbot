#!/usr/bin/env bash
set -euo pipefail
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export PYTHONUNBUFFERED=1
echo "[RUNSH] starting run.sh at $(date -u +%FT%TZ)"

# Always clear webhook on boot so polling isn't conflicted
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook" >/dev/null 2>&1 || true
fi

# Start web app (background)
export FETCH_ENABLE_SCANNERS=1
echo "[RUNSH] launching gunicorn (web)"
gunicorn app:app --bind 0.0.0.0:5000 --workers=1 &

# Poller (foreground) with simple auto-restart
export FETCH_ENABLE_SCANNERS=0
while true; do
  echo "[RUNSH] starting poller loop..."
  python3 -u simple_polling_bot.py || true
  echo "[RUNSH] poller exited; restarting in 2s"
  sleep 2
done