import json
import threading

_CFG_PATH = "alerts_config.json"
_lock = threading.RLock()
_last_sent_ts = 0.0
_sent_this_min = 0
_sent_min_bucket = 0


def _as_float(x, default=0.0):
    try:
        if isinstance(x, str):
            x = x.strip().rstrip("%").strip()
        return float(x)
    except (TypeError, ValueError):
        return default


def _load_cfg() -> dict:
    try:
        with open(_CFG_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "chat_id": None,
            "min_move_pct": 1.0,
            "rate_per_min": 5,
            "muted_until": 0,
        }


def _should_rate_limit(now: float, rate_per_min: int) -> bool:
    global _sent_this_min, _sent_min_bucket
    minute = int(now // 60)
    if minute != _sent_min_bucket:
        _sent_min_bucket = minute
        _sent_this_min = 0
    if _sent_this_min >= max(1, int(rate_per_min)):
        return True
    _sent_this_min += 1
    return False


def format_price_alert(
    symbol: str, mint: str, price: float, move_pct: float, src: str, reason: str = "price_move"
) -> str:
    direction = "▲" if move_pct >= 0 else "▼"
    pct = f"{move_pct:+.2f}%"
    pstr = f"${price:,.6f}" if price < 1 else f"${price:,.4f}" if price < 10 else f"${price:,.2f}"
    return f"[ALERT] {symbol or mint} {direction}{pct} price={pstr} src={src} {('('+reason+')' if reason else '')}".strip()


def try_send_alert(text: str, preview: bool = False) -> bool:
    from app import alerts_send  # uses our new unified alert system

    res = alerts_send(text)
    return bool(res.get("ok"))


def emit_price_move(
    mint: str, symbol: str, price: float, move_pct: float, src: str, reason: str = ""
) -> bool:
    """Caller ensures move_pct is absolute threshold-eligible; we re-check settings here just in case."""
    cfg = _load_cfg()
    thresh = _as_float(cfg.get("min_move_pct", 1.0) or 1.0, 1.0)
    if abs(_as_float(move_pct, 0.0)) < thresh:
        return False
    msg = format_price_alert(symbol, mint, price, move_pct, src, reason)
    return try_send_alert(msg, preview=True)


def emit_info(text: str) -> bool:
    return try_send_alert(text, preview=True)
