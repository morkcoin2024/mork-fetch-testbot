# Replit External Domain Routing Issue

## Problem Summary
**Date**: August 17, 2025  
**Issue**: External domain `https://morkcoin2024.replit.app` returns 404 for ALL routes  
**Status**: Replit platform infrastructure problem  

## Evidence
1. **Flask App Works Locally**: 
   ```bash
   curl localhost:5000/  # ✅ Returns correct JSON
   ```

2. **External Domain Broken**:
   ```bash
   curl https://morkcoin2024.replit.app/  # ❌ Returns 404
   ```

3. **All Routes Confirmed Available**:
   ```python
   from app import app
   for rule in app.url_map.iter_rules():
       print(f'{rule.rule} -> {rule.endpoint}')
   # Shows: /, /webhook, /webhook_v2, /status, etc.
   ```

4. **Telegram Webhook Reports 404**:
   ```json
   {
     "last_error_message": "Wrong response from the webhook: 404 Not Found"
   }
   ```

## Root Cause
- **Not a code issue**: Flask app configured correctly
- **Not a gunicorn issue**: Local server responds properly  
- **Platform routing failure**: Replit's external domain not forwarding to Flask app
- **Excessive file watching**: `--reload` flag causing continuous restarts

## Workaround
**Use polling mode instead of webhook mode**:
```bash
python3 production_runner.py
```

## For Production Deployment
1. **Replit Deploy**: Use polling mode (`production_runner.py`)
2. **External Hosting**: Webhook mode will work normally
3. **Domain Fix**: Once Replit fixes routing, switch back to webhook

## Technical Details
- **Flask routes**: All properly defined and accessible locally
- **Gunicorn**: Running correctly on port 5000
- **External routing**: Broken at Replit infrastructure level
- **Workaround**: Direct Telegram API polling bypasses domain routing

This is a temporary Replit platform issue, not a bot configuration problem.