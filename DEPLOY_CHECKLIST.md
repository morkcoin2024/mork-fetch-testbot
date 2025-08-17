# Replit Deploy Setup Checklist

## A) UI CHECKLIST (Replit Deploy)
- Open: **Deployments** → (current deployment) → **Stop**
- Click: **Edit Deployment**
- **Start command**: `gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`   *(webhook mode - RECOMMENDED)*
  - **Alternative**: `python3 production_runner.py`   *(dual-service polling)*
- **Env**: ensure `TELEGRAM_BOT_TOKEN` is present
- **Save** → **Redeploy**
- Open **Logs** for this deployment

## B) VERIFICATION COMMANDS
```bash
# Check for beacon messages in deployment logs:
grep -i "RUNSH" /deployment/logs/*
grep -i "POLL.*boot.*pid" /deployment/logs/*

# Expected log lines:
# [RUNSH] starting run.sh at 2025-08-17T17:18:00Z
# [RUNSH] launching gunicorn (web)
# [RUNSH] starting poller loop...
# [POLL] boot pid= 12345
```

## C) HEALTH CHECK
```bash
# Verify both services running:
curl -s https://your-app.replit.app/   # Web app responds
# Check deployment logs for ongoing "[RUNSH] starting poller loop..." messages
```

## 🎯 RECOMMENDED START COMMANDS

**WEBHOOK MODE (RECOMMENDED):** `gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`
- ✅ Proven webhook system with Telegram API integration
- ✅ Successfully processes all Telegram commands 
- ✅ Single process, maximum reliability
- ✅ No polling conflicts, clean architecture

**Alternative Options:**
- `python3 production_runner.py` (dual-service polling)
- `bash run.sh` (enhanced dual-service script)

## TROUBLESHOOTING
- If only web app works: Check start command is not just `gunicorn`
- If no polling: Look for "[POLL] Started with PID" in logs
- If command responses fail: Check for "✅ Sent message_id=" confirmations