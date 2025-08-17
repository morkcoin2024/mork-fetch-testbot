# Replit Deploy Setup Checklist

## A) UI CHECKLIST (Replit Deploy)
- Open: **Deployments** → (current deployment) → **Stop**
- Click: **Edit Deployment**
- **Start command**: `python3 production_runner.py`   *(proven working solution)*
  - **Alternative**: `bash run.sh`   *(enhanced dual-service script)*
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

**Primary Option:** `python3 production_runner.py`
- ✅ Proven polling worker system 
- ✅ Successfully processes Telegram commands
- ✅ Auto-restart capabilities
- ✅ Clean process separation

**Alternative:** `bash run.sh`
- ✅ Enhanced dual-service script with startup beacons

## TROUBLESHOOTING
- If only web app works: Check start command is not just `gunicorn`
- If no polling: Look for "[POLL] Started with PID" in logs
- If command responses fail: Check for "✅ Sent message_id=" confirmations