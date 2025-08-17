# Mork F.E.T.C.H Bot - Deployment Setup Guide

## 🚀 Replit Deployment Instructions

### Step 1: Configure Deployment Start Command

1. Go to **Replit → Deploy → Edit deployment**
2. Set **Start command** to: `python3 -u working_polling_bot.py`
3. Click **Save** then **Redeploy**

### Step 2: Verify Deployment Health

Run these commands to verify the deployment:

```bash
# Check webhook status (should be disabled)
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" \
| python3 -c "import sys,json as j; d=j.load(sys.stdin); print('webhook_url=', d.get('result',{}).get('url'))"

# Check for running bot process
ps aux | grep -E "working_polling_bot\.py" | grep -v grep || echo "NO POLLER"

# Check pending updates (should be 0)
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates?timeout=1" \
| python3 -c "import sys,json as j; d=j.load(sys.stdin); R=d.get('result',[]); print('pending=',len(R))"
```

### Step 3: Test Bot Functionality

Send these commands to @MorkSniperBot via Telegram:
- `/ping` - Basic connectivity test
- `/help` - Display available commands  
- `/status` - Show bot status
- `/wallet` - Wallet management

### Current Architecture

- **Standalone Polling**: `working_polling_bot.py` runs as the main process
- **No Webhook**: Polling mode bypasses Replit external domain issues
- **Production Ready**: Auto-restart mechanisms ensure reliability

### Troubleshooting

If bot doesn't respond:
1. Check deployment logs for errors
2. Verify `TELEGRAM_BOT_TOKEN` environment variable is set
3. Ensure no webhook conflicts with: `curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"`
4. Restart deployment if needed

## Status: ✅ Ready for Production Deployment