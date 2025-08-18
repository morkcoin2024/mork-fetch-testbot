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

# --------- persistence API (DRY-RUN) ----------
def force_save():
    """Save current state to autosell_state.json with backup"""
    try:
        with _LOCK:
            state_data = {
                "enabled": _STATE["enabled"],
                "interval": _STATE["interval"],
                "rules": _RULES[:],  # copy
                "dry_run": _STATE["dry_run"]
            }
        # Save primary file
        tmp = "autosell_state.json.tmp"
        with open(tmp, "w") as f:
            json.dump(state_data, f, indent=2)
        os.replace(tmp, "autosell_state.json")
        
        # Best-effort backup copy
        try:
            backup_tmp = "autosell_state.backup.json.tmp"
            with open(backup_tmp, "w") as f:
                json.dump(state_data, f, indent=2)
            os.replace(backup_tmp, "autosell_state.backup.json")
        except Exception:
            pass
            
        logger.info("[autosell] saved autosell_state.json (rules=%s)", len(state_data["rules"]))
        return True
    except Exception as e:
        logger.error("[autosell] save failed: %s", e)
        return False

def reload():
    """Load state from autosell_state.json"""
    try:
        with open("autosell_state.json", "r") as f:
            state_data = json.load(f)
        with _LOCK:
            _STATE["enabled"] = state_data.get("enabled", False)
            _STATE["interval"] = max(3, int(state_data.get("interval", 10)))
            _STATE["dry_run"] = state_data.get("dry_run", True)
            _RULES[:] = state_data.get("rules", [])
        logger.info("[autosell] loaded from autosell_state.json")
        return status()
    except FileNotFoundError:
        logger.info("[autosell] no autosell_state.json found")
        return status()
    except Exception as e:
        logger.error("[autosell] load failed: %s", e)
        return status()

def reset():
    """Reset to default state and stop thread"""
    with _LOCK:
        _STATE["enabled"] = False
        _STATE["interval"] = 10
        _STATE["ticks"] = 0
        _STATE["dry_run"] = True
        _RULES.clear()
    _stop_thread()
    logger.info("[autosell] reset to defaults")
    return status()

# test-only: break the thread without disabling (to trigger watchdog)
def test_break():
    _THREAD["stop"] = True
    logger.warning("[autosell] test_break(): stop flag set without disable()")