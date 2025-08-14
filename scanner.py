# scanner.py
import threading, time, json, os
from typing import List, Tuple

_LOCK = threading.RLock()
_STATE_PATH = "scanner_state.json"
_state = {
    "enabled": False,
    "interval_sec": 20,
    "threshold": 75,
    "seen_mints": [],
    "watchlist": [],
    "autobuy": {}  # mint -> {"sol": float, "enabled": bool}
}

_thread = None
_stop = False

def _load():
    if os.path.exists(_STATE_PATH):
        try:
            with open(_STATE_PATH) as f:
                _state.update(json.load(f))
        except Exception:
            pass

def _save():
    try:
        with open(_STATE_PATH, "w") as f:
            json.dump(_state, f)
    except Exception:
        pass

def enable():
    """Enable scanner and start loop thread if not running."""
    global _thread, _stop
    with _LOCK:
        _load()
        _state["enabled"] = True
        _save()
        if _thread is None or not _thread.is_alive():
            _stop = False
            _thread = threading.Thread(target=_loop, daemon=True)
            _thread.start()

def disable():
    """Disable scanner and request loop stop (thread exits on next tick)."""
    global _stop
    with _LOCK:
        _state["enabled"] = False
        _save()
        _stop = True

def set_threshold(v: int):
    with _LOCK:
        _state["threshold"] = int(v)
        _save()

def set_interval(seconds: int):
    with _LOCK:
        _state["interval_sec"] = max(5, int(seconds))
        _save()

def add_watch(mint: str) -> bool:
    with _LOCK:
        if mint in _state["watchlist"]: return False
        _state["watchlist"].append(mint); _save(); return True

def remove_watch(mint: str) -> bool:
    with _LOCK:
        if mint not in _state["watchlist"]: return False
        _state["watchlist"].remove(mint); _save(); return True

def get_watchlist() -> List[str]:
    with _LOCK:
        return list(_state["watchlist"])

def set_autobuy(mint: str, sol_amount: float, enabled: bool = True):
    """Set autobuy configuration for a mint."""
    with _LOCK:
        _load()
        if "autobuy" not in _state:
            _state["autobuy"] = {}
        _state["autobuy"][mint] = {"sol": float(sol_amount), "enabled": bool(enabled)}
        _save()

def remove_autobuy(mint: str) -> bool:
    """Remove autobuy configuration for a mint."""
    with _LOCK:
        _load()
        if "autobuy" not in _state:
            _state["autobuy"] = {}
        if mint not in _state["autobuy"]:
            return False
        del _state["autobuy"][mint]
        _save()
        return True

def get_autobuy_config() -> dict:
    """Get all autobuy configurations."""
    with _LOCK:
        _load()
        if "autobuy" not in _state:
            _state["autobuy"] = {}
        return dict(_state["autobuy"])

def toggle_autobuy(mint: str) -> bool:
    """Toggle autobuy enabled status for a mint. Returns new enabled status."""
    with _LOCK:
        _load()
        if "autobuy" not in _state:
            _state["autobuy"] = {}
        if mint not in _state["autobuy"]:
            return False
        _state["autobuy"][mint]["enabled"] = not _state["autobuy"][mint]["enabled"]
        _save()
        return _state["autobuy"][mint]["enabled"]

def clear_seen():
    with _LOCK:
        _state["seen_mints"] = []; _save()

def status() -> dict:
    with _LOCK:
        return {
            "enabled": _state["enabled"],
            "interval_sec": _state["interval_sec"],
            "threshold": _state["threshold"],
            "seen_count": len(_state["seen_mints"]),
            "watchlist": list(_state["watchlist"]),
            "thread_alive": (_thread is not None and _thread.is_alive()),
        }

# One-off scan used by /fetchnow
def scan_now(n: int) -> List[Tuple[dict,int,str]]:
    import token_fetcher, flip_checklist
    toks = token_fetcher.recent(n)             # list[dict]
    out = []
    for t in toks:
        s, v, _ = flip_checklist.score(t)
        out.append((t, s, v))
    out.sort(key=lambda x: x[1], reverse=True)
    return out

