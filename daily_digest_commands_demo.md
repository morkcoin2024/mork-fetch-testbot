# Daily Heartbeat Digest - Command Demonstration

## Overview
The Daily Heartbeat Digest feature provides automated status reports delivered at configured UTC times with comprehensive bot health and configuration summaries.

## New Commands (Admin Only)

### `/digest_status`
Shows current digest configuration and target chat information.
```
🗞 Digest: off @ 09:00 UTC  
chat: 1653046781
```

### `/digest_on`
Enables daily digest delivery and starts the background scheduler thread.
```
✅ Daily digest enabled
```

### `/digest_off`
Disables daily digest delivery while preserving time and chat configuration.
```
🛑 Daily digest disabled
```

### `/digest_time HH:MM`
Sets the daily delivery time in UTC format (24-hour).
```
⏰ Digest time set to 14:30 UTC
```

### `/digest_test [note]`
Sends immediate digest with optional custom note for testing.
```
📤 Digest sent: True
```

## Sample Daily Digest Output
```
🗞 Daily Digest — 2025-08-18 19:07:28 UTC
AutoSell: enabled=False alive=None interval=?s
Rules: []
Alerts: chat=not set min_move=0.0% muted_until=0
Note: manual test
—
Tips: /help  •  /autosell_status  •  /watchlist  •  /autosell_logs 10
```

## Smart Chat Selection
The digest system uses intelligent chat selection:
1. **Digest-specific chat** (if set via future `/digest_chat` command)
2. **Alert routing chat** (shared with alert system)
3. **Admin environment variable** (ASSISTANT_ADMIN_TELEGRAM_ID)

## Integration with Existing Systems

### Alert Routing System
- Shares `alert_chat.json` persistence file
- Extends existing 13-command suite to 18 commands
- Uses same admin authentication and configuration patterns

### AutoSell Integration  
- Real-time AutoSell status including enabled state, rules count
- Heartbeat age and tick counter when available
- Graceful handling when AutoSell module unavailable

### Configuration Persistence
```json
{
  "chat_id": 1653046781,
  "min_move_pct": 0.0,
  "rate_per_min": 60,
  "muted_until": 0,
  "discord_webhook": null,
  "digest": {
    "enabled": false,
    "time": "09:00",
    "chat_id": null
  }
}
```

## Background Scheduler
- Runs in dedicated daemon thread
- 30-second configuration refresh cycle
- Intelligent sleep calculation with date rollover
- Never-die exception handling
- Automatic thread initialization on first command

## Technical Implementation
- UTC-based time calculations with `datetime` module
- Thread-safe global state management  
- Regex-based time validation (00:00 to 23:59)
- Atomic file operations for persistence
- Integration with existing `tg_send()` messaging infrastructure

## Production Ready Features
- Backward compatible with existing Alert Routing System
- Thread-safe implementation suitable for multi-worker deployments  
- Comprehensive error handling with graceful degradation
- Persistent configuration across bot restarts
- No performance impact when disabled