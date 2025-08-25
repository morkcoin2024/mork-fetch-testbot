# trade_store.py
import json
import os
import time
import uuid

_PATH = "trades_state.json"
_state = {
    "enabled_live": False,  # stays False until you flip it
    "max_sol": 1.0,  # per order safety cap
    "slippage_bps": 100,  # 1% default
    "positions": {},  # {mint: {"mint":..., "symbol":..., "qty": float, "avg_price": float, "last_update": ts}}
    "fills": [],  # list of {id, side, mint, symbol, qty, price, sol_cost, ts}
    "pending": {},  # {confirm_id: {"ts":..., "action":{...}}}
}


def _load():
    global _state
    if os.path.exists(_PATH):
        try:
            _state.update(json.load(open(_PATH)))
        except Exception:
            pass


def _save():
    json.dump(_state, open(_PATH, "w"))


def get_state() -> dict:
    _load()
    return _state


def set_live(enabled: bool):
    _load()
    _state["enabled_live"] = bool(enabled)
    _save()


def set_caps(max_sol: float = None, slippage_bps: int = None):
    _load()
    if max_sol is not None:
        _state["max_sol"] = float(max_sol)
    if slippage_bps is not None:
        _state["slippage_bps"] = int(slippage_bps)
    _save()


def add_pending(action: dict, ttl_sec=120) -> str:
    _load()
    cid = uuid.uuid4().hex[:8]
    _state["pending"][cid] = {"ts": time.time(), "action": action, "ttl": ttl_sec}
    _save()
    return cid


def pop_pending(cid: str):
    _load()
    rec = _state["pending"].pop(cid, None)
    _save()
    if not rec:
        return None
    if time.time() - rec["ts"] > rec.get("ttl", 120):
        return None
    return rec["action"]


def positions() -> dict[str, dict]:
    _load()
    return _state["positions"]


def get_all_positions() -> dict[str, dict]:
    """Alias for positions() for compatibility"""
    return positions()


def fills() -> list[dict]:
    _load()
    return list(_state["fills"])


def record_fill(side: str, mint: str, symbol: str, qty: float, price: float, sol_cost: float):
    _load()
    _state["fills"].append(
        {
            "id": uuid.uuid4().hex[:8],
            "side": side,
            "mint": mint,
            "symbol": symbol,
            "qty": float(qty),
            "price": float(price),
            "sol_cost": float(sol_cost),
            "ts": time.time(),
        }
    )
    # update position
    pos = _state["positions"].get(
        mint, {"mint": mint, "symbol": symbol, "qty": 0.0, "avg_price": 0.0, "last_update": 0}
    )
    if side == "BUY":
        new_qty = pos["qty"] + qty
        pos["avg_price"] = (
            ((pos["avg_price"] * pos["qty"]) + (price * qty)) / new_qty if new_qty > 0 else 0.0
        )
        pos["qty"] = new_qty
    else:  # SELL
        pos["qty"] = max(0.0, pos["qty"] - qty)
        if pos["qty"] == 0.0:
            pos["avg_price"] = 0.0
    pos["last_update"] = time.time()
    _state["positions"][mint] = pos
    _save()
