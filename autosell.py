from __future__ import annotations
import threading, time, json, os
from collections import deque
from typing import Dict, Optional

# ---- state ----
STATE = {
    "enabled": False,
    "interval_sec": 10,
    "rules": {},                # mint -> {"tp":..,"sl":..,"trail":..,"ref":0.0,"peak":0.0}
    "events": deque(maxlen=200),
    "thread": None,
    "alive": False,
    "last_tick": 0.0,
}
LOCK = threading.RLock()
_PERSIST = "/tmp/autosell_rules.json"

def _log(msg: str):
    with LOCK:
        ts = time.strftime("%H:%M:%S")
        STATE["events"].append(f"{ts} {msg}")

def _persist():
    try:
        with LOCK:
            data = {"rules": STATE["rules"], "interval_sec": STATE["interval_sec"]}
        open(_PERSIST, "w").write(json.dumps(data))
    except Exception:
        pass

def _load():
    try:
        data = json.loads(open(_PERSIST).read())
        with LOCK:
            STATE["rules"] = data.get("rules", {})
            STATE["interval_sec"] = int(data.get("interval_sec", 10))
    except Exception:
        pass
_load()

def enable():
    with LOCK:
        STATE["enabled"] = True
    _ensure_thread()
    _log("AutoSell enabled.")
    return True

def disable():
    with LOCK:
        STATE["enabled"] = False
    _log("AutoSell disabled.")
    return True

def status() -> dict:
    with LOCK:
        return {
            "enabled": STATE["enabled"],
            "alive": STATE["alive"],
            "interval_sec": STATE["interval_sec"],
            "rules_count": len(STATE["rules"]),
            "last_tick_age": int(time.time() - STATE["last_tick"]) if STATE["last_tick"] else None,
        }

# --- API expected by router ---
def set_interval(seconds: int) -> int:
    seconds = max(3, int(seconds))
    with LOCK:
        STATE["interval_sec"] = seconds
    _persist()
    _log(f"[cfg] interval={seconds}s")
    return seconds

def set_rule(mint: str, tp: Optional[int]=None, sl: Optional[int]=None, trail: Optional[int]=None) -> dict:
    # All values optional; only update what's provided
    mint = mint.strip()
    with LOCK:
        rule = STATE["rules"].get(mint, {"tp": None, "sl": None, "trail": None, "ref": 0.0, "peak": 0.0})
        if tp is not None: rule["tp"] = int(tp)
        if sl is not None: rule["sl"] = int(sl)
        if trail is not None: rule["trail"] = int(trail)
        STATE["rules"][mint] = rule
    _persist()
    _log(f"[cfg] rule {mint} tp={rule['tp']} sl={rule['sl']} trail={rule['trail']}")
    return {"mint": mint, **STATE["rules"][mint]}

def rule_info(mint: str) -> str:
    with LOCK:
        r = STATE["rules"].get(mint)
    if not r:
        return "No such rule."
    return f"Rule info: {mint} tp={r['tp']} sl={r['sl']} trail={r['trail']} ref={r['ref']} peak={r['peak']}"

def dryrun_rule(mint: str) -> str:
    with LOCK:
        r = STATE["rules"].get(mint)
    if not r:
        return "No matching rules."
    # Mock evaluation line
    return f"[DRY] hold {mint} price=~{0.973:.6f} src=sim ref={r['ref']:.6f} peak={r['peak']:.6f}"

def get_logs(limit: int=10):
    with LOCK:
        items = list(STATE["events"])[-int(max(1,limit)):]
    return items or ["No events yet."]

def _ensure_thread():
    with LOCK:
        th = STATE.get("thread")
        if th and th.is_alive():
            return
        th = threading.Thread(target=_worker, daemon=True, name="autosell-worker")
        STATE["thread"] = th
        th.start()

def _worker():
    STATE["alive"] = True
    _log("[hb] worker started")
    try:
        while True:
            with LOCK:
                interval = STATE["interval_sec"]
                en = STATE["enabled"]
                STATE["last_tick"] = time.time()
            if en:
                _tick_evaluate_rules()
                _log("[tick] ok")
            time.sleep(interval)
    except Exception as e:
        _log(f"[err] worker {e!r}")
    finally:
        STATE["alive"] = False
        _log("[hb] worker stopped")

def _tick_evaluate_rules():
    """Evaluate all rules and emit price move alerts when thresholds are met"""
    from app import get_price
    
    with LOCK:
        rules = dict(STATE["rules"])
    
    for mint, rule in rules.items():
        try:
            # Get current price using the unified price system
            res = get_price(mint)
            if not res.get("ok"):
                continue
                
            price = res["price"]
            src = res["source"]
            
            # Calculate price change from reference
            ref_price = rule.get("ref", 0.0)
            if ref_price > 0:
                move_pct = ((price - ref_price) / ref_price) * 100.0
                
                # Try to emit alert for significant price moves
                try:
                    from alerts_glue import emit_price_move
                    # Get symbol from token metadata if available
                    symbol = mint[:8] + ".."  # fallback
                    emit_price_move(
                        mint=mint,
                        symbol=symbol,
                        price=price,
                        move_pct=move_pct,
                        src=src,
                        reason="autosell_tick"
                    )
                except Exception:
                    # Never crash autosell on alert failures
                    pass
                    
        except Exception as e:
            _log(f"[tick] error evaluating {mint}: {e}")
            continue