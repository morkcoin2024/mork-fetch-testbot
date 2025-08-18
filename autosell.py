import threading, time, logging, os, json, math, hashlib, collections, requests
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
_EVENTS = collections.deque(maxlen=100)  # rolling log of dry-run decisions
_PX_CACHE = {}  # mint -> (ts, price)
_PX_TTL   = int(os.environ.get("FETCH_PRICE_TTL_SEC", "5"))
_PX_ENABLE_DEX = True  # toggleable at runtime via admin commands
_WATCH = {}   # mint -> {"last": float|None}
_WATCH_SENS = float(os.environ.get("FETCH_WATCH_SENS_PCT", "1.0"))  # % change to alert
_ALERTS_ENABLED = True
_STATE_FILE = os.environ.get("FETCH_STATE_FILE", "autosell_state.json")

def status():
    with _LOCK:
        return {
            **dict(_STATE),
            "watch": sorted(list(_WATCH.keys())),
            "watch_sens_pct": _WATCH_SENS,
            "alerts": _ALERTS_ENABLED,
        }

def set_interval(seconds: int):
    with _LOCK:
        _STATE["interval"] = max(3, int(seconds))
    _save_state()
    return status()

def enable():
    with _LOCK:
        _STATE["enabled"] = True
    _ensure_thread()
    _save_state()
    return status()

def disable():
    with _LOCK:
        _STATE["enabled"] = False
    _stop_thread()
    _save_state()
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
    # Iterate rules and produce a DRY-RUN decision + log line
    changed = False
    with _LOCK:
        rules = [dict(r) for r in _RULES]
    for r in rules:
        mint = r.get("mint","").strip()
        if not mint:
            continue
        price, source = _get_price(mint)
        if price is None:
            price, source = _sim_price(mint), "sim"
        # initialize per-rule reference/peak
        if "ref" not in r or r["ref"] is None:
            r["ref"] = float(price); changed = True
        if "peak" not in r or r["peak"] is None:
            r["peak"] = float(price); changed = True
        if price > r["peak"]:
            r["peak"] = float(price); changed = True
        # evaluate conditions
        reason = None
        ref  = float(r["ref"]); peak = float(r["peak"])
        tp   = _as_int(r.get("tp"));    sl = _as_int(r.get("sl"))
        trail= _as_int(r.get("trail")); size = _as_int(r.get("size"))
        if sl   is not None and price <= ref  * (1 - sl/100.0):   reason = f"SL{sl}%"
        if tp   is not None and price >= ref  * (1 + tp/100.0):   reason = reason or f"TP{tp}%"
        if trail is not None and price <= peak * (1 - trail/100.0): reason = reason or f"TRAIL{trail}%"
        if reason:
            _log_event(f"[DRY] would SELL {mint} @ {price:.6f} reason={reason} src={source} ref={ref:.6f} peak={peak:.6f}" + (f" size={size}" if size else ""))
        else:
            _log_event(f"[DRY] hold {mint} price={price:.6f} src={source} ref={ref:.6f} peak={peak:.6f}")
        # write back mutated state to canonical rules
        _merge_rule_runtime(mint, ref=r["ref"], peak=r["peak"])
    if changed:
        force_save()
    # Evaluate watchlist alerts
    _watch_tick()

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
    _save_state()
    return rule

def remove_rule(mint: str):
    mint = (mint or "").strip()
    if not mint: return 0
    with _LOCK:
        n0 = len(_RULES)
        _RULES[:] = [r for r in _RULES if r["mint"].lower()!=mint.lower()]
        removed = n0 - len(_RULES)
    if removed > 0: _save_state()
    return removed

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

def _as_int(v):
    try:
        return int(v) if v is not None else None
    except:
        return None

def _merge_rule_runtime(mint, **kw):
    with _LOCK:
        for rr in _RULES:
            if rr.get("mint","").lower()==mint.lower():
                for k,v in kw.items(): rr[k]=v
                break

def _log_event(s: str):
    ts = time.strftime("%H:%M:%S", time.gmtime())
    line = f"{ts} {s}"
    _EVENTS.append(line)
    logger.info("[autosell] %s", s)

# ------- price sources -------
def _get_price(mint:str):
    """Return (price, source) or (None, None). Uses short cache + Dexscreener; falls back to sim in caller."""
    now = time.time()
    m = (mint or "").strip()
    if not m:
        return None, None
    # cache
    ent = _PX_CACHE.get(m.lower())
    if ent and (now - ent[0]) <= _PX_TTL:
        return ent[1], ("dex(cache)" if _PX_ENABLE_DEX else "sim(cache)")
    # fresh from Dexscreener if enabled
    if _PX_ENABLE_DEX:
        p = _dex_price(m)
        if p is not None:
            _PX_CACHE[m.lower()] = (now, float(p))
            return float(p), "dex"
    return None, None

def _dex_price(mint:str):
    """Dexscreener public API – best-effort USD price."""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
    try:
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None
        j = r.json() or {}
        pairs = j.get("pairs") or []
        if not pairs:
            return None
        # choose the pair with highest liquidityUsd, else first with priceUsd
        pairs = [p for p in pairs if p.get("priceUsd")]
        if not pairs:
            return None
        best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd") or 0.0))
        return float(best["priceUsd"])
    except Exception:
        return None

def _sim_price(mint:str):
    """Deterministic-ish pseudo price for safe DRY-RUN testing."""
    # base from hash(mint), gentle oscillation by time
    h = int(hashlib.sha256(mint.encode()).hexdigest(), 16)
    base = 0.5 + (h % 5000) / 10000.0          # 0.5 .. 1.0
    t = time.time() / 12.0                     # 12s cycle
    wiggle = 1.0 + 0.03 * math.sin(2*math.pi*t + (h % 360))
    return round(base * wiggle, 6)

