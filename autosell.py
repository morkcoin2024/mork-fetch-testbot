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
_RULES = []  # in-memory, dry-run only  [{mint,tp,sl,trail,size}]

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

# --------- simple rule API (DRY-RUN) ----------
def list_rules():
    with _LOCK:
        return [dict(r) for r in _RULES]

get_rules = list_rules  # alias used by help/handlers

def set_rule(mint: str, **kw):
    """Create/update rule for a mint. kw can include tp, sl, trail, size (ints)."""
    mint = (mint or "").strip()
    if not mint:
        raise ValueError("mint required")
    rule = {"mint": mint}
    for k in ("tp","sl","trail","size"):
        v = kw.get(k)
        if v is not None:
            try: rule[k] = int(v)
            except: raise ValueError(f"{k} must be int")
    with _LOCK:
        # upsert
        for r in _RULES:
            if r["mint"].lower() == mint.lower():
                r.update(rule)
                break
        else:
            _RULES.append(rule)
    return rule

def remove_rule(mint: str):
    mint = (mint or "").strip()
    if not mint: return 0
    with _LOCK:
        n0 = len(_RULES)
        _RULES[:] = [r for r in _RULES if r["mint"].lower()!=mint.lower()]
        return n0 - len(_RULES)