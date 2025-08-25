#!/usr/bin/env bash
set -euo pipefail
: "${TELEGRAM_BOT_TOKEN?set in env}"
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook" \
| python3 -c "import sys,json as j;print(j.dumps(j.load(sys.stdin), indent=2))"
