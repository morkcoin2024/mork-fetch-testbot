#!/usr/bin/env bash
set -euo pipefail
: "${TELEGRAM_BOT_TOKEN?set in env}"
: "${PUBLIC_URL?e.g. https://<your-repl>.repl.co}"
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d url="${PUBLIC_URL}/webhook" \
| python3 -c "import sys,json as j;print(j.dumps(j.load(sys.stdin), indent=2))"