# ----- admin helpers for price system -----
def price_config():
    return {
        "ttl": _PX_TTL,
        "dex_enabled": _PX_ENABLE_DEX,
        "cache_size": len(_PX_CACHE),
    }

def set_price_ttl(sec:int):
    global _PX_TTL
    try:
        sec = int(sec)
        _PX_TTL = max(1, min(sec, 3600))
        return _PX_TTL
    except Exception:
        return _PX_TTL

def set_price_source(enable_dex:bool):
    global _PX_ENABLE_DEX
    _PX_ENABLE_DEX = bool(enable_dex)
    return _PX_ENABLE_DEX

def clear_price_cache():
    _PX_CACHE.clear()
    return 0

# ---------- Watchlist ----------
def watch_add(mint:str):
    m = (mint or "").strip()
    if not m: return 0
    with _LOCK:
        _WATCH.setdefault(m, {"last": None})
    _save_state()
    return 1

def watch_remove(mint:str):
    m = (mint or "").strip()
    if not m: return 0
    with _LOCK:
        ok = 1 if _WATCH.pop(m, None) is not None else 0
    if ok: _save_state()
    return ok

def watch_list():
    with _LOCK:
        return {k: dict(v) for k,v in _WATCH.items()}

def watch_set_sens(pct:float):
    global _WATCH_SENS
    try:
        pct = float(pct)
        pct = max(0.1, min(pct, 100.0))
    except Exception:
        pass
    _WATCH_SENS = pct
    _save_state()
    return _WATCH_SENS

def _watch_tick():
    """Emit alerts when price changes exceed threshold."""
    global _WATCH_SENS
    sens = _WATCH_SENS
    with _LOCK:
        items = list(_WATCH.items())
    for mint, ent in items:
        px, src = _get_price(mint)
        if px is None:
            px, src = _sim_price(mint), "sim"
        last = ent.get("last")
        if last is None:
            # initialize baseline quietly
            with _LOCK:
                _WATCH[mint]["last"] = px
            continue
        change = 0.0 if last == 0 else (px - last) / last * 100.0
        if _ALERTS_ENABLED and abs(change) >= sens:
            _log_event(f"[ALERT] {mint} {change:+.2f}% price={px:.6f} src={src}")
            with _LOCK:
                _WATCH[mint]["last"] = px

# ---------- Persistence ----------
def _save_state():
    try:
        with _LOCK:
            data = {
                "rules": list(_RULES),
                "watch": {k: {"last": v.get("last")} for k,v in _WATCH.items()},
                "watch_sens": _WATCH_SENS,
                "interval": _STATE["interval"],
                "alerts": _ALERTS_ENABLED,
            }
        tmp = _STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, _STATE_FILE)
        return True
    except Exception:
        return False

def restore_state():
    """Load persisted state (does not auto-enable the worker)."""
    global _WATCH_SENS, _ALERTS_ENABLED
    try:
        if not os.path.exists(_STATE_FILE):
            return False
        with open(_STATE_FILE, "r") as f:
            data = json.load(f) or {}
        rules = data.get("rules") or []
        watch = data.get("watch") or {}
        sens = float(data.get("watch_sens", _WATCH_SENS))
        interval = int(data.get("interval", _STATE["interval"]))
        alerts = bool(data.get("alerts", True))
        with _LOCK:
            _RULES[:] = rules
            _WATCH.clear()
            for k,v in (watch.items()):
                _WATCH[k] = {"last": (v or {}).get("last")}
            _STATE["interval"] = max(3, interval)
            _STATE["ticks"] = 0
            _STATE["alive"] = bool(_STATE.get("thread_alive"))
            _WATCH_SENS = max(0.1, min(sens, 100.0))
            _ALERTS_ENABLED = alerts
        _log_event("[RESTORE] state loaded")
        return True
    except Exception:
        return False

# Alert toggle
def alerts_set(enabled:bool):
    global _ALERTS_ENABLED
    _ALERTS_ENABLED = bool(enabled)
    _save_state()
    return _ALERTS_ENABLED

# --------- public helpers for bot ---------
def events(n=10):
    n = max(1, min(int(n), 100))
    with _LOCK:
        return list(_EVENTS)[-n:]

def dryrun_eval(mint=None):
    """Run one DRY-RUN evaluation now for either a specific mint or all rules, return list of strings."""
    out = []
    with _LOCK:
        rules = [dict(r) for r in _RULES if (not mint or r.get("mint","").lower()==mint.lower())]
    if not rules:
        out.append("No matching rules.")
        return out
    # do a single-shot evaluation like the tick
    for r in rules:
        m = r["mint"]
        price, source = _get_price(m)
        if price is None: price, source = _sim_price(m), "sim"
        ref = float(r.get("ref") or price); peak=float(r.get("peak") or price)
        tp=_as_int(r.get("tp")); sl=_as_int(r.get("sl")); trail=_as_int(r.get("trail"))
        reason=None
        if sl is not None and price <= ref*(1-sl/100.0): reason=f"SL{sl}%"
        if tp is not None and price >= ref*(1+tp/100.0): reason=reason or f"TP{tp}%"
        if trail is not None and price <= peak*(1-trail/100.0): reason=reason or f"TRAIL{trail}%"
        if reason:
            out.append(f"[DRY] would SELL {m} @ {price:.6f} reason={reason} src={source} ref={ref:.6f} peak={peak:.6f}")
        else:
            out.append(f"[DRY] hold {m} price={price:.6f} src={source} ref={ref:.6f} peak={peak:.6f}")
    return out