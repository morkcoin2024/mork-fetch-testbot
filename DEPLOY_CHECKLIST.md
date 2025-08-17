# Replit Deploy Setup Checklist

## A) UI CHECKLIST (Replit Deploy)
- Open: **Deployments** → (current deployment) → **Stop**
- Click: **Edit Deployment**
- **Start command**: `bash run.sh`   *(not gunicorn)*
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

## TROUBLESHOOTING
- If only web app works: Check start command is `bash run.sh` not `gunicorn`
- If no beacons: Deployment may be using cached/old start command
- If poller dies: Look for auto-restart beacon "[RUNSH] poller exited; restarting in 2s"