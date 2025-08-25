# Mork F.E.T.C.H Bot - Deployment Setup Guide

## 🚀 Replit Deployment Instructions

### Step 1: Configure Environment Variables (CRITICAL)

1. Go to **Replit → Deploy → Edit deployment**
2. **IMPORTANT**: Set environment variable `POLLING_ENABLED=0`
   - This prevents Deploy from polling Telegram (only RUN should poll)
   - Deploy conflicts are eliminated when Deploy stays webhook-only
3. Ensure all other secrets are configured (TELEGRAM_BOT_TOKEN, etc.)

### Step 2: Configure Deployment Start Command

1. Set **Start command** to: `gunicorn main:app --bind 0.0.0.0:5000 --workers=1`
2. Click **Save** then **Redeploy**

### Step 3: Verify Deployment Health

Run these commands to verify the deployment:

```bash
# Check webhook status (should be disabled)
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" \
| python3 -c "import sys,json as j; d=j.load(sys.stdin); print('webhook_url=', d.get('result',{}).get('url'))"

# Check for running bot process
ps aux | grep -E "production_polling_bot\.py" | grep -v grep || echo "NO POLLER"

# Check pending updates (should be 0)
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates?timeout=1" \
| python3 -c "import sys,json as j; d=j.load(sys.stdin); R=d.get('result',[]); print('pending=',len(R))"
```

### Step 4: Test Bot Functionality

Send these commands to @MorkSniperBot via Telegram:
- `/ping` - Basic connectivity test
- `/help` - Display available commands
- `/status` - Show bot status
- `/wallet` - Wallet management

### Current Architecture

- **Single-Poller Design**: Only RUN instance polls Telegram (POLLING_ENABLED=1)
- **Deploy Mode**: POLLING_ENABLED=0 prevents conflicts, serves Flask app only
- **Unified App**: Both RUN and Deploy use main:app configuration
- **Production Ready**: Enhanced /version with runtime tracking and transparent debugging

### Troubleshooting

If bot doesn't respond:
1. **Check POLLING_ENABLED**: Deploy must have `POLLING_ENABLED=0`, RUN should have `POLLING_ENABLED=1`
2. Verify `TELEGRAM_BOT_TOKEN` environment variable is set in Deploy
3. Check deployment logs for errors
4. Ensure no webhook conflicts with: `curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"`
5. Remember: Only RUN instance should be the active Telegram poller

### Critical Environment Settings

**For RUN (Workspace):**
- `POLLING_ENABLED=1` (default, enables Telegram polling)

**For Deploy (Production):**
- `POLLING_ENABLED=0` (REQUIRED, disables polling to prevent conflicts)
- All other environment variables same as RUN

## Status: ✅ Ready for Production Deployment