def _loop():
    import token_fetcher, flip_checklist
    from alerts.telegram import send_alert

    while not _stop:
        with _LOCK:
            enabled   = _state.get("enabled", False)
            interval  = int(_state.get("interval_sec", 20))
            threshold = int(_state.get("threshold", 75))
            seen      = set(_state.get("seen_mints", []))
            watch     = list(_state.get("watchlist", []))

        if enabled:
            try:
                # Pull recents
                toks = token_fetcher.recent(25)  # tune as needed

                # Force-fetch watchlist additions
                try:
                    extra = []
                    for m in watch:
                        try:
                            t = token_fetcher.lookup(m)
                            if t: extra.append(t)
                        except Exception:
                            pass
                    toks.extend(extra)
                except Exception:
                    pass

                # Score & alert
                winners = []
                autobuy_executions = []
                with _LOCK:
                    autobuy_config = dict(_state.get("autobuy", {}))
                
                for t in toks:
                    mint = t.get("mint")
                    if not mint or mint in seen:
                        continue
                    s, v, details = flip_checklist.score(t)
                    if s >= threshold:
                        winners.append((t, s, v, details))
                        seen.add(mint)
                        
                        # Check for autobuy
                        if mint in autobuy_config and autobuy_config[mint].get("enabled", False):
                            sol_amount = autobuy_config[mint].get("sol", 0)
                            if sol_amount > 0:
                                autobuy_executions.append((t, sol_amount, s, v))

                # Execute autobuy orders first
                if autobuy_executions:
                    try:
                        import trade_store, trade_engine
                        for token, sol_amount, score, verdict in autobuy_executions:
                            try:
                                mint = token.get("mint")
                                symbol = token.get("symbol", "TKN")
                                st = trade_store.get_state()
                                
                                # Safety check - respect max_sol cap
                                if sol_amount > st.get("max_sol", 0.5):
                                    send_alert(f"🚫 AUTOBUY BLOCKED: {symbol} ({mint[:8]}...)\nAmount {sol_amount} SOL exceeds cap {st.get('max_sol', 0.5)} SOL\nScore: {score} ({verdict})")
                                    continue
                                
                                # Execute the buy
                                if st.get("enabled_live", False):
                                    qty, px = trade_engine.execute_buy(mint, symbol, sol_amount, st.get("slippage_bps", 150))
                                    mode = "LIVE"
                                else:
                                    qty, px = trade_engine.preview_buy(mint, symbol, sol_amount, st.get("slippage_bps", 150))
                                    mode = "DRY-RUN"
                                
                                # Record the fill
                                trade_store.record_fill("BUY", mint, symbol, qty, px, sol_cost=sol_amount)
                                
                                # Send autobuy alert
                                send_alert(f"🤖 AUTOBUY EXECUTED ({mode})\n{symbol} ({mint[:8]}...)\nSize: {sol_amount} SOL → {qty:.4f} tokens\nPrice: {px:.8f} SOL/token\nScore: {score} ({verdict})")
                                
                            except Exception as e:
                                send_alert(f"⚠️ AUTOBUY ERROR: {token.get('symbol', '?')} ({mint[:8]}...)\nError: {e}")
                    except Exception as e:
                        send_alert(f"⚠️ Autobuy system error: {e}")

                if winners:
                    winners.sort(key=lambda x: x[1], reverse=True)
                    for t, s, v, details in winners[:5]:
                        msg = (
                            f"🚨 {v}  Score {s}\n"
                            f"{t.get('symbol','?')}  {t.get('mint','?')[:8]}...\n"
                            f"Price: {t.get('price','?')}  FDV: {t.get('fdv','?')}  LP: {t.get('lp','?')}\n"
                            f"Age: {t.get('age','?')}s  Holders: {t.get('holders','?')}\n"
                            f"{details}"
                        )
                        send_alert(msg)

                with _LOCK:
                    _state["seen_mints"] = list(seen)
                    _save()

            except Exception as e:
                print(f"[scanner] loop error: {e}")

        time.sleep(max(5, interval))