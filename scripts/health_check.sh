#!/usr/bin/env bash
set -e
echo "Process:" && ps aux | grep -E "working_polling_bot\.py" | grep -v grep || echo "NO POLLER"
echo -n "Webhook: " && curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" \
| python3 -c "import sys,json as j; d=j.load(sys.stdin); print(d.get('result',{}).get('url'))"
echo -n "Pending: " && curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates?timeout=1" \
| python3 -c "import sys,json as j; d=j.load(sys.stdin); print(len(d.get('result',[])))"
echo "--- live_bot.log (tail) ---" && tail -n 30 live_bot.log || true