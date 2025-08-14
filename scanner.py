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

def autobuy_set(mint: str, sol: float):
    with _LOCK:
        _load()
        _state["autobuy"][mint] = {"sol": float(sol), "enabled": True}
        _save()
        return True

def autobuy_on(mint: str):
    with _LOCK:
        _load()
        if mint not in _state["autobuy"]: return False
        _state["autobuy"][mint]["enabled"] = True
        _save()
        return True

def autobuy_off(mint: str):
    with _LOCK:
        _load()
        if mint not in _state["autobuy"]: return False
        _state["autobuy"][mint]["enabled"] = False
        _save()
        return True

def autobuy_remove(mint: str):
    with _LOCK:
        _load()
        if _state["autobuy"].pop(mint, None) is None: return False
        _save()
        return True

def autobuy_list():
    with _LOCK:
        _load()
        return dict(_state["autobuy"])

def set_quick_buy_sol(x: float):
    _load(); _state["quick_buy_sol"] = float(x); _save()

def get_quick_buy_sol() -> float:
    _load(); return float(_state.get("quick_buy_sol", 0.1))

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
                for t in toks:
                    mint = t.get("mint")
                    if not mint or mint in seen:
                        continue
                    s, v, details = flip_checklist.score(t)
                    if s >= threshold:
                        winners.append((t, s, v, details))
                        seen.add(mint)

                if winners:
                    from trade_store import get_state as trade_state, record_fill
                    import trade_engine

                    winners.sort(key=lambda x: x[1], reverse=True)
                    for t, s, v, details in winners[:5]:
                        mint = t.get('mint','?')
                        symbol = t.get('symbol','?')
                        price = t.get('price','?')
                        fdv   = t.get('fdv','?')
                        lp    = t.get('lp','?')
                        age   = t.get('age','?')
                        holders = t.get('holders','?')

                        # One-tap command suggestions
                        quick_buy_sol = get_quick_buy_sol()  # configurable default
                        actions = f"/buy {mint} {quick_buy_sol}   /watch {mint}   /fetch {mint}"

                        msg = (
                            f"🚨 {v}  Score {s}\n"
                            f"{symbol}  {mint[:8]}...\n"
                            f"Price: {price}  FDV: {fdv}  LP: {lp}\n"
                            f"Age: {age}s  Holders: {holders}\n"
                            f"{details}\n"
                            f"— Quick actions —\n{actions}"
                        )
                        send_alert(msg)

                        # AutoBuy (best-effort, respects caps + live flag). Runs once because we add to 'seen'.
                        try:
                            auto = _state.get("autobuy", {}).get(mint)
                            if auto and auto.get("enabled", False):
                                st = trade_state()
                                sol_amt = float(auto.get("sol", 0))
                                # hard safety: respect global cap
                                if sol_amt > 0 and sol_amt <= float(st.get("max_sol", 1.0)):
                                    if st.get("enabled_live", False):
                                        qty, px = trade_engine.execute_buy(mint, symbol, sol_amt, int(st.get("slippage_bps", 100)))
                                        mode = "LIVE"
                                    else:
                                        qty, px = trade_engine.preview_buy(mint, symbol, sol_amt, int(st.get("slippage_bps", 100)))
                                        mode = "DRY-RUN"
                                    record_fill("BUY", mint, symbol, qty, px, sol_amt)
                                    send_alert(f"🤖 AutoBuy {mode}\n{symbol} {mint[:8]}...\nSize: {sol_amt} SOL  Qty: {qty:.4f}  Px: {px:.8f}")
                                else:
                                    send_alert(f"⚠️ AutoBuy skipped for {mint[:8]}… (size {sol_amt} exceeds cap {st.get('max_sol')})")
                        except Exception as e:
                            send_alert(f"⚠️ AutoBuy error for {mint[:8]}…: {e}")

                with _LOCK:
                    _state["seen_mints"] = list(seen)
                    _save()

            except Exception as e:
                print(f"[scanner] loop error: {e}")

        time.sleep(max(5, interval))