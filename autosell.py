import threading, time, logging, os, json
logger = logging.getLogger("autosell")

_STATE = {
    "enabled": False,
    "interval": 10,           # seconds
    "rules": [],              # placeholder for future rules
    "thread_alive": False,
    "ticks": 0,
    "last_heartbeat_ts": 0,
    "dry_run": True,          # ALWAYS TRUE for safety
}
_LOCK = threading.RLock()
_THREAD = {"t": None, "stop": False}

def status():
    with _LOCK:
        return dict(_STATE)

def set_interval(seconds: int):
    with _LOCK:
        _STATE["interval"] = max(3, int(seconds))
    return status()

def enable():
    with _LOCK:
        _STATE["enabled"] = True
    _ensure_thread()
    return status()

def disable():
    with _LOCK:
        _STATE["enabled"] = False
    _stop_thread()
    return status()

def _ensure_thread():
    # start background worker if not running
    if _THREAD["t"] and _THREAD["t"].is_alive():
        return
    _THREAD["stop"] = False
    t = threading.Thread(target=_run_loop, name="autosell-loop", daemon=True)
    _THREAD["t"] = t
    t.start()
    logger.info("[autosell] thread started")

def _stop_thread():
    if _THREAD["t"]:
        _THREAD["stop"] = True
        logger.info("[autosell] stop requested")

def _run_loop():
    try:
        while not _THREAD["stop"]:
            with _LOCK:
                _STATE["thread_alive"] = True
                iv = _STATE["interval"]
                enabled = _STATE["enabled"]
                _STATE["last_heartbeat_ts"] = int(time.time())
            # Heartbeat
            logger.info("[autosell] hb enabled=%s interval=%ss ticks=%s",
                        enabled, iv, _STATE["ticks"])
            if enabled:
                # DRY-RUN work placeholder
                try:
                    _dry_run_tick()
                except Exception as e:
                    logger.error("[autosell] tick error: %s", e)
            time.sleep(max(1, iv))
            with _LOCK:
                _STATE["ticks"] += 1
    except Exception as e:
        logger.exception("[autosell] fatal thread error: %s", e)
    finally:
        with _LOCK:
            _STATE["thread_alive"] = False
        logger.info("[autosell] thread stopped")

def _dry_run_tick():
    # This is intentionally a no-op placeholder that simulates "work"
    # Expand later with safe, read-only scanner checks / rule evals
    pass