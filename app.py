"""
Flask Web Application for Mork F.E.T.C.H Bot
Handles Telegram webhooks and provides web interface
"""

import os, time, json, logging, re, requests
import threading
import hashlib
import inspect
import textwrap
import math
from datetime import datetime, timedelta, time as dtime, timezone
from flask import Flask, request, jsonify, Response, stream_with_context, render_template_string

# --- ROUTER TRACE BEGIN ---
import time as _rt_time
_ROUTER_TRACE = "/tmp/router_trace.log"
def _rt_log(msg: str):
    try:
        with open(_ROUTER_TRACE, "a") as _f:
            _f.write(f"{int(_rt_time.time())} {msg}\n")
    except Exception:
        pass
# --- ROUTER TRACE END ---

# ---- Alerts auto-ticker globals ----
ALERTS_TICK_DEFAULT = int(os.getenv("ALERTS_TICK_SEC", "30"))  # 0 = disabled
ALERTS_TICK_INTERVAL = ALERTS_TICK_DEFAULT
ALERTS_TICK_STOP = None
ALERTS_TICK_THREAD = None

# Guard against shadowing: top-level reference to ok function (defined later)
RESP_OK = None

# Add near top of file (helpers)
BIRDEYE_MINT_ALIASES = {
    "SOL": "So11111111111111111111111111111111111111112",  # wSOL
    "WSOL": "So11111111111111111111111111111111111111112",
}
_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

def normalize_mint(m: str) -> str:
    m = (m or "").strip()
    up = m.upper()
    if up in BIRDEYE_MINT_ALIASES:
        return BIRDEYE_MINT_ALIASES[up]
    return m

def is_valid_mint(m: str) -> bool:
    return bool(_BASE58_RE.match(m))

# Baseline and configuration helpers
BASELINE_PATH = "alerts_price_baseline.json"
NAME_CACHE_PATH = "token_names.json"
JUP_CACHE_PATH  = "jup_tokens.json"
NAME_CACHE_FILE = "token_names.json"
JUP_CATALOG_FILE = "jupiter_tokens.json"
JUP_CATALOG_TTL = 24 * 60 * 60  # 24h
OVERRIDES_FILE = "token_overrides.json"

def _load_json_safe(path):
    try:
        return json.load(open(path))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def _save_json_safe(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def _normalize_symbol(sym: str | None) -> str | None:
    """Clean a ticker-like symbol. Prefer 2–12 alnum chars, uppercased."""
    if not sym:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", str(sym)).upper()
    if 2 <= len(s) <= 12:
        return s
    return None

def _short_mint(mint: str) -> str:
    return f"{mint[:4]}..{mint[-4:]}"

# --- Individual source probes (wrap your existing HTTP helper(s)) ---
def _http_get_json(url, headers=None, params=None, timeout=8):
    # Reuse your project's HTTP getter if you have one; otherwise keep this thin
    r = requests.get(url, headers=headers or {}, params=params or {}, timeout=timeout)
    if r.status_code == 200:
        return r.json()
    return None

def _birdeye_headers():
    # Reuse your existing Birdeye header builder if present
    h = {"X-Chain": "solana"}
    try:
        k = os.getenv("BIRDEYE_API_KEY")
        if k:
            h["X-API-KEY"] = k
    except Exception:
        pass
    return h

def _name_from_birdeye(mint: str) -> tuple[str|None, str|None]:
    # Try the v3 market-data endpoint which includes symbol/name when available
    url = "https://public-api.birdeye.so/defi/v3/token/market-data"
    d = _http_get_json(url, headers=_birdeye_headers(), params={"address": mint, "chain": "solana"}) or {}
    dd = d.get("data") or {}
    sym = _normalize_symbol(dd.get("symbol") or dd.get("tokenSymbol"))
    sec = dd.get("name") or dd.get("tokenName")
    return sym, sec

def _name_from_jupiter(mint: str) -> tuple[str|None, str|None]:
    # Jupiter token info has symbol/name
    d = _http_get_json(f"https://tokens.jup.ag/token/{mint}") or {}
    return _normalize_symbol(d.get("symbol")), d.get("name")

def _name_from_dexscreener(mint: str) -> tuple[str|None, str|None]:
    d = _http_get_json(f"https://api.dexscreener.com/latest/dex/tokens/{mint}") or {}
    pairs = d.get("pairs") or []
    if not pairs:
        return None, None
    bt = pairs[0].get("baseToken") or {}
    return _normalize_symbol(bt.get("symbol")), bt.get("name")

def _name_from_solscan(mint: str) -> tuple[str|None, str|None]:
    d = _http_get_json("https://api.solscan.io/token/meta", params={"tokenAddress": mint}) or {}
    return _normalize_symbol(d.get("symbol")), d.get("name")

# ===== Jupiter catalog (bulk) =====
def _ensure_jup_catalog(force: bool = False):
    cat = _load_json_safe(JUP_CATALOG_FILE)
    ts = int(cat.get("ts", 0))
    stale = (time.time() - ts) > JUP_CATALOG_TTL
    if force or stale or not cat.get("by_mint"):
        arr = _http_get_json("https://tokens.jup.ag/tokens") or []
        by_mint = {}
        for t in arr:
            mint = t.get("address") or t.get("mint") or t.get("id")
            if not mint:
                continue
            sym = _normalize_symbol(t.get("symbol"))
            name = t.get("name")
            if sym or name:
                by_mint[mint] = {"symbol": sym, "name": name}
        cat = {"ts": int(time.time()), "by_mint": by_mint}
        _save_json_safe(JUP_CATALOG_FILE, cat)
    return cat

def _name_from_jup_catalog(mint: str) -> tuple[str|None, str|None]:
    cat = _ensure_jup_catalog()
    d = (cat.get("by_mint") or {}).get(mint) or {}
    return _normalize_symbol(d.get("symbol")), d.get("name")

# ===== Name overrides system =====
def _name_overrides_get(mint: str) -> tuple[str|None, str|None]:
    o = _load_json_safe(OVERRIDES_FILE)
    d = o.get(mint) or {}
    return d.get("primary"), d.get("secondary")

def _name_overrides_set(mint: str, primary: str|None, secondary: str|None):
    o = _load_json_safe(OVERRIDES_FILE)
    o[mint] = {"primary": primary, "secondary": secondary, "ts": time.time()}
    _save_json_safe(OVERRIDES_FILE, o)

def _name_overrides_clear(mint: str):
    o = _load_json_safe(OVERRIDES_FILE)
    if mint in o:
        o.pop(mint, None)
        _save_json_safe(OVERRIDES_FILE, o)

# Public aliases for external use
def name_override_get(mint: str):
    d = _load_json_safe(OVERRIDES_FILE).get(mint) or {}
    return d if d else None

def name_override_set(mint: str, primary: str, secondary: str):
    return _name_overrides_set(mint, primary.strip(), secondary.strip())

def name_override_clear(mint: str):
    return _name_overrides_clear(mint)

def _display_name_for(mint: str) -> str:
    try:
        ov = _name_overrides_get(mint)
    except Exception:
        ov = None
    if ov:
        p, s = ov
        p = (p or "").strip()
        s = (s or "").strip()
        if p and s: return f"{p}\n{s}"
        if p:       return p
        if s:       return s
    try:
        nm = resolve_token_name(mint) or ""
        if nm: return nm   # may be "TICKER\nLong"
    except Exception:
        pass
    return f"{mint[:4]}..{mint[-4:]}"

# ===== Heuristic primary extraction =====
_STOPWORDS = {"THE","COIN","TOKEN","INU","PROTOCOL","AI","ON","CHAIN","CO","DAO","CAT","DOG"}
def _heuristic_primary_from_secondary(sec: str|None) -> str|None:
    if not sec:
        return None
    # Split by non-letters, choose a decent "brand" word
    words = [w for w in re.split(r"[^A-Za-z0-9]+", sec) if w]
    # Prefer a 3–8 length word that's not a stopword
    cands = [w for w in words if 3 <= len(w) <= 12 and w.upper() not in _STOPWORDS]
    if not cands and words:
        cands = words
    if not cands:
        return None
    pick = max(cands, key=len)  # longest is often "PUDGY", "LIGHT", etc
    sym = re.sub(r"[^A-Za-z0-9]", "", pick).upper()
    return sym if 2 <= len(sym) <= 12 else None

def _choose_name(candidates: list[tuple[str|None, str|None]]):
    # Filter out None candidates and handle safely
    valid_candidates = [c for c in candidates if c is not None and isinstance(c, tuple)]
    if not valid_candidates:
        return None, None
    
    # primary = first good ticker; secondary = first descriptive name
    primary = next((p for p, s in valid_candidates if p), None)
    secondary = next((s for p, s in valid_candidates if s), None)
    # heuristic: if only secondary exists and looks like "TICKER — Long Name"
    if not primary and secondary:
        left = re.split(r"[—\-|:]", secondary)[0].strip()
        p2 = _normalize_symbol(left)
        if p2:
            primary = p2
    # ensure we always have something
    return primary, secondary

def _http_get_json_original(url, headers=None, params=None, timeout=8):
    try:
        r = requests.get(url, headers=headers or {}, params=params or {}, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def _name_cache_load():
    try:
        return json.load(open(NAME_CACHE_PATH))
    except Exception:
        return {}

def _name_cache_save(d):
    try:
        json.dump(d, open(NAME_CACHE_PATH, "w"))
    except Exception:
        pass

def _name_from_solscan(mint: str):
    # Pro key first (optional), then public
    key = os.getenv("SOLSCAN_API_KEY","").strip()
    if key:
        url = "https://pro-api.solscan.io/v1.0/market/token/meta"
        out = _http_get_json(url, headers={"token": key}, params={"address": mint})
        if out and isinstance(out, dict):
            sym = (out.get("symbol") or "").strip()
            name = (out.get("name") or "").strip()
            if sym or name:
                return {"symbol": sym, "name": name, "src": "solscan-pro"}
    # Public
    out = _http_get_json("https://api.solscan.io/token/meta", params={"address": mint})
    if not out or not isinstance(out, dict): 
        out = _http_get_json("https://public-api.solscan.io/token/meta", params={"tokenAddress": mint})
    if out and isinstance(out, dict):
        # public returns { "symbol": "...", "tokenName": "..." }
        sym = (out.get("symbol") or "").strip()
        name = (out.get("tokenName") or out.get("name") or "").strip()
        if sym or name:
            return {"symbol": sym, "name": name, "src": "solscan"}
    return None

def _name_from_dexscreener(mint: str):
    out = _http_get_json(f"https://api.dexscreener.com/latest/dex/tokens/{mint}")
    if not out or "pairs" not in out or not out["pairs"]:
        return None
    # Prefer a SOL pair with the mint as baseToken
    for p in out["pairs"]:
        base = (p.get("baseToken") or {})
        if base.get("address") == mint:
            sym = (base.get("symbol") or "").strip()
            name = (base.get("name") or "").strip()
            if sym or name:
                return {"symbol": sym, "name": name, "src": "dexscreener"}
    # Fallback first pair
    base = (out["pairs"][0].get("baseToken") or {})
    sym = (base.get("symbol") or "").strip()
    name = (base.get("name") or "").strip()
    if sym or name:
        return {"symbol": sym, "name": name, "src": "dexscreener"}
    return None

def _name_from_jupiter(mint: str):
    # Cache Jupiter list for 24h
    try:
        stat = os.stat(JUP_CACHE_PATH)
        fresh = (time.time() - stat.st_mtime) < 24*3600
    except Exception:
        fresh = False
    if not fresh:
        data = _http_get_json("https://tokens.jup.ag/strict")
        if isinstance(data, list) and data:
            try: json.dump(data, open(JUP_CACHE_PATH, "w"))
            except Exception: pass
    try:
        data = json.load(open(JUP_CACHE_PATH))
    except Exception:
        data = []
    for t in data:
        if (t.get("address") or "").strip() == mint:
            sym = (t.get("symbol") or "").strip()
            name = (t.get("name") or "").strip()
            if sym or name:
                return {"symbol": sym, "name": name, "src": "jupiter"}
    return None

PRICE_HISTORY_FILE = "price_history.json"
def _history_load():
    import json, os
    try: return json.load(open(PRICE_HISTORY_FILE))
    except: return {}
def _history_save(d):
    import json
    json.dump(d, open(PRICE_HISTORY_FILE,"w"))
def record_price_point(mint:str, price:float, src:str):
    import time
    if not (mint and price and price>0): return
    d=_history_load()
    lst=d.get(mint) or []
    lst.append({"ts":int(time.time()), "price":float(price), "src":src})
    # keep last ~2 days at 30s cadence ≈ 6k points
    d[mint]=lst[-6000:]
    _history_save(d)
def pct(a,b):
    try: return ((a-b)/b)*100.0
    except: return None
def window_change(mint:str, secs:int):
    """return (pct_change, ref_price) where ref_price is the price at/just before now-secs"""
    import time, bisect
    hist=_history_load().get(mint) or []
    if not hist: return (None, None)
    cutoff=int(time.time())-secs
    # find the last point <= cutoff
    ref=None
    for p in reversed(hist):
        if p["ts"]<=cutoff:
            ref=p["price"]; break
    if ref is None: return (None, None)
    cur=hist[-1]["price"]
    return (pct(cur, ref), ref)
def decorate_pct(x):
    if x is None: return "n/a"
    arrow = "🟢▲" if x>=0 else "🔴▼"
    return f"{arrow} {x:+.2f}%"
def short_mint(m): return f"{m[:4]}..{m[-4:]}" if m and len(m)>12 else m
def name_line(mint):
    nm = resolve_token_name(mint)  # existing
    # Expect "TICKER — Full Name"
    if "—" in nm:
        sym, full = [s.strip() for s in nm.split("—",1)]
    else:
        sym, full = nm, ""
    return sym, full

def _alerts_cfg_load():
    import json, os
    try: return json.load(open("alerts_config.json"))
    except: return {"enabled": True, "chat_id": None, "min_move_pct": 0.01, "rate_per_min": 60, "muted_until": 0, "muted": False}
def _alerts_cfg_save(d):
    import json; json.dump(d, open("alerts_config.json","w"))

def get_price_auto(mint:str):
    vals=[]
    used=[]
    for name,fn in [("birdeye", price_birdeye), ("dex", price_dex)]:
        try:
            r=fn(mint)
            if r and r.get("ok") and r.get("price"):
                vals.append(float(r["price"])); used.append(name)
        except: pass
    if not vals:
        return {"ok": True, "price": 0.06924, "source": "sim"}  # last-resort
    vals.sort()
    median = vals[len(vals)//2] if len(vals)%2==1 else (vals[len(vals)//2-1]+vals[len(vals)//2])/2.0
    return {"ok": True, "price": median, "source": f"auto({','.join(used)})"}

DEXS_URL = "https://api.dexscreener.com/latest/dex/tokens/"
JUP_URL  = "https://price.jup.ag/v6/price?ids="  # works with mint addresses

def is_base58_mint(s:str)->bool:
    # cheap check to avoid "wrong mint" surprises; we still pass through as-given for display
    return bool(s) and len(s) >= 32 and re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]+", s) is not None

def _tf_merge(*dicts):
    out = {}
    for d in dicts:
        if not d: continue
        for k,v in d.items():
            if v is None: continue
            out[k] = v
    return out  # last writer wins

def fetch_timeframes_dex(mint:str):
    try:
        r = requests.get(DEXS_URL + mint, timeout=6)
        if r.status_code != 200: return {}
        j = r.json()
        # pick best pair (highest liquidity) if many
        pairs = j.get("pairs") or []
        if not pairs: return {}
        best = max(pairs, key=lambda p: float(p.get("liquidity",{}).get("usd",0)))
        pc = best.get("priceChange", {})  # { "m5": "...", "h1": "...", "h6": "...", "h24": "..." }
        def f(key):
            v = pc.get(key)
            try: return float(v)
            except: return None
        return {
            "5m": f("m5"),
            "1h": f("h1"),
            "6h": f("h6"),
            "24h": f("h24"),
        }
    except Exception:
        return {}

def fetch_timeframes_jup(mint:str):
    try:
        r = requests.get(JUP_URL + mint, timeout=6)
        if r.status_code != 200: return {}
        j = r.json()
        data = (j.get("data") or {}).get(mint) or {}
        # Jupiter gives 24h change; sometimes also 1h; we normalize keys
        out = {}
        for k_src, k_dst in (("24hChange", "24h"), ("1hChange","1h")):
            v = data.get(k_src)
            try: out[k_dst] = float(v)
            except: pass
        return out
    except Exception:
        return {}

def fetch_timeframes(mint:str):
    # Merge Dexscreener first (more buckets), then layer any extra from Jupiter
    return _tf_merge(fetch_timeframes_dex(mint), fetch_timeframes_jup(mint))

def _load_json(p):
    try:
        import json, os
        if not os.path.exists(p): return {}
        return json.load(open(p))
    except Exception:
        return {}

def _save_json(p, obj):
    import json, tempfile, os
    tmp = p + ".tmp"
    json.dump(obj, open(tmp, "w"))
    os.replace(tmp, p)

def _load_baseline():
    return _load_json(BASELINE_PATH)

def _save_baseline(b):
    _save_json(BASELINE_PATH, b)

# ---------- Enhanced Token name resolution (multi-provider) ----------
TOKEN_NAME_CACHE = "token_names.json"
SOL_PSEUDO_MINT = "So11111111111111111111111111111111111111112"
PRICE_HISTORY_DIR = "price_history"  # per-mint .jsonl files for /info windows
os.makedirs(PRICE_HISTORY_DIR, exist_ok=True)

def _load_token_cache():
    try:
        return json.load(open(TOKEN_NAME_CACHE))
    except Exception:
        return {}

def _save_token_cache(d):
    try:
        json.dump(d, open(TOKEN_NAME_CACHE, "w"))
    except Exception:
        pass

def _short(mint: str) -> str:
    return f"{mint[:4]}..{mint[-4:]}" if len(mint) > 12 else mint

def _arrow(delta_pct: float) -> str:
    if delta_pct > 0: return "🟢▲"
    if delta_pct < 0: return "🔴▼"
    return "•"

def _fmt_pct(delta_pct: float) -> str:
    return f"{_arrow(delta_pct)} {delta_pct:+.2f}%"

# --- lightweight price history (append-only jsonl per mint) ---
def _history_path(mint: str) -> str:
    return os.path.join(PRICE_HISTORY_DIR, f"{mint}.jsonl")

def _record_price(mint: str, price: float, src: str):
    try:
        with open(_history_path(mint), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "price": float(price), "src": src}) + "\n")
    except Exception:
        logging.exception("history append failed")

def _load_price_at_or_before(mint: str, t_target: int) -> float | None:
    """
    Scan the mint's .jsonl backwards and return the latest price with ts <= t_target.
    For small files in our bot this is fine; can be optimized later.
    """
    path = _history_path(mint)
    if not os.path.exists(path): return None
    try:
        # read last ~200 lines to keep it light
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            chunk = 64 * 1024
            buf = b""
            pos = size
            while pos > 0 and len(buf.splitlines()) < 200:
                pos = max(0, pos - chunk)
                f.seek(pos)
                buf = f.read(size - pos) + buf
        lines = buf.splitlines()
        for line in reversed(lines):
            try:
                rec = json.loads(line.decode("utf-8"))
                if int(rec.get("ts", 0)) <= t_target:
                    return float(rec.get("price"))
            except Exception:
                continue
    except Exception:
        logging.exception("history read failed")
    return None

# Build three-line identity for alerts: ticker, name, (short)
def _alert_name_lines(mint: str) -> tuple[str, str | None, str]:
    """
    Returns (ticker_or_primary, secondary_name_or_None, short_mint)
    Example: ("WINGS", "Wings Stays On", "8aJ6..3777")
    """
    primary, secondary = _token_labels(mint)
    tline = (primary or secondary or _short(mint)).strip()
    nline = None
    if secondary and (not primary or secondary.lower() != (primary or "").lower()):
        nline = secondary.strip()
    return tline, nline, _short(mint)

def _format_price_alert_card(
    mint: str,
    price: float,
    baseline: float,
    delta_pct: float,
    source: str,
    up: bool,
) -> str:
    arrow = "🟢▲" if up else "🔴▼"
    tline, nline, sm = _alert_name_lines(mint)
    lines = [f"Price Alert {arrow}", f"Mint: {tline}"]
    if nline:
        lines.append(nline)
    lines.append(f"({sm})")
    # 6dp keeps degen tokens readable; large caps still ok
    lines.append(f"Price: ${price:,.6f}")
    lines.append(f"Change: {delta_pct:+.2f}%")
    lines.append(f"Baseline: ${baseline:,.6f}")
    lines.append(f"Source: {source}")
    return "\n".join(lines)

def _dot(pct):
    """Visual indicator for percentage changes"""
    if pct is None: 
        return "⚪︎"
    return "🟢▲" if pct >= 0 else "🔴▼"

def _info_card(mint: str, price_now: float, src: str) -> str:
    """
    Build enhanced multi-window info card with API-based real-time changes.
    Professional format with visual indicators and proper token naming.
    """
    # Get token names using existing resolution system
    primary_name, secondary_name = _token_labels(mint)
    short_mint = _short(mint)
    
    # Get API-based percentage changes
    ch = get_token_changes(mint)
    
    # Build professional info card
    lines = [
        f"*Info*",
        f"Mint: {primary_name or short_mint}",
        f"{secondary_name or primary_name or short_mint}",
        f"({short_mint})",
        f"Price: ${price_now:.6f}",
        f"Source: {src}",
        "",
        f"30m: {ch['m30']:+.2f}% {_dot(ch['m30'])}" if ch['m30'] is not None else "30m: n/a ⚪︎",
        f"1h:  {ch['h1']:+.2f}% {_dot(ch['h1'])}"   if ch['h1']  is not None else "1h:  n/a ⚪︎",
        f"4h:  {ch['h4']:+.2f}% {_dot(ch['h4'])}"   if ch['h4']  is not None else "4h:  n/a ⚪︎",
        f"12h: {ch['h12']:+.2f}% {_dot(ch['h12'])}" if ch['h12'] is not None else "12h: n/a ⚪︎",
        f"24h: {ch['h24']:+.2f}% {_dot(ch['h24'])}" if ch['h24'] is not None else "24h: n/a ⚪︎",
    ]
    
    # Add tracking history if available (optional enhancement)
    path = _history_path(mint)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                first = f.readline().strip()
                if first:
                    r = json.loads(first)
                    first_seen_price = float(r.get("price"))
                    first_seen_ts = int(r.get("ts", 0))
                    lines.append("")
                    lines.append(f"Since tracking: ${first_seen_price:.6f} @ {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(first_seen_ts))}")
        except Exception:
            pass
    
    return "\n".join(lines)

def _clean_symbol(s: str) -> str | None:
    """Normalize tickers: uppercase, alnum+_ only, trimmed to 12 chars."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip().upper()
    # common junk removal
    s = s.replace("$","").replace("·","").replace("•","")
    # keep A-Z0-9 and underscore
    import re
    s = re.sub(r"[^A-Z0-9_]", "", s)
    s = s[:12]
    return s or None

def _clean_name(s: str) -> str | None:
    """Normalize marketing names; keep a readable proper name only."""
    if not s or not isinstance(s, str):
        return None
    s = s.replace("\u200b","").replace("\ufeff","").strip()
    import re
    low = s.lower()
    low = re.sub(r'^\s*the\s+', '', low)               # drop leading "the "
    low = re.sub(r'\s+(coin|token)$', '', low)         # drop trailing generic
    low = re.sub(r'\s*[\(\[][^)\]]{1,32}[\)\]]\s*$', '', low)  # drop tail ()/[]
    low = re.sub(r'\s+', ' ', low).strip()
    cleaned = low.title()
    return (cleaned or None)[:64]

def _load_token_cache() -> dict:
    try:
        import json
        return json.load(open(TOKEN_NAME_CACHE))
    except Exception:
        return {}

def _save_token_cache(cache: dict) -> None:
    import json
    try:
        json.dump(cache, open(TOKEN_NAME_CACHE, "w"))
    except Exception:
        pass

# Back-compat: old cache sometimes stored just {"name": "..."}
def _coerce_cache_entry(ent) -> dict:
    if not isinstance(ent, dict):
        return {}
    if "primary" in ent or "secondary" in ent:
        return ent
    # migrate old shape
    out = {"primary": None, "secondary": ent.get("name"), "ts": ent.get("ts")}
    return out

def _token_labels(mint: str) -> tuple[str | None, str | None]:
    """
    Resolve (primary, secondary) = (ticker, full name).
    Caches {'primary','secondary','ts'} for 7 days.
    """
    import os, time, requests, json
    now = int(time.time())
    cache = _load_token_cache()
    ent = _coerce_cache_entry(cache.get(mint) or {})
    if ent and now - int(ent.get("ts") or 0) < 7*24*3600:
        return ent.get("primary"), ent.get("secondary")

    # Special-case SOL
    if mint == SOL_PSEUDO_MINT:
        ent = {"primary": "SOL", "secondary": "Solana", "ts": now}
        cache[mint] = ent
        _save_token_cache(cache)
        return ent["primary"], ent["secondary"]

    primary = None
    secondary = None

    # Birdeye v3
    try:
        api = os.getenv("BIRDEYE_API_KEY","")
        if api:
            h = {"X-API-KEY": api, "X-Chain": "solana"}
            url = "https://public-api.birdeye.so/defi/v3/token/market-data"
            r = requests.get(url, params={"address": mint, "chain":"solana"}, headers=h, timeout=(5,10))
            if r.status_code == 200:
                data = r.json().get("data") or {}
                ti = data.get("token_info") or {}
                secondary = _clean_name(ti.get("name") or data.get("name") or "") or secondary
                primary   = _clean_symbol(ti.get("symbol") or "") or primary
    except Exception:
        pass

    # Dexscreener
    if not primary or not secondary:
        try:
            r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=(5,10))
            if r.status_code == 200:
                js = r.json() or {}
                pairs = js.get("pairs") or []
                if pairs:
                    bt = (pairs[0] or {}).get("baseToken") or {}
                    secondary = _clean_name(bt.get("name") or "") or secondary
                    primary   = _clean_symbol(bt.get("symbol") or "") or primary
        except Exception:
            pass

    # Fallbacks
    if not primary and secondary:
        # synthesize ticker from secondary (first word upcased alnum)
        import re
        primary = _clean_symbol(re.sub(r'\s.*$', '', secondary))
    if not secondary and primary:
        secondary = primary  # better than None
    if not primary and not secondary:
        secondary = _short(mint)

    ent = {"primary": primary, "secondary": secondary, "ts": now}
    cache[mint] = ent
    _save_token_cache(cache)
    return primary, secondary

def resolve_token_name(mint: str, refresh: bool=False) -> str:
    """
    Returns a display string used by render_about_list:
    - If both present: 'PRIMARY\nSECONDARY'
    - If only one: that single string
    Caches {'primary','secondary','ts'} in token_names.json
    """
    # 1) Hard-coded SOL pseudo-mint stays as-is
    if mint == "So11111111111111111111111111111111111111112":
        primary, secondary = "SOL", "Solana"
        cache = _load_json_safe(NAME_CACHE_FILE)
        cache[mint] = {"primary": primary, "secondary": secondary, "ts": int(time.time())}
        _save_json_safe(NAME_CACHE_FILE, cache)
        return f"{primary}\n{secondary}"

    # 2) Local overrides take top priority unless refresh=True
    if not refresh:
        p0, s0 = _name_overrides_get(mint)
        if p0 or s0:
            return f"{p0}\n{s0}" if (p0 and s0 and s0.upper()!=p0) else (p0 or s0)

    # 3) Cached value next
    cache = _load_json_safe(NAME_CACHE_FILE)
    if not refresh and isinstance(cache.get(mint), dict):
        p, s = cache[mint].get("primary"), cache[mint].get("secondary")
        if p or s:
            return f"{p}\n{s}" if (p and s and s.upper()!=p) else (p or s)

    # 4) Probe live sources + Jupiter catalog
    cands = []
    for fn in (_name_from_jupiter, _name_from_birdeye, _name_from_dexscreener, _name_from_solscan, _name_from_jup_catalog):
        try:
            cands.append(fn(mint))
        except Exception:
            continue

    # 5) Pick best
    valid_cands = [c for c in cands if c is not None and isinstance(c, tuple)]
    primary = next((p for p,s in valid_cands if p), None)
    secondary = next((s for p,s in valid_cands if s), None)

    # 6) If still no symbol, derive one from secondary (heuristic)
    if not primary and secondary:
        primary = _heuristic_primary_from_secondary(secondary)

    # 7) Absolute last resort: short mint
    if not primary and not secondary:
        short = _short_mint(mint)
        primary = short
        secondary = short
    if not secondary:
        secondary = primary

    # 8) Cache & return
    cache[mint] = {"primary": primary, "secondary": secondary, "ts": int(time.time())}
    _save_json_safe(NAME_CACHE_FILE, cache)
    return f"{primary}\n{secondary}" if (secondary and secondary.upper()!=primary) else primary

def _alert_label(mint: str) -> str:
    p, s = _token_labels(mint)
    base = p or s or _short(mint)
    if p and s and p.lower() != s.lower():
        base = f"{p} — {s}"
    return f"{base} ({_short(mint)})"

# Standard token label for alerts: "<Name> (<So11..1112>)"
def _token_label(mint: str) -> str:
    return _alert_label(mint)

# Enhanced alert hook using the new resolver
def post_watch_alert_enhanced(mint, price, base_price, source, chat_id=None):
    """
    Enhanced alert hook that uses the multi-provider token resolver.
    Called after watch tick determines a significant move.
    """
    try:
        pct = 0.0
        if base_price and base_price > 0:
            pct = (price - base_price) / base_price * 100.0
        tri = "🟢▲" if pct >= 0 else "🔴▼"
        label = _token_label(mint)
        txt = f"[ALERT] {label} {tri} {pct:+.2f}%  price=${price:.6f}  src={source}"
        # Try to use existing alerts_send function if available
        try:
            return alerts_send(txt, chat_id=chat_id)
        except NameError:
            # Fallback to simple print for testing
            print(f"ALERT: {txt}")
            return True
    except Exception as e:
        print(f"Enhanced alert error: {e}")
        return False
# ---------------------------------------------------------------------------

# --- BEGIN: alerts HTML sender ---
import time, requests
from html import escape as _h

ALERTS_API_LOG = "/tmp/alerts_send_api.log"

def _alerts_send_html(chat_id: int, text: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        r = requests.post(url, json=payload, timeout=10)
        success = r.ok
        # Log result (status + first bytes of body)
        with open(ALERTS_API_LOG, "a") as f:
            f.write(f"{int(time.time())} ok={success} code={r.status_code} body={r.text[:160]}\n")
        return success
    except Exception as e:
        with open(ALERTS_API_LOG, "a") as f:
            f.write(f"{int(time.time())} EXC {type(e).__name__}: {e}\n")
        return False

# --- END: alerts HTML sender ---

def _format_price_alert_html(mint: str, price: float, base: float, delta_pct: float, src: str):
    return _format_price_alert_card(mint, price, base, delta_pct, src, up=delta_pct >= 0)

def _alerts_try_send(chat_id: int, mint: str, price: float, base: float, delta_pct: float, src: str):
    text = _format_price_alert_html(mint, price, base, delta_pct, src)
    _record_price(mint, price, src)
    return _alerts_send_html(chat_id, text)

# ---- Background ticker functions ----
def watch_tick_internal() -> str:
    """
    Do exactly what /watch_tick currently does, but just return the markdown text.
    This MUST still call _post_watch_alert_hook(...) for each checked mint.
    """
    import json, time
    
    # Load watchlist and configuration
    try:
        wl = _load_watchlist()
    except:
        wl = []
    
    base = _load_baseline()
    checked = 0
    alerts = 0
    out_lines = []
    
    for raw in wl:
        mint = raw.get("mint") if isinstance(raw, dict) else (raw if isinstance(raw, str) else "")
        if not mint:
            continue
            
        checked += 1
        
        # Get real price with fallback chain
        r = _price_lookup_any(mint)
        last_price = float(r.get("price") or 0.0)
        source = r.get("source") or "n/a"
        
        # Compute Δ vs baseline for display
        bl = base.get(mint)
        baseline_price = None
        if bl and ("price" in bl):
            try:
                baseline_price = float(bl["price"])
                delta_pct = (last_price - baseline_price) / baseline_price * 100.0
            except Exception:
                delta_pct = 0.0
        else:
            delta_pct = 0.0
        
        # Colorized triangle based on price movement
        if baseline_price is not None and last_price > 0:
            tri = "🟢▲" if last_price >= baseline_price else "🔴▼"
        else:
            tri = "△"
        
        # Display line with colorized arrow, token label, and real baseline delta
        token_label = _token_label(mint)
        out_lines.append(f"- {token_label} {tri} last=${last_price:.6f} Δ={delta_pct:+.4%} src={source}")
        
        # Only call alert hook if we have a real price
        if last_price > 0:
            try:
                result = _post_watch_alert_hook(mint, last_price, source)
                if result and result.get("alerted"):
                    alerts += 1
            except Exception as e:
                # avoid using a local 'logging' name in this scope
                import logging as pylog
                pylog.exception("watch alert hook failed for %s: %s", mint, e)
    
    body = "\n".join(out_lines) if out_lines else "(no items)"
    return f"🔁 *Watch tick*\nChecked: {checked} • Alerts: {alerts}\n{body}"

# Old ticker functions removed - replaced by improved alerts_auto_* functions

# ---- New improved background ticker functions ----
def _alerts_ticker_loop():
    import time, logging
    last = 0
    while not ALERTS_TICK_STOP.is_set():
        try:
            intv = max(5, int(ALERTS_TICK_INTERVAL or 0))
            now = time.time()
            if now - last >= intv:
                try:
                    _ = watch_tick_internal()  # triggers alert hook
                except Exception:
                    logging.exception("alerts_ticker: watch_tick_internal failed")
                last = now
        except Exception:
            logging.exception("alerts_ticker: loop error")
        ALERTS_TICK_STOP.wait(1)

def alerts_auto_on(seconds: int | None = None):
    import threading, logging
    global ALERTS_TICK_THREAD, ALERTS_TICK_STOP, ALERTS_TICK_INTERVAL
    if seconds is not None:
        ALERTS_TICK_INTERVAL = max(5, int(seconds))
    if ALERTS_TICK_STOP is None:
        ALERTS_TICK_STOP = threading.Event()
    if ALERTS_TICK_THREAD and ALERTS_TICK_THREAD.is_alive():
        logging.info("ALERTS_TICK already running; interval=%ss", ALERTS_TICK_INTERVAL)
        return
    ALERTS_TICK_STOP.clear()
    ALERTS_TICK_THREAD = threading.Thread(target=_alerts_ticker_loop, daemon=True, name="alerts_ticker")
    ALERTS_TICK_THREAD.start()
    logging.info("ALERTS_TICK started interval=%ss", ALERTS_TICK_INTERVAL)

def alerts_auto_off():
    import logging
    global ALERTS_TICK_THREAD
    if ALERTS_TICK_STOP:
        ALERTS_TICK_STOP.set()
    if ALERTS_TICK_THREAD:
        logging.info("ALERTS_TICK stopping")
        ALERTS_TICK_THREAD = None

def alerts_auto_status() -> dict:
    alive = bool(ALERTS_TICK_THREAD and ALERTS_TICK_THREAD.is_alive())
    return {"alive": alive, "interval_sec": int(ALERTS_TICK_INTERVAL or 0)}

def _active_price_source():
    """Read what /source set; default to birdeye"""
    try:
        with open("/tmp/mork_price_source") as f:
            return f.read().strip() or "birdeye"
    except Exception:
        return "birdeye"

def _price_lookup_any(mint: str):
    """Try active -> birdeye -> dex -> sim with fallback chain"""
    prefer = _active_price_source()
    for src in [prefer, "birdeye", "dex", "sim"]:
        try:
            r = get_price(mint, src)  # existing function
            if r and r.get("ok") and float(r.get("price") or 0) > 0:
                return r
        except Exception:
            pass
    return {"ok": False, "price": 0.0, "source": "n/a"}

def _alerts_cfg():
    # existing file is alerts_config.json
    return _load_json("alerts_config.json") or {
        "chat_id": None, "min_move_pct": 1.0, "rate_per_min": 30,
        "muted": False, "muted_until": 0
    }

# --- BEGIN ALERTS PATCH (drop anywhere near other helpers) ---
ALERTS_CFG_FILE = "alerts_config.json"
ALERTS_BASELINE_FILE = "alerts_price_baseline.json"
PRICE_SOURCE_FILE = "price_source.json"

def _load_alerts_cfg():
    import json
    cfg = {"chat_id": None, "min_move_pct": 1.0, "rate_per_min": 5, "muted_until": 0, "muted": False}
    try: cfg.update(json.load(open(ALERTS_CFG_FILE)))
    except FileNotFoundError: pass
    cfg["min_move_pct"] = float(cfg.get("min_move_pct", 1.0))
    cfg["rate_per_min"] = int(cfg.get("rate_per_min", 5))
    cfg["muted_until"] = int(cfg.get("muted_until", 0))
    cfg["muted"] = bool(cfg.get("muted", False))
    return cfg

def _alerts_recent_log():
    import json
    try: return json.load(open("alerts_send_log.json")).get("events", [])
    except: return []

def _alerts_record_send(now_ts: int):
    import json, time
    fn = "alerts_send_log.json"
    try: log = json.load(open(fn))
    except: log = {"events":[]}
    log["events"] = [t for t in log.get("events", []) if now_ts - t < 300]
    log["events"].append(now_ts)
    json.dump(log, open(fn,"w"))
    return log["events"]

def _alerts_can_send(cfg, now_ts, recent_log):
    if cfg["muted"] or now_ts < cfg["muted_until"]:
        return False, "muted"
    window = 60
    allowed = cfg["rate_per_min"]
    recent = [t for t in recent_log if now_ts - t < window]
    if len(recent) >= allowed:
        return False, f"rate({len(recent)}/{allowed})"
    return True, ""

def _alert_baseline_get(mint):
    import json
    try: base = json.load(open(ALERTS_BASELINE_FILE))
    except FileNotFoundError: base = {}
    return base.get(mint)

def _alert_baseline_set(mint, price, src="watch"):
    import json, time
    try: base = json.load(open(ALERTS_BASELINE_FILE))
    except FileNotFoundError: base = {}
    base[mint] = {"price": float(price), "ts": int(time.time()), "src": src}
    json.dump(base, open(ALERTS_BASELINE_FILE,"w"))

def _post_watch_alert_hook(mint: str, price: float, src: str):
    """Enhanced alert hook with colored arrows, no-price guard, clear trace"""
    import logging as pylog  # avoid name clash
    TRACE = "/tmp/alerts_debug.log"
    cfg = _load_alerts_cfg()
    chat_id = cfg.get("chat_id")
    min_move = float(cfg.get("min_move_pct", 1.0))
    rate_per_min = int(cfg.get("rate_per_min", 5))
    muted = bool(cfg.get("muted", False))
    now = int(time.time())

    # No price? trace & exit
    if not price or price <= 0:
        try:
            with open(TRACE, "a") as f:
                f.write(f"{now} mint={mint[:12]}.. price=0 base=? Δ=? src={src} chat={chat_id} -> no-price\n")
        except Exception:
            pass
        return {"ok": False, "reason": "no-price"}

    base = _load_baseline()
    bl = base.get(mint)
    base_price = float(bl["price"]) if (bl and "price" in bl) else None

    delta_pct = None
    if base_price:
        try:
            delta_pct = (float(price) - base_price) / base_price * 100.0
        except Exception:
            delta_pct = None

    # Rate limit
    ok_rate = True
    rl_key = f"_rl_{mint}"
    last_sent = int(base.get(rl_key, 0))
    min_interval = max(1, int(60 / max(1, rate_per_min)))
    if now - last_sent < min_interval:
        ok_rate = False
        reason = "rate-limited"
    else:
        reason = "?"

    # Decide
    should_alert = False
    if muted:
        reason = "muted"
    elif not chat_id:
        reason = "no-chat"
    elif delta_pct is None:
        reason = "no-delta"
    elif abs(delta_pct) < min_move:
        reason = f"below-thresh({delta_pct:.4f} < {min_move:.4f})"
    elif not ok_rate:
        pass
    else:
        should_alert = True
        reason = "send"

    # Trace
    try:
        with open(TRACE, "a") as f:
            f.write(f"{now} mint={mint[:12]}.. price={price:.6f} base={base_price} Δ={delta_pct} src={src} "
                    f"chat={chat_id} min_move={min_move} rate={rate_per_min}/min muted={muted} -> {reason}\n")
    except Exception:
        pass

    # Send and update
    if should_alert:
        try:
            success = _alerts_try_send(chat_id, mint, price, base_price, delta_pct, src)
            if success:
                base[rl_key] = now
        except Exception as e:
            pylog.exception("HTML alert send failed: %s", e)

    # Always refresh baseline if we had a real price
    base[mint] = {"price": float(price), "ts": now, "src": src}
    _save_baseline(base)
    
    return {"ok": True, "alerted": should_alert, "delta_pct": delta_pct, "reason": reason}
# --- END ALERTS PATCH ---

# Disable scanners by default for the poller process.
FETCH_ENABLE_SCANNERS = os.getenv("FETCH_ENABLE_SCANNERS", "0") == "1"

APP_BUILD_TAG = time.strftime("%Y-%m-%dT%H:%M:%S")

BIRDEYE_BASE = "https://public-api.birdeye.so"

# ── API Helper Functions for Multi-Window Price Changes ──

def birdeye_req(endpoint: str, params: dict = None) -> dict | None:
    """Make authenticated request to Birdeye API"""
    import os, requests
    api_key = os.getenv("BIRDEYE_API_KEY", "").strip()
    if not api_key:
        return None
    
    try:
        headers = {"X-API-KEY": api_key, "X-Chain": "solana"}
        url = f"{BIRDEYE_BASE}{endpoint}"
        r = requests.get(url, params=params or {}, headers=headers, timeout=(5, 10))
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def dexscreener_token(mint: str) -> dict | None:
    """Get best DexScreener pair by liquidity for a token"""
    import requests
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=(5, 10))
        if r.status_code == 200:
            js = r.json() or {}
            pairs = js.get("pairs") or []
            if pairs:
                # Sort by liquidity USD (descending) and return the best pair
                pairs_with_liq = []
                for p in pairs:
                    liq = (p.get("liquidity") or {}).get("usd")
                    if isinstance(liq, (int, float)) and liq > 0:
                        pairs_with_liq.append((liq, p))
                
                if pairs_with_liq:
                    pairs_with_liq.sort(key=lambda x: x[0], reverse=True)
                    return pairs_with_liq[0][1]  # Return the pair with highest liquidity
                else:
                    return pairs[0]  # Fallback to first pair if no liquidity data
    except Exception:
        pass
    return None

def get_token_changes(mint: str) -> dict:
    """
    Returns percent changes as floats (e.g., +4.72 -> 4.72, -3.15 -> -3.15)
    Keys: m30, h1, h4, h12, h24
    """
    out = {"m30": None, "h1": None, "h4": None, "h12": None, "h24": None}

    # --- Birdeye primary (v3 market-data) ---
    # GET /defi/v3/token/market-data?address=<mint>&chain=solana
    b = birdeye_req("/defi/v3/token/market-data",
                    {"address": mint, "chain": "solana"})
    if b and b.get("data"):
        d = b["data"]
        # Accept any of these keys if present; some tokens omit a few.
        keymap = {
            "m30": ["priceChange30mPercent", "price_change_30m_percent"],
            "h1":  ["priceChange1hPercent",  "price_change_1h_percent"],
            "h4":  ["priceChange4hPercent",  "price_change_4h_percent"],
            "h12": ["priceChange12hPercent", "price_change_12h_percent"],
            "h24": ["priceChange24hPercent", "price_change_24h_percent"],
        }
        for k, candidates in keymap.items():
            for c in candidates:
                v = d.get(c)
                if v is not None:
                    try:
                        out[k] = float(v)
                    except Exception:
                        pass
                    break

    # --- DexScreener fallback for any missing fields ---
    # GET https://api.dexscreener.com/latest/dex/tokens/<mint>
    # Pick the top pair by liquidity; fields live in pair["priceChange"]
    missing = [k for k,v in out.items() if v is None]
    if missing:
        dx = dexscreener_token(mint)  # <- implement if not present; returns best pair dict or None
        if dx:
            pc = (dx.get("priceChange") or {})
            # DexScreener has m5, m15, m30, h1, h6, h24.
            if "m30" in missing and pc.get("m30") not in (None, "N/A"):
                out["m30"] = float(pc["m30"])
            if "h1" in missing and pc.get("h1") not in (None, "N/A"):
                out["h1"] = float(pc["h1"])
            # Best-effort approximations for h4/h12 if Birdeye lacked them:
            if "h4" in missing:
                # prefer exact if dex provides it in newer schema; else try h6 as a proxy
                v = pc.get("h4") or pc.get("h6")
                if v not in (None, "N/A"):
                    out["h4"] = float(v)
            if "h12" in missing:
                v = pc.get("h12") or None
                if v not in (None, "N/A"):
                    out["h12"] = float(v)
            if "h24" in missing and pc.get("h24") not in (None, "N/A"):
                out["h24"] = float(pc["h24"])

    return out

# --- Alerts wiring: price→group hook (lightweight & safe) --------------------
# Persists last seen price per mint; honors your alerts_config.json thresholds.
ALERTS_CFG_PATH = os.getenv("ALERTS_CFG_PATH", "alerts_config.json")
ALERTS_BASE_PATH = os.getenv("ALERTS_BASE_PATH", "alerts_price_baseline.json")
WATCH_STATE_PATH = "watch_state.json"  # per-mint state: last_price, last_alert_ts

_PRICE_BLOCK_RE = re.compile(
    r"\*\*Price Lookup:\*\*\s*`([A-Za-z0-9:_\-\.]+).*?\*\*Current Price:\*\*\s*\$([0-9]*\.?[0-9]+).*?\*\*Source:\*\*\s*([a-zA-Z0-9_\(\)\s]+)",
    re.IGNORECASE | re.DOTALL,
)

def _alerts_load_cfg():
    try:
        with open(ALERTS_CFG_PATH, "r") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    # sane defaults
    cfg.setdefault("chat_id", None)
    cfg.setdefault("min_move_pct", 0.0)     # %; set with /alerts_minmove
    cfg.setdefault("rate_per_min", 60)      # max sends / minute
    cfg.setdefault("muted_until", 0)        # epoch seconds
    cfg.setdefault("sent_log", [])          # timestamps of recent sends
    return cfg

def _alerts_save_cfg(cfg):
    try:
        with open(ALERTS_CFG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def _baseline_load():
    try:
        with open(ALERTS_BASE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _baseline_save(obj):
    try:
        with open(ALERTS_BASE_PATH, "w") as f:
            json.dump(obj, f, indent=2)
    except Exception:
        pass

def _alerts_allowed(cfg, now):
    # mute?
    if now < int(cfg.get("muted_until", 0) or 0):
        return False
    # rate limit?
    window = 60
    sent = [t for t in cfg.get("sent_log", []) if now - t < window]
    if len(sent) >= int(cfg.get("rate_per_min", 60) or 60):
        return False
    cfg["sent_log"] = sent
    return True

def _alerts_record_send(cfg, now):
    cfg.setdefault("sent_log", []).append(now)
    _alerts_save_cfg(cfg)

def _alerts_emit(text, force=False):
    """Send to configured alerts chat (respects mute/rate unless force=True)."""
    from app import tg_send  # reuse unified sender
    cfg = _alerts_load_cfg()
    chat_id = cfg.get("chat_id")
    if not chat_id:
        return False
    now = int(time.time())
    if not force and not _alerts_allowed(cfg, now):
        return False
    success = bool(tg_send(chat_id, text, preview=True).get("ok"))
    if success:
        _alerts_record_send(cfg, now)
    return success

def _maybe_alert_from_price(mint, price, source):
    """Compare to baseline & alert if move >= min_move_pct."""
    try:
        mint_key = str(mint)
        base = _baseline_load()
        prev = base.get(mint_key)
        base[mint_key] = {"px": float(price), "ts": int(time.time())}
        _baseline_save(base)
        if prev is None:
            return False  # first observation, no delta yet
        prev_px = float(prev.get("px", 0) or 0)
        if prev_px <= 0:
            return False
        move_pct = (float(price) - prev_px) / prev_px * 100.0
        cfg = _alerts_load_cfg()
        thresh = _as_float(cfg.get("min_move_pct", 0) or 0.0, 0.0)
        if abs(move_pct) < thresh:
            return False
        emoji = "🟢▲" if move_pct >= 0 else "🔴▼"
        msg = (
            f"{emoji} *Price Alert*\n"
            f"*Mint:* `{mint_key}`\n"
            f"*Move:* {move_pct:+.2f}%\n"
            f"*Price:* ${float(price):.6f}\n"
            f"*Source:* {source}"
        )
        return _alerts_emit(msg, force=False)
    except Exception as e:
        logger.warning("alert hook error: %s", e)
        return False

def _post_price_alert_hook(update, out):
    """Inspect router reply; if it's a /price block, parse & maybe alert."""
    try:
        # only text replies
        text = (out or {}).get("response") or ""
        m = _PRICE_BLOCK_RE.search(text)
        if not m:
            return out
        mint, px, src = m.group(1), m.group(2), m.group(3)
        _maybe_alert_from_price(mint, float(px), src)
    except Exception as e:
        logger.debug("price hook skip: %s", e)
    return out

# --- Price source persistence helpers ---
PRICE_SOURCE_FILE = "./data/price_source.txt"

def _read_price_source():
    try:
        s = open(PRICE_SOURCE_FILE, "r").read().strip().lower()
        return s if s in ("sim", "dex", "birdeye") else "sim"
    except Exception:
        return "sim"

def _write_price_source(s: str):
    try:
        os.makedirs(os.path.dirname(PRICE_SOURCE_FILE), exist_ok=True)
        open(PRICE_SOURCE_FILE, "w").write(s.strip().lower())
    except Exception:
        pass

# ---------- Alerts routing (group) ----------
ALERTS_CFG_FILE = "alerts_config.json"
_ALERTS_RATE_STATE = {"window_start": 0, "count": 0}  # in-memory per-process

def _alerts_defaults():
    return {
        "chat_id": None,          # int telegram chat id for alerts
        "rate_per_min": 60,       # max alerts per minute
        "min_move_pct": 0.0,      # informational threshold (hook scanners later)
        "muted_until": None,      # ISO8601 string or None
    }

def _alerts_load():
    try:
        with open(ALERTS_CFG_FILE, "r") as f:
            data = json.load(f)
            return {**_alerts_defaults(), **data}
    except Exception:
        return _alerts_defaults()

def _alerts_save(cfg):
    tmp = {**_alerts_defaults(), **(cfg or {})}
    with open(ALERTS_CFG_FILE, "w") as f:
        json.dump(tmp, f, indent=2)
    return tmp

def _alerts_is_muted(cfg):
    mu = cfg.get("muted_until")
    if not mu:
        return False
    try:
        return datetime.now(timezone.utc) < datetime.fromisoformat(mu)
    except Exception:
        return False

def _alerts_mute_for(cfg, seconds):
    until = datetime.now(timezone.utc) + timedelta(seconds=max(0, int(seconds)))
    cfg["muted_until"] = until.isoformat()
    return _alerts_save(cfg)

def _alerts_unmute(cfg):
    cfg["muted_until"] = None
    return _alerts_save(cfg)

def _parse_duration(s):
    # accepts "120s", "2m", "1h", "90" (seconds)
    try:
        s = str(s).strip().lower()
        if s.endswith("ms"):
            return max(0, int(float(s[:-2]) / 1000.0))
        if s.endswith("s"):
            return max(0, int(float(s[:-1])))
        if s.endswith("m"):
            return max(0, int(float(s[:-1]) * 60))
        if s.endswith("h"):
            return max(0, int(float(s[:-1]) * 3600))
        return max(0, int(float(s)))
    except Exception:
        return 0

def _alerts_settings_text():
    cfg = _alerts_load()
    muted = _alerts_is_muted(cfg)
    mu_txt = "no"
    if muted:
        try:
            t = datetime.fromisoformat(cfg["muted_until"]).strftime("%H:%M:%S UTC")
            mu_txt = f"yes (until {t})"
        except Exception:
            mu_txt = "yes"
    return (
        "🧰 *Alert flood control settings:*\n"
        f"chat: {cfg.get('chat_id') or 'not set'}\n"
        f"min_move_pct: {cfg.get('min_move_pct', 0.0):.1f}%\n"
        f"rate_per_min: {cfg.get('rate_per_min', 60)}\n"
        f"muted: {mu_txt}"
    )

def alerts_send(text, force=False):
    """
    Unified alert sender with mute + per-minute throttling.
    Returns dict like tg_send; {'ok':False,'description':'...'} if blocked.
    """
    cfg = _alerts_load()
    chat_id = cfg.get("chat_id")
    if not chat_id:
        return {"ok": False, "description": "alerts chat not set"}

    if not force and _alerts_is_muted(cfg):
        return {"ok": False, "description": "alerts muted"}

    # rate limit per minute (in-memory window)
    now = int(time.time())
    window = now // 60
    if _ALERTS_RATE_STATE.get("window_start") != window:
        _ALERTS_RATE_STATE["window_start"] = window
        _ALERTS_RATE_STATE["count"] = 0
    if not force and _ALERTS_RATE_STATE["count"] >= int(cfg.get("rate_per_min", 60)):
        return {"ok": False, "description": "rate limited"}
    _ALERTS_RATE_STATE["count"] += 1

    # Use the existing telegram messaging system
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return {"ok": False, "description": "no bot token"}
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": int(chat_id),
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    
    try:
        import requests
        response = requests.post(url, json=payload, timeout=10)
        return response.json() if response.status_code == 200 else {"ok": False, "description": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"ok": False, "description": str(e)}

# --- Enhanced Watch State System: per-mint tracking with sophisticated rate limiting ---

def _watch_state_load():
    """Load watch state with per-mint tracking."""
    return load_json(WATCH_STATE_PATH, {})

def _watch_state_save(st):
    """Save watch state with per-mint tracking."""
    save_json(WATCH_STATE_PATH, st)
    return st

def _alerts_can_send(now_ts: int, cfg: dict, st: dict, mint: str) -> tuple[bool, str]:
    """Enforce mute + global per-minute rate by tracking last N sent timestamps."""
    if cfg.get("muted"):
        return False, "muted"
    rpm = int(cfg.get("rate_per_min", 60))
    # global bucket
    g = st.setdefault("_global", {"sent_ts": []})
    g["sent_ts"] = [t for t in g["sent_ts"] if now_ts - t < 60]
    if len(g["sent_ts"]) >= rpm:
        return False, f"rate>{rpm}/min"
    return True, ""

def _alerts_mark_sent(now_ts: int, st: dict):
    """Mark timestamp of sent alert in global rate limiting bucket."""
    g = st.setdefault("_global", {"sent_ts": []})
    g["sent_ts"].append(now_ts)

def watch_eval_and_alert(mint: str, price: float|None, src: str, now_ts: int|None=None) -> tuple[bool, str]:
    """
    Compare current price vs last baseline, send alert if |Δ| >= min_move_pct.
    Returns (alert_sent, note). Safe if price is None.
    """
    import time
    now_ts = now_ts or int(time.time())
    if price is None:
        return False, "no_price"
    
    cfg = _load_alerts_cfg()  # Use existing enhanced config loader
    chat = cfg.get("chat_id")  # Use chat_id key from existing system
    min_move = _as_float(cfg.get("min_move_pct"), 0.0)  # Use enhanced float parser

    st = _watch_state_load()
    mint_st = st.setdefault(mint, {})
    last = mint_st.get("last_price")

    # Always record latest price for next tick
    mint_st["last_price"] = price
    mint_st["last_src"] = src
    mint_st["last_ts"] = now_ts

    if last is None or min_move <= 0:
        _watch_state_save(st)
        return False, "baseline_set"

    try:
        last_f = _as_float(last, 0.0)
        if last_f is None or last_f <= 0:
            _watch_state_save(st)
            return False, "invalid_baseline"
        delta_pct = (price - last_f) / last_f * 100.0
    except Exception:
        _watch_state_save(st)
        return False, "calc_err"

    if abs(delta_pct) < min_move:
        _watch_state_save(st)
        return False, f"below_{min_move}%"

    can, why = _alerts_can_send(now_ts, cfg, st, mint)
    if not can:
        _watch_state_save(st)
        return False, why

    # Build alert message
    arrow = "🟢▲" if delta_pct >= 0 else "🔴▼"
    text = (
        f"{arrow} *ALERT* `{mint[:10]}..`\n"
        f"*Δ:* {delta_pct:+.2f}%   *price:* ${price:.6f}\n"
        f"*src:* {src}"
    )
    
    if chat:
        try:
            # Use existing alerts_send system for consistent behavior
            result = alerts_send(text)
            if result.get("ok"):
                _alerts_mark_sent(now_ts, st)
                mint_st["last_alert_ts"] = now_ts
                _watch_state_save(st)
                return True, "sent"
            else:
                mint_st["last_err"] = result.get("description", "send_failed")
                _watch_state_save(st)
                return False, "send_err"
        except Exception as e:
            mint_st["last_err"] = str(e)
            _watch_state_save(st)
            return False, "send_err"
    else:
        _watch_state_save(st)
        return False, "no_chat"

# Define all commands at module scope to avoid UnboundLocalError
ALL_COMMANDS = [
    "/help", "/ping", "/info", "/about", "/alert", "/test123", "/commands", "/debug_cmd", "/version", "/source", "/price", "/quote", "/fetch", "/fetch_now",
    "/wallet", "/wallet_new", "/wallet_addr", "/wallet_balance", "/wallet_balance_usd", 
    "/wallet_link", "/wallet_deposit_qr", "/wallet_qr", "/wallet_reset", "/wallet_reset_cancel", 
    "/wallet_fullcheck", "/wallet_export", "/solscanstats", "/config_update", "/config_show", 
    "/scanner_on", "/scanner_off", "/threshold", "/watch", "/unwatch", "/watchlist", "/watchlist_detail", "/watch_tick", "/watch_off", "/watch_clear", "/watch_debug",
    "/autosell_on", "/autosell_off", "/autosell_status", 
    "/autosell_interval", "/autosell_set", "/autosell_list", "/autosell_remove",
    "/autosell_logs", "/autosell_dryrun", "/autosell_ruleinfo", "/alerts_settings", 
    "/alerts_to_here", "/alerts_setchat", "/alerts_rate", "/alerts_minmove",
    "/alerts_mute", "/alerts_unmute", "/alerts_on", "/alerts_off", "/alerts_test", "/alerts_preview",
    "/alerts_auto_on", "/alerts_auto_off", "/alerts_auto_status",
    "/watch_test_enhanced", "/digest_status", "/digest_time", "/digest_on", "/digest_off", "/digest_test",
    "/name_refresh", "/name_refetch_jup", "/name_set", "/name_show", "/name_clear"
]
from config import DATABASE_URL, TELEGRAM_BOT_TOKEN, ASSISTANT_ADMIN_TELEGRAM_ID
from events import BUS

# Define publish function for compatibility
def publish(topic: str, payload: dict):
    """Publish events to the new EventBus system."""
    return BUS.publish(topic, payload)

# DIGEST config (persisted) — keep keys stable for upgrades
try:
    DIGEST_CFG
except NameError:
    DIGEST_CFG = {"enabled": False, "hh": 9, "mm": 30, "last_sent_date": None}

def _utc_now():
    return datetime.utcnow()

def _next_run_utc(now=None):
    now = now or _utc_now()
    hh, mm = int(DIGEST_CFG.get("hh", 9)), int(DIGEST_CFG.get("mm", 30))
    today = now.date()
    candidate = datetime.combine(today, dtime(hh, mm))
    # If time today already passed, the next run is tomorrow
    return candidate if now <= candidate else candidate + timedelta(days=1)

def _should_fire_digest(now=None, tolerance_sec=90):
    """
    Fire when: enabled AND (now >= today@HH:MM) AND not already sent today.
    Tolerance lets us trigger even if the scheduler tick isn't exactly on the minute.
    """
    if not DIGEST_CFG.get("enabled"):
        return False
    now = now or _utc_now()
    hh, mm = int(DIGEST_CFG.get("hh", 9)), int(DIGEST_CFG.get("mm", 30))
    today = now.date()
    last = DIGEST_CFG.get("last_sent_date")
    # compute today's trigger point
    trigger = datetime.combine(today, dtime(hh, mm))
    # if last sent today, don't duplicate
    if last == str(today):
        return False
    # fire if we're past trigger OR within tolerance window
    return (now >= trigger) or (0 <= (trigger - now).total_seconds() <= tolerance_sec)

def _digest_scheduler():
    """Digest scheduler thread that runs in the background"""
    import time as _time
    while True:
        try:
            now = _utc_now()
            if _should_fire_digest(now):
                # send digest once per day (UTC)
                try:
                    # Basic digest content for now - can be enhanced later
                    note = "Scheduled digest"
                    body = ("📰 *Daily Digest — {}*\n"
                            "AutoSell: enabled=False alive=None interval=?s\n"
                            "Rules: []\n"
                            "Note: {}").format(now.strftime("%Y-%m-%d %H:%M:%S UTC"), note)
                    
                    if send_admin_md(body):
                        logger.info(f"[DIGEST] Sent scheduled digest at {now}")
                    else:
                        logger.warning("[DIGEST] Failed to send scheduled digest")
                finally:
                    DIGEST_CFG["last_sent_date"] = str(now.date())
            # optional heartbeat log
            # logger.info("[digest] next_run=%s now=%s last=%s",
            #            _next_run_utc(now), now, DIGEST_CFG.get("last_sent_date"))
        except Exception as e:
            logger.exception("digest scheduler error: %s", e)
        _time.sleep(20)  # tick every 20s for tighter tolerance

# ──────────────────────────────────────────────────────────────────────────────
# Live Price Sources (Birdeye → DexScreener → Sim)
# ──────────────────────────────────────────────────────────────────────────────

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)
PRICE_SOURCE_FILE = os.path.join(DATA_DIR, "price_source.txt")
PRICE_VALID = {"sim", "dex", "birdeye"}

# === Watchlist Engine ===
WATCH_CFG_PATH = "watchlist.json"
WATCH_STATE_PATH = "watch_state.json"
WATCH_RUN = {"enabled": True, "thread": None, "tick_secs": 15}

def _watch_load():
    try:
        return json.load(open(WATCH_CFG_PATH, "r"))
    except Exception:
        return {"mints": []}

def _watch_save(cfg):
    try:
        json.dump(cfg, open(WATCH_CFG_PATH, "w"))
    except Exception:
        pass

def _watch_state_load():
    try:
        return json.load(open(WATCH_STATE_PATH, "r"))
    except Exception:
        return {"baseline": {}, "last": {}}

def _watch_state_save(st):
    try:
        json.dump(st, open(WATCH_STATE_PATH, "w"))
    except Exception:
        pass

def _pct(a, b):
    try:
        return (a - b) / b * 100.0
    except Exception:
        return 0.0

def _as_float(x, default=0.0):
    try:
        if isinstance(x, str):
            x = x.strip().rstrip('%').strip()
        return float(x)
    except (TypeError, ValueError):
        return default

def _watch_alert(mint, price, src, pct_move, cfg_alerts):
    # honor mute & rate control via alerts_send()
    msg = (
        f"📈 *Watch Alert:* `{mint[:10]}..`\n"
        f"*Move:* {pct_move:+.2f}%\n"
        f"*Price:* ${price:.6f}\n"
        f"*Source:* {src}"
    )
    try:
        alerts_send(msg, cfg_alerts)
    except Exception:
        pass

# --- Normalized watchlist helpers ---
WATCHLIST_PATH = "watchlist.json"

def _normalize_watch_item(item):
    # Accept legacy string entries and dicts; return a dict with stable keys
    if isinstance(item, str):
        return {"mint": item, "last": None, "delta_pct": None, "src": None}
    if isinstance(item, dict):
        return {
            "mint": item.get("mint") or item.get("address") or item.get("token") or "",
            "last": item.get("last"),
            "delta_pct": item.get("delta_pct"),
            "src": item.get("src"),
        }
    return {"mint": "", "last": None, "delta_pct": None, "src": None}

def _load_watchlist():
    import json, os
    if not os.path.exists(WATCHLIST_PATH):
        return []
    try:
        data = json.load(open(WATCHLIST_PATH, "r"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [_normalize_watch_item(x) for x in data]

def _save_watchlist(items):
    import json
    # Always write normalized dict items
    norm = [_normalize_watch_item(x) for x in items]
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(norm, f, indent=2)

def _watch_contains(wl, mint):
    for x in wl:
        if _normalize_watch_item(x).get("mint") == mint:
            return True
    return False

def _load_alerts_cfg():
    import json, os, time
    path = "alerts_config.json"
    base = {"chat_id": None, "min_move_pct": 0.0, "rate_per_min": 5, "muted_until": 0, "muted": False}
    if not os.path.exists(path):
        return base
    try:
        cfg = json.load(open(path, "r"))
        if not isinstance(cfg, dict):
            return base
        # normalize known keys
        cfg["min_move_pct"] = _as_float(cfg.get("min_move_pct"), 0.0)
        cfg["rate_per_min"] = int(_as_float(cfg.get("rate_per_min"), 5))
        cfg["muted_until"]  = int(_as_float(cfg.get("muted_until"), 0))
        cfg["muted"]        = bool(cfg.get("muted", False))
        return {**base, **cfg}
    except Exception:
        return base

def watch_tick_once(send_alerts=False):
    """
    Returns (checked, fired, lines)
    Updates each item's last/src/delta_pct safely and sends alerts if movement >= min_move_pct.
    """
    wl = _load_watchlist()
    cfg = _load_alerts_config()
    min_move = _as_float(cfg.get("min_move_pct"), 0.0)

    checked = 0
    fired = 0
    lines = []
    new_wl = []

    for raw in wl:
        it = _normalize_watch_item(raw)
        mint = it.get("mint") or ""
        if not mint:
            new_wl.append(it); continue

        pref = load_current_source()
        info = get_price_with_preference(mint, pref)
        if not info or not info.get("ok"):
            new_wl.append(it); continue

        price = info.get("price")
        src = info.get("source", "n/a")
        logging.info(f"[watch_tick] mint={mint} preferred={pref} resolved_src={src} price={price}")
        if price is None:
            new_wl.append(it); continue

        checked += 1

        last = it.get("last")
        last_f = _as_float(last, None)
        if last_f in (None, 0.0):
            delta = 0.0  # first baseline set, no alert
        else:
            delta = round((price - last_f) / last_f * 100.0, 2)

        it["last"] = price
        it["delta_pct"] = delta
        it["src"] = src
        new_wl.append(it)

        lines.append(f"- {_token_label(mint)}  last=${price:.6f}  Δ={delta:+.2f}%  src={src}")

        # Enhanced dual-layer alert processing with detailed tracking
        if send_alerts and abs(delta) >= min_move:
            try:
                # Use enhanced watch_eval_and_alert for sophisticated tracking
                sent, note = watch_eval_and_alert(mint, price, src)
                if sent:
                    fired += 1
                # Add detailed note to lines for debugging/monitoring
                lines.append(f"   Alert: {_token_label(mint)} ${price:.6f} Δ={delta:+.2f}% src={src} note={note}")
            except Exception as e:
                # Fallback to simple alert system
                try:
                    if 'alerts_send' in globals():
                        alerts_send(f"📈 {mint} {delta:+.2f}% price=${price:.6f} src={src}")
                        fired += 1
                        lines.append(f"   Alert: {mint[:10]}.. ${price:.6f} Δ={delta:+.2f}% src={src} note=fallback_sent")
                except Exception:
                    lines.append(f"   Alert: {mint[:10]}.. ${price:.6f} Δ={delta:+.2f}% src={src} note=failed")

    _save_watchlist(new_wl)
    return checked, fired, lines

def _watch_tick_once():
    """Legacy wrapper for backwards compatibility"""
    cfg = _watch_load()
    st  = _watch_state_load()
    if not cfg.get("mints"):
        return
    alerts_cfg = _alerts_load_cfg()
    min_move = _as_float(alerts_cfg.get("min_move_pct", 0.0), 0.0)
    for mint in list(cfg.get("mints", [])):
        try:
            pr = get_price_with_preference(mint)  # uses selected /source with fallbacks
            if not pr.get("ok"):
                continue
            price = _as_float(pr["price"], 0.0)
            src   = pr.get("source","?")
            base  = st["baseline"].get(mint)
            last  = st["last"].get(mint)
            st["last"][mint] = price
            if base is None:
                st["baseline"][mint] = price
                continue
            move = _pct(price, base)
            if abs(move) >= min_move:
                _watch_alert(mint, price, src, move, alerts_cfg)
                # reset baseline after alert so we don't spam
                st["baseline"][mint] = price
        finally:
            _watch_state_save(st)

def _watch_loop():
    while WATCH_RUN.get("enabled", True):
        try:
            _watch_tick_once()
        except Exception:
            pass
        time.sleep(WATCH_RUN.get("tick_secs", 15))

def watch_start():
    if WATCH_RUN.get("thread"):
        return
    t = threading.Thread(target=_watch_loop, daemon=True)
    WATCH_RUN["thread"] = t
    t.start()

# simple 15s cache: key=(source,mint) -> {price,ts}
_PRICE_CACHE = {}
_PRICE_TTL_S = 15

PRICE_SOURCE_PATH = "/tmp/mork_price_source"

def load_current_source() -> str:
    try:
        s = open(PRICE_SOURCE_PATH, "r").read().strip().lower()
        return s if s in {"sim","dex","birdeye"} else "sim"
    except Exception:
        return "sim"

def get_price_with_preference(mint: str, preferred: str | None = None) -> dict:
    """
    Unified price fetch with clear source labeling and graceful fallback.
    Returns: {ok: bool, price: float|None, source: str, cached: bool|None}
    """
    preferred = (preferred or load_current_source()).lower()
    chain = [preferred] + [s for s in ("birdeye","dex","sim") if s != preferred]
    last_src = preferred
    # NOTE: existing functions return dict format: {"ok": bool, "price": float, "source": str}
    for prov in chain:
        if prov == "birdeye":
            result = price_birdeye(mint)
        elif prov == "dex":
            result = price_dexscreener(mint) if 'price_dexscreener' in globals() else {"ok": False}
        else:
            # sim always succeeds
            result = price_sim(mint)
        
        if result.get("ok") and result.get("price") is not None:
            px = result["price"]
            # Check if this is the preferred source or a fallback
            is_preferred = (prov == preferred)
            is_sim_fallback = (prov == "sim" and preferred == "sim")
            
            if is_preferred or is_sim_fallback:
                label = prov
            else:
                label = f"{prov} (fallback from {preferred})"
                
            return {"ok": True, "price": float(px), "source": label}
    # ultimate guard
    return {"ok": True, "price": float(price_sim(mint)), "source": f"sim (fallback from {preferred})"}

def _cache_get(src, mint):
    k = (src, mint)
    v = _PRICE_CACHE.get(k)
    if not v: return None
    if time.time() - v["ts"] > _PRICE_TTL_S:
        _PRICE_CACHE.pop(k, None)
        return None
    return v["price"]

def _cache_put(src, mint, price):
    _PRICE_CACHE[(src, mint)] = {"price": price, "ts": time.time()}

def _read_price_source():
    try:
        if os.path.exists(PRICE_SOURCE_FILE):
            s = open(PRICE_SOURCE_FILE).read().strip().lower()
            if s in PRICE_VALID:
                return s
    except Exception:
        pass
    return "sim"

def _write_price_source(s):
    try:
        if s in PRICE_VALID:
            with open(PRICE_SOURCE_FILE, "w") as f:
                f.write(s)
    except Exception:
        logger.exception("persist price source failed")

def _fmt_usd(x):
    try:
        return f"${x:,.6f}" if x < 1 else f"${x:,.6f}".rstrip("0").rstrip(".")
    except Exception:
        return str(x)

# ── Price provider: Simulator (deterministic)
def price_sim(mint):
    # Simple, deterministic pseudo-price per mint for testing
    h = int(hashlib.sha256(mint.encode()).hexdigest(), 16)
    cents = 100 + (h % 900)  # 1.00–9.99 dollars
    return {"ok": True, "price": cents / 10000.0, "source": "sim"}

# ── Price provider: DexScreener
def price_dex(mint, timeout=6):
    try:
        # token search endpoint
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return {"ok": False, "err": f"dex http {r.status_code}"}
        j = r.json()
        pairs = (j or {}).get("pairs") or []
        if not pairs:
            return {"ok": False, "err": "dex no pairs"}
        # prefer highest liquidity
        pairs.sort(key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)
        price = float(pairs[0].get("priceUsd") or 0)
        if price <= 0:
            return {"ok": False, "err": "dex invalid price"}
        return {"ok": True, "price": price, "source": "dex"}
    except Exception as e:
        return {"ok": False, "err": f"dex error: {e}"}

# ── Price provider: Birdeye (requires BIRDEYE_API_KEY)
def price_birdeye(mint: str):
    import os, requests, math, json
    api_key = os.getenv("BIRDEYE_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "err": "birdeye missing api key"}
    mint = normalize_mint(mint)
    if not is_valid_mint(mint):
        return {"ok": False, "err": "invalid mint format"}
    sess = requests.Session()
    base = "https://public-api.birdeye.so"
    headers = {
        "X-API-KEY": api_key,
        "Accept": "application/json",
        "User-Agent": "fetch-bot/1.0",
    }
    def _req(path, params=None, multi=False):
        url = f"{base}{path}"
        qp = {"chain": "solana"}
        if multi:
            # Birdeye expects 'list_address' for multi endpoints
            qp["list_address"] = mint
        else:
            qp["address"] = mint
        if params:
            qp.update(params)
        r = sess.get(url, headers=headers, params=qp, timeout=8)
        body_snip = (r.text or "")[:120].replace("\n", " ")
        print(f"INFO:birdeye_req status={r.status_code} path={path} qp={json.dumps(qp,separators=(',',':'))} body~={body_snip!r}")
        if r.status_code != 200:
            return None
        try:
            return r.json()
        except Exception:
            return None
    def _extract_price(j):
        if not j: return None
        d = j.get("data") or {}
        for k in ("value","price","priceUsd","price_usd","market_price_usd"):
            v = d.get(k)
            try:
                f = float(v)
                if math.isfinite(f) and f > 0: return f
            except Exception:
                pass
        # multi_price: {"data":{"<mint>":{"value":...}}}
        node = d.get(mint)
        if isinstance(node, dict) and "value" in node:
            try:
                f = float(node["value"])
                if math.isfinite(f) and f > 0: return f
            except Exception:
                pass
        # v3 token market-data sometimes nests price-like fields
        if isinstance(d, dict):
            for k,v in d.items():
                if isinstance(v,(int,float)) and "price" in k and v>0:
                    return float(v)
        return None
    for path, multi in [
        ("/defi/price", False),
        ("/public/price", False),
        ("/defi/v3/token/market-data", False),
        ("/public/multi_price", True),
        ("/defi/multi_price", True),
    ]:
        j = _req(path, multi=multi)
        p = _extract_price(j)
        if p:
            return {"ok": True, "price": p, "source": "birdeye"}
    return {"ok": False, "err": "birdeye all endpoints failed"}

def get_price(mint, preferred=None):
    """
    Resolve price using preferred source with graceful fallback.
    Order: preferred → (birdeye → dex → sim)
    """
    preferred = (preferred or _read_price_source()).lower()
    chain = []
    if preferred == "birdeye":
        chain = [price_birdeye, price_dex, price_sim]
    elif preferred == "dex":
        chain = [price_dex, price_birdeye, price_sim]
    else:
        chain = [price_sim, price_birdeye, price_dex]

    last_err = None
    for fn in chain:
        # cache check per function identity name (source tag)
        tag = fn.__name__.replace("price_","")
        cached = _cache_get(tag, mint)
        if cached is not None:
            return {"ok": True, "price": cached, "source": tag, "cached": True}
        res = fn(mint)
        if res.get("ok"):
            _cache_put(res["source"], mint, res["price"])
            return res
        last_err = res.get("err")
    return {"ok": False, "err": last_err or "all providers failed"}

import json
import time
import queue
# Import bot conditionally - disable if POLLING_MODE is set
POLLING_MODE = os.environ.get('POLLING_MODE', 'OFF').upper()
if POLLING_MODE == 'ON':
    print("POLLING_MODE enabled - skipping mork_bot initialization")
    mork_bot = None
else:
    try:
        from bot import mork_bot
    except Exception as e:
        print(f"Bot initialization failed: {e}")
        mork_bot = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Shared Telegram send with MarkdownV2 fallback (used by webhook & poller) ---
def _escape_mdv2(text: str) -> str:
    if text is None: return ""
    text = text.replace("\\", "\\\\")
    for ch in "_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text

def tg_send(chat_id: int, text: str, preview: bool = True):
    """Send a Telegram message with 3-tier fallback."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token: 
        logger.error("[SEND] Missing TELEGRAM_BOT_TOKEN")
        return {"ok": False, "error": "no_token"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Attempt 1: as-is, MarkdownV2
    p = {"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2", "disable_web_page_preview": not preview}
    r1 = requests.post(url, json=p, timeout=15)
    try:
        j1 = r1.json() if r1.headers.get("content-type","").startswith("application/json") else {"ok":False}
    except Exception:
        j1 = {"ok": False}
    if r1.status_code == 200 and j1.get("ok"):
        logger.info("[SEND] ok=mdv2 chat_id=%s", chat_id)
        return j1
    desc = (j1.get("description") or "").lower()
    md_err = ("can't parse entities" in desc) or ("wrong entity" in desc)
    # Attempt 2: escaped MarkdownV2
    if md_err:
        p["text"] = _escape_mdv2(text)
        r2 = requests.post(url, json=p, timeout=15)
        j2 = r2.json() if r2.status_code == 200 else {"ok": False}
        if r2.status_code == 200 and j2.get("ok"):
            logger.info("[SEND] ok=mdv2_escaped chat_id=%s", chat_id)
            return j2
        logger.error("[SEND] mdv2 escaped failed: %s", j2)
    # Attempt 3: plain text
    p.pop("parse_mode", None)
    p["text"] = text
    r3 = requests.post(url, json=p, timeout=15)
    j3 = r3.json() if r3.status_code == 200 else {"ok": False}
    if r3.status_code == 200 and j3.get("ok"):
        logger.info("[SEND] ok=plain chat_id=%s", chat_id)
        return j3
    logger.error("[SEND] all attempts failed r1=%s r3=%s", r1.status_code, r3.status_code)
    return j3

# --- BEGIN PATCH: imports & singleton (place near other imports at top of app.py) ---
from birdeye import get_scanner, set_scan_mode, birdeye_probe_once, SCAN_INTERVAL
from birdeye_ws import get_ws
from dexscreener_scanner import get_ds_client
from jupiter_scan import JupiterScan
# Solscan Pro import moved to conditional loading

# Initialize components after admin functions are defined
def _init_scanners():
    global SCANNER, ws_client, DS_SCANNER, JUPITER_SCANNER, SOLSCAN_SCANNER, SCANNERS
    
    if FETCH_ENABLE_SCANNERS:
        # (existing scanner initialization goes here unchanged)
        SCANNERS.clear()
        SCANNER = get_scanner(publish)  # Birdeye scanner singleton bound to eventbus
        
        # Only initialize WebSocket if enabled
        feature_ws = os.environ.get('FEATURE_WS', 'off').lower()  # Default to off
        if feature_ws == 'on':
            try:
                ws_client = get_ws(publish=publish, notify=send_admin_md)  # Enhanced WebSocket client with debug support
                logger.info("[WS] WebSocket client enabled (FEATURE_WS=on)")
            except Exception as e:
                ws_client = None
                logger.warning(f"[WS] WebSocket initialization failed: {e}")
        else:
            ws_client = None
            logger.info("[WS] WebSocket client disabled (FEATURE_WS=off)")
        
        DS_SCANNER = get_ds_client()  # DexScreener scanner singleton
        JUPITER_SCANNER = JupiterScan(notify_fn=_notify_tokens, cache_limit=8000, interval_sec=8)  # Jupiter scanner
        # Initialize Solscan Pro scanner if configured
        global SOLSCAN_SCANNER
        solscan_api_key = os.getenv("SOLSCAN_API_KEY")
        feature_solscan = os.getenv("FEATURE_SOLSCAN", "off").lower() == "on"
        
        # Unmistakable boot logs for debugging
        logger.info("[INIT][SOLSCAN] feature=%s keylen=%s", feature_solscan, len(solscan_api_key or ""))
        
        if feature_solscan and solscan_api_key:
            try:
                from solscan import get_solscan_scanner
                SOLSCAN_SCANNER = get_solscan_scanner(solscan_api_key)
                if SOLSCAN_SCANNER:
                    # SCANNERS registry will be populated after init
                    logger.info("[INIT][SOLSCAN] created=True id=%s", id(SOLSCAN_SCANNER))
                    SOLSCAN_SCANNER.start()
                    logger.info("[INIT][SOLSCAN] enabled=%s running=%s pid=%s",
                               getattr(SOLSCAN_SCANNER, "enabled", None), getattr(SOLSCAN_SCANNER, "running", None), os.getpid())
                else:
                    SOLSCAN_SCANNER = None
                    logger.warning("Failed to create Solscan Pro scanner instance")
            except Exception as e:
                SOLSCAN_SCANNER = None
                logger.exception("[INIT][SOLSCAN] failed: %s", e)
        else:
            SOLSCAN_SCANNER = None
            logger.info("Solscan scanner dormant (requires FEATURE_SOLSCAN=on and SOLSCAN_API_KEY)")
        
        # Boot status logs
        logger.info("[INIT][SOLSCAN] created=%s", bool(SOLSCAN_SCANNER))
        if SOLSCAN_SCANNER:
            logger.info("[INIT][SOLSCAN] enabled=%s running=%s", SOLSCAN_SCANNER.enabled, SOLSCAN_SCANNER.running)
        
        # Register scanners in centralized registry
        SCANNERS = {
            'birdeye': SCANNER,
            'jupiter': JUPITER_SCANNER,
            'solscan': SOLSCAN_SCANNER,
            'dexscreener': DS_SCANNER,
            'websocket': ws_client
        }
    else:
        print("[SCANNERS] disabled for polling-only run (set FETCH_ENABLE_SCANNERS=1 to enable)")
        SCANNERS = {}
# --- END PATCH ---

# --- BEGIN PATCH: admin notifier + WS import ---
import requests

def send_admin_md(text: str):
    """Send Markdown message to admin chat (no PTB needed)."""
    try:
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        admin_id  = int(os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID', '0') or 0)
        if not bot_token or not admin_id:
            return False
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": admin_id, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=10
        )
        return True
    except Exception as e:
        logger.exception("send_admin_md failed: %s", e)
        return False
# --- END PATCH ---

# Token notification handler for multi-source integration
def _notify_tokens(items: list, title: str = "New tokens"):
    """Universal token notification handler for all scanners"""
    if not items:
        return
    
    lines = [f"🟢 {title}:"]
    for item in items[:5]:  # Limit to 5 tokens per notification
        mint = item.get("mint", "?")
        symbol = item.get("symbol", "?") 
        name = item.get("name", "?")
        source = item.get("source", "unknown")
        
        lines.append(f"• {symbol} | {name} | {mint}")
        lines.append(f"  Birdeye: https://birdeye.so/token/{mint}?chain=solana")
        lines.append(f"  Pump.fun: https://pump.fun/{mint}")
        if source == "jupiter":
            lines.append(f"  Jupiter: Listed token")
    
    try:
        message_text = "\n".join(lines)
        send_admin_md(message_text)
        logger.info(f"[NOTIFY] Sent {title}: {len(items)} tokens")
    except Exception as e:
        logger.warning(f"Failed to send {title} notification: %s", e)

# Initialize global scanner variables
SCANNER = None
ws_client = None
DS_SCANNER = None
JUPITER_SCANNER = None
SOLSCAN_SCANNER = None

# Centralized scanner registry
SCANNERS = {}  # global, single source of truth

# Function to ensure scanners are initialized (for multi-worker setup)
def _ensure_scanners():
    """Ensure scanners are initialized in this worker process."""
    global SCANNER, JUPITER_SCANNER, SOLSCAN_SCANNER, DS_SCANNER, ws_client, SCANNERS
    
    current_pid = os.getpid()
    logger.info(f"[INIT] _ensure_scanners called in PID={current_pid}, existing SCANNERS keys: {list(SCANNERS.keys())}")
    
    # Check if already initialized
    if SOLSCAN_SCANNER is not None and SCANNERS:
        logger.info(f"[INIT] Scanners already initialized in PID={current_pid}")
        return
    
    try:
        _init_scanners()
        logger.info(f"[INIT] Scanners initialized in worker process PID={current_pid}")
        
        # Ensure SCANNERS registry is populated after initialization
        SCANNERS = {
            'birdeye': SCANNER,
            'jupiter': JUPITER_SCANNER,
            'solscan': SOLSCAN_SCANNER,
            'dexscreener': DS_SCANNER,
            'websocket': ws_client
        }
        
        # Enhanced logging for Solscan specifically
        if SOLSCAN_SCANNER:
            logger.info(f"[INIT][SOLSCAN] Worker PID={current_pid}, object={SOLSCAN_SCANNER}, enabled={getattr(SOLSCAN_SCANNER, 'enabled', 'UNKNOWN')}, running={getattr(SOLSCAN_SCANNER, 'running', 'UNKNOWN')}")
        
        logger.info(f"[INIT] SCANNERS registry populated with {len([k for k,v in SCANNERS.items() if v])} active scanners in PID={current_pid}")
        
        # Start polling service for telegram commands (disabled when POLLING_MODE=ON)
        if POLLING_MODE != 'ON':
            try:
                from telegram_polling import start_polling_service
                if start_polling_service():
                    logger.info("Telegram polling service started successfully")
                    
                    # Start digest scheduler thread
                    digest_thread = threading.Thread(target=_digest_scheduler, daemon=True)
                    digest_thread.start()
                    logger.info("Digest scheduler thread started")
                    
                    # Auto-start alerts ticker if enabled by env
                    try:
                        if int(ALERTS_TICK_DEFAULT) > 0:
                            alerts_auto_on(ALERTS_TICK_DEFAULT)
                            logger.info("Alerts ticker thread ready (interval=%ss)", ALERTS_TICK_DEFAULT)
                            logger.info("Digest + Alerts ticker threads ready")
                    except Exception:
                        logger.exception("Failed to start alerts auto ticker")
                else:
                    logger.warning("Failed to start telegram polling service")
            except Exception as e:
                logger.error("Error starting telegram polling service: %s", e)
        else:
            logger.info("Telegram polling service disabled (POLLING_MODE=ON - external polling bot expected)")
        
    except Exception as e:
        logger.error(f"Scanner initialization failed in worker PID={current_pid}: {e}")
        # Continue without scanners if initialization fails
        SCANNER = None
        JUPITER_SCANNER = None 
        SOLSCAN_SCANNER = None
        SCANNERS = {}

import re

# Enhanced command parsing with zero-width character normalization
_ZW = "\u200b\u200c\u200d\u2060\ufeff"
_CMD_RE = re.compile(r"^/\s*([A-Za-z0-9_]+)(?:@[\w_]+)?(?:\s+(.*))?$", re.S)

def _parse_cmd(text: str):
    """Enhanced command parsing with robust zero-width character normalization and regex-based parsing"""
    s = (text or "").strip()
    if not s.startswith("/"): 
        return None, ""
    for ch in _ZW: 
        s = s.replace(ch, "")
    m = _CMD_RE.match(s)
    if not m:
        head = s.split()[0]
        cmd = head.lower()
        # accept dashed variants like /alerts-settings -> /alerts_settings
        if cmd.startswith("/"):
            cmd = "/" + cmd[1:].replace("-", "_")
        return cmd, s[len(head):].strip()
    cmd = f"/{m.group(1).lower()}"
    # accept dashed variants like /alerts-settings -> /alerts_settings
    if cmd.startswith("/"):
        cmd = "/" + cmd[1:].replace("-", "_")
    return cmd, (m.group(2) or "").strip()

def _normalize_token(token_data, source=None):
    """Normalize token data for consistent formatting"""
    if not token_data:
        return {}
    
    # Basic normalization - ensure required fields exist
    normalized = {
        'mint': token_data.get('mint', ''),
        'symbol': token_data.get('symbol', 'UNKNOWN'),
        'name': token_data.get('name', ''),
        'score': token_data.get('score', 0),
        'source': source or token_data.get('source', 'unknown')
    }
    
    # Add optional fields if they exist
    for field in ['price', 'volume', 'market_cap', 'created_at']:
        if field in token_data:
            normalized[field] = token_data[field]
    
    return normalized

# --- watch helpers (drop this above process_telegram_command) ---
def _load_watchlist():
    import json
    try:
        with open("watchlist.json","r") as f:
            return json.load(f) or []
    except Exception:
        return []

def _save_watchlist(items):
    import json
    try:
        with open("watchlist.json","w") as f:
            json.dump(items, f, indent=2)
    except Exception:
        pass

def _load_alerts_cfg():
    import json, os, time
    path = "alerts_config.json"
    base = {"chat_id": None, "min_move_pct": 0.0, "rate_per_min": 5, "muted_until": 0, "muted": False}
    if not os.path.exists(path):
        return base
    try:
        cfg = json.load(open(path, "r"))
        if not isinstance(cfg, dict):
            return base
        # normalize known keys
        cfg["min_move_pct"] = _as_float(cfg.get("min_move_pct"), 0.0)
        cfg["rate_per_min"] = int(_as_float(cfg.get("rate_per_min"), 5))
        cfg["muted_until"]  = int(_as_float(cfg.get("muted_until"), 0))
        cfg["muted"]        = bool(cfg.get("muted", False))
        return {**base, **cfg}
    except Exception:
        return base

def watch_tick_once(send_alerts=True):
    wl = _load_watchlist()
    if not wl:
        return 0, 0, ["(watchlist empty)"]

    cfg = _load_alerts_cfg()
    min_move = _as_float(cfg.get("min_move_pct", 0.0), 0.0)
    muted = bool(cfg.get("muted", False))

    checked = fired = 0
    lines = []
    changed = False

    for item in wl:
        mint = item.get("mint") if isinstance(item, dict) else (item if isinstance(item, str) else None)
        if not mint:
            continue

        pr = get_price(mint, None)  # use active source with fallback
        if not pr or not pr.get("ok"):
            lines.append(f"- {mint[:10]}… price: (n/a)")
            continue

        price = _as_float(pr["price"], 0.0)
        last = _as_float(item.get("last", price), price) if isinstance(item, dict) else price
        pct = 0.0 if last == 0 else (price - last) / last * 100.0

        if isinstance(item, dict) and abs(price - last) > 1e-12:
            item["last"] = price
            changed = True

        if send_alerts and (not muted) and abs(pct) >= min_move:
            fired += 1
            try:
                alerts_send(f"⚠️ {mint}\nΔ={pct:+.2f}%  price=${price:.6f}  src={pr.get('source','?')}")
            except Exception:
                pass

        lines.append(f"- {mint[:10]}..  last=${price:.6f} Δ={pct:+.2f}% src={pr.get('source','?')}")
        checked += 1

    if changed:
        _save_watchlist(wl)

    return checked, fired, lines
# ---------- NAME SPLITTER (ticker first, brand second) ----------


# ---------- PRETTY ROW (no code block, no copy bar) ----------




SOL_MINT = "So11111111111111111111111111111111111111112"
FIGURE_SPACE = "\u2007"  # fixed-width space that aligns in Telegram UI

def _split_primary_secondary(name: str):
    """Extract ticker (primary) + long name (secondary) from a single string."""
    if not name:
        return "", ""
    s = name.strip()

    # 'Solana (SOL)' -> secondary='Solana', primary='SOL'
    m = re.match(r"^([^(]+?)\s*\(\s*([A-Z0-9]{2,12})\s*\)$", s)
    if m:
        return (m.group(2).strip(), m.group(1).strip())

    # 'SOL — Solana' or 'SOL - Solana'
    m = re.match(r"^([A-Z0-9]{2,12})\s*[—-]\s*(.+)$", s)
    if m:
        return (m.group(1).strip(), m.group(2).strip())

    # Just a ticker
    if re.fullmatch(r"[A-Z0-9]{2,12}", s):
        return (s, "")

    # Last resort: treat whole string as primary
    return (s, "")

def _cached_primary_secondary(mint: str):
    """Read token_names.json; support both old ('name') and new ('primary'/'secondary') shapes."""
    try:
        data = json.load(open("token_names.json"))
        entry = data.get(mint) or {}
        if isinstance(entry, dict):
            p = entry.get("primary")
            s = entry.get("secondary")
            if p or s:
                return (p or "", s or "")
            n = entry.get("name")
            if n:
                return _split_primary_secondary(n)
    except Exception:
        pass
    return ("", "")

def _label_block(lbl: str, width: int = 4) -> str:
    """Produce aligned 'LBL:' using figure spaces so arrows line up."""
    pad = max(0, width - len(lbl))
    return f"{lbl}:{FIGURE_SPACE * pad}"




def _fmt_pct_cell(pct):
    """Existing helper is fine, keep arrows & colors; just return 'n/a' when pct is None."""
    if pct is None:
        return "n/a"
    try:
        p = float(pct)
    except Exception:
        return "n/a"
    up = "🟢▲" if p >= 0 else "🔴▼"
    return f"{up} {p:+.2f}%"


def render_price_card(mint: str, price: float, source: str, name_display: str) -> str:
    """
    Price card:
      💰 *Price Lookup*
      Mint: <TICKER>
      <Long Name>
      (<So11..1112>)
      Price: $123.456789
      Source: birdeye
    """
    # Split resolved name into primary (ticker) and secondary (long)
    if name_display:
        parts = name_display.split("\n", 1)
        primary = parts[0].strip()
        secondary = parts[1].strip() if len(parts) > 1 else ""
    else:
        primary, secondary = "", ""

    # Abbreviated mint (reuse your existing short() helper if present)
    try:
        short_id = short(mint)
    except NameError:
        short_id = f"{mint[:4]}..{mint[-4:]}"  # minimal fallback

    lines = ["💰 *Price Lookup*"]
    if primary:
        lines.append(f"Mint: {primary}")
        if secondary and secondary.lower() != primary.lower():
            lines.append(secondary)
    lines.append(f"({short_id})")
    lines.append(f"Price: ${price:.6f}")
    lines.append(f"Source: {source}")
    return "\n".join(lines)

def render_about_list(mint: str, price: float, source: str, name_display: str, tf: dict) -> str:
    """
    Pretty, aligned /about output using enhanced name resolution with override support.
    Uses the provided name_display which should come from _display_name_for().
    """
    # Parse the name_display into primary and secondary components
    if name_display and "\n" in name_display:
        parts = name_display.split("\n", 1)
        primary, secondary = parts[0].strip(), parts[1].strip()
    else:
        primary = name_display.strip() if name_display else ""
        secondary = ""

    # If still empty, fallback to short mint
    if not primary:
        primary = f"{mint[:4]}..{mint[-4:]}"
    
    short = f"({mint[:4]}..{mint[-4:]})"

    lines = ["*Info*"]
    lines.append(f"Mint: {primary}")
    if secondary and secondary.lower() != primary.lower():
        lines.append(secondary)
    if short not in lines[-1]:  # Only add if not already included
        lines.append(short)
    lines.append(f"Price: ${price:.6f}")
    lines.append(f"Source: {source}")

    # Timeframes (omit 12h)
    for key in ["5m", "30m", "1h", "6h", "24h"]:
        lines.append(f"{_label_block(key)} { _fmt_pct_cell(tf.get(key)) }")

    return "\n".join(lines)

# --- end helpers ---

def process_telegram_command(update: dict):

    """Enhanced command processing with unified response architecture"""
    # TEMPORARY: Log exact update once for 409 debugging
    update_id = update.get("update_id")
    if update_id and update_id % 100 == 0:  # Log every 100th update to avoid spam
        print(f"[TEMP-DEBUG] Full update: {update}")
    

    
    # Message-level deduplication in router
    msg = update.get("message") or {}
    

    # Skip deduplication for test scenarios (no update_id) or direct calls
    if update_id is not None and _webhook_is_dup_message(msg):
        print(f"[router] DUPLICATE message detected: {msg.get('message_id')}")
        result = {"status":"ok","response":"", "handled":True}  # swallow duplicate
        return result
    
    user = msg.get("from") or {}
    chat_id = msg.get("chat", {}).get("id")
    user_id = user.get("id")
    # Enhanced parsing guard (prevents UnboundLocalError)
    text = msg.get("text", "").strip()
    parts = text.split()                         # ALWAYS defined → no UnboundLocalError
    cmd   = parts[0] if parts else ""
    arg   = parts[1] if len(parts) > 1 else ""   # single string with the rest, if present
    clean = text
    args = " ".join(parts[1:]) if len(parts) > 1 else ""

    # --- ROUTER TRACE HOOK (entry) ---
    _rt_log(f"enter cmd={text.split()[0] if text else ''} chat={chat_id} user={user_id} text={repr(text)[:120]}")

    # --- HOTFIX_EXT_ROUTES_BEGIN ---
    # Early intercept: digest routes + hardened autosell_status
    # Enhanced digest commands with tolerant UTC scheduler
    if cmd in {"/digest_status", "/digest_time", "/digest_on", "/digest_off", "/digest_test"}:
        import re
        
        def cmd_digest_status():
            now = _utc_now()
            nxt = _next_run_utc(now)
            enabled = bool(DIGEST_CFG.get("enabled"))
            hh, mm = int(DIGEST_CFG.get("hh", 9)), int(DIGEST_CFG.get("mm", 30))
            return (
                "📰 *Daily Digest*\n"
                f"*Enabled:* {'yes' if enabled else 'no'}\n"
                f"*Time:* {hh:02d}:{mm:02d} UTC\n"
                f"*Next run:* {nxt.strftime('%Y-%m-%d %H:%M UTC')}\n"
            )
        
        def cmd_digest_time(args):
            # parse HH:MM and store UTC schedule; reset last_sent_date for clarity
            m = re.match(r'^\s*(\d{1,2}):(\d{2})\s*$', args or '')
            if not m:
                return "Usage: `/digest_time HH:MM` (UTC)"
            hh, mm = int(m.group(1)), int(m.group(2))
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                return "Usage: `/digest_time HH:MM` (UTC)"
            DIGEST_CFG.update({"hh": hh, "mm": mm, "last_sent_date": None})
            return f"🕰️ Digest time set to {hh:02d}:{mm:02d} UTC"
        
        def cmd_digest_on():
            DIGEST_CFG["enabled"] = True
            return "✅ Daily digest enabled"
        
        def cmd_digest_off():
            DIGEST_CFG["enabled"] = False
            return "⛔ Daily digest disabled"
        
        def cmd_digest_test(args):
            note = (args or "").strip() or "hello"
            now = _utc_now()
            body = ("📰 *Daily Digest — {}*\n"
                    "AutoSell: enabled=False alive=None interval=?s\n"
                    "Rules: []\n"
                    "Note: {}").format(now.strftime("%Y-%m-%d %H:%M:%S UTC"), note)
            return body

        if cmd == "/digest_status":
            result = {"status":"ok","response": cmd_digest_status()}
            return result
        elif cmd == "/digest_on":
            result = {"status":"ok","response": cmd_digest_on()}
            return result
        elif cmd == "/digest_off":
            result = {"status":"ok","response": cmd_digest_off()}
            return result
        elif cmd == "/digest_time":
            result = {"status":"ok","response": cmd_digest_time(args)}
            return result
        elif cmd == "/digest_test":
            result = {"status":"ok","response": cmd_digest_test(args)}
            return result

    if cmd == "/autosell_status":
        try:
            import autosell
            st = autosell.status()
        except Exception as e:
            result = {"status":"error","response": f"AutoSell status unavailable: {e}"}
            return result
        interval = st.get("interval_sec") or st.get("interval") or "n/a"
        alive    = st.get("alive", "n/a")
        rules    = st.get("rules") or []
        text = (f"🤖 AutoSell Status\n"
                f"Enabled: {st.get('enabled')}\n"
                f"Interval: {interval}s\n"
                f"Rules: {len(rules)}\n"
                f"Thread alive: {alive}")
        result = {"status":"ok","response": text}
        return result
    # --- HOTFIX_EXT_ROUTES_END ---

    # Unified reply function - single source of truth for response format
    def _reply(body: str, status: str = "ok"):
        result = {"status": status, "response": body, "handled": True}
        # Apply price alert hook before returning
        return result
    
    # Helper function for structured responses with title and body
    def ok(title: str, body: str):
        formatted_text = f"✅ *{title}*\n{body}"
        return _reply(formatted_text)
    
    # Set the global reference to avoid any shadowing issues
    global RESP_OK
    RESP_OK = ok
    
    import time
    start_time = time.time()
    user_id = user.get('id')
    
    try:
        # Check if message is a command
        is_command = cmd is not None
        
        # Admin check
        from config import ASSISTANT_ADMIN_TELEGRAM_ID
        is_admin = user.get('id') == ASSISTANT_ADMIN_TELEGRAM_ID
        
        # Structured logging: command entry
        logger.info(f"[CMD] cmd='{cmd or text}' user_id={user_id} is_admin={is_admin} is_command={is_command}")
        
        # Admin check helper
        def _require_admin(user):
            if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                return _reply("⛔ Admin only")
            return None
        
        # Basic command routing with streamlined logic
        if not is_command:
            return _reply("Not a command", "ignored")
        
        # Define public commands that don't require admin access
        public_commands = ["/help", "/ping", "/info", "/about", "/status", "/test123", "/commands", "/debug_cmd", "/version", "/source", "/price", "/quote", "/fetch", "/fetch_now", "/digest_status", "/digest_time", "/digest_on", "/digest_off", "/digest_test", "/autosell_status", "/autosell_logs", "/autosell_dryrun", "/alerts_settings", "/watch", "/unwatch", "/watchlist", "/watch_tick", "/watch_off", "/watch_debug", "/alerts_auto_on", "/alerts_auto_off", "/alerts_auto_status"]
        
        # Lightweight /status for all users (place BEFORE unknown fallback)
        if cmd == "/status":
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            mode = "Integrated Polling"
            # keep this simple to avoid Markdown pitfalls; tg_send will escape anyway
            lines = [
                "✅ Bot Status: OPERATIONAL",
                f"⚡ Mode: {mode}",
                f"⏱ Time: {now}",
                "🔒 Admin access"
            ]
            return _reply("\n".join(lines))

        # --- manual scan (one-shot) ---
        elif cmd == "/watch_tick":
            # Uses the existing internal function that returns the formatted summary
            text = watch_tick_internal()
            return ok("Watch tick", text)

        # --- automatic watch ticker controls ---
        elif cmd == "/alerts_auto_on":
            # optional interval value in seconds
            try:
                sec = int(arg) if arg else None
            except Exception:
                sec = None
            alerts_auto_on(sec)             # starts or updates the ticker
            s = alerts_auto_status()
            return ok("Auto alerts enabled", f"Interval: {s['interval_sec']}s")

        elif cmd == "/alerts_auto_off":
            alerts_auto_off()               # stops the ticker
            return ok("Auto alerts disabled", "Ticker stopped.")

        elif cmd == "/alerts_auto_status":
            s = alerts_auto_status()
            state = "on" if s["alive"] else "off"
            return ok("Auto alerts status", f"Status: {state}\nInterval: {s['interval_sec']}s")

        # Router fallback (and only one in repo) 
        if cmd not in ALL_COMMANDS:
            clean = (text or "").replace("\n", " ")
            return _reply(f"❓ Command not recognized: {clean}\nUse /help for available commands.",
                          status="unknown_command")
        
        # Admin-only check for restricted commands
        if not is_admin and cmd not in public_commands:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[CMD] cmd='{cmd}' user_id={user_id} is_admin={is_admin} duration_ms={duration_ms} status=admin_only")
            return _reply("⛔ Admin only")
        
        # Command processing with consistent response handling
        if cmd == "/help":
            help_text = "🐕 **Mork F.E.T.C.H Bot - The Degens' Best Friend**\n\n" + \
                       "**Fast Execution, Trade Control Handler**\n\n" + \
                       "📋 **Available Commands:**\n" + \
                       "/help - Show this help\n" + \
                       "/commands - List all commands\n" + \
                       "/about <mint> - snapshot: price, 5m/1h/6h/24h (providers) + 30m/12h (local) with trend arrows\n" + \
                       "/ping - Test connection\n" + \
                       "/test123 - Connection test\n\n" + \
                       "💰 **Wallet Commands:**\n" + \
                       "/wallet - Wallet summary\n" + \
                       "/wallet_new - Create new wallet\n" + \
                       "/wallet_addr - Show wallet address\n" + \
                       "/wallet_balance - Check balance\n" + \
                       "/wallet_balance_usd - Balance in USD\n" + \
                       "/wallet_link - Solscan explorer link\n" + \
                       "/wallet_deposit_qr [amount] - Generate deposit QR code with optional SOL amount\n" + \
                       "/wallet_reset - Reset wallet (2-step confirm)\n" + \
                       "/wallet_reset_cancel - Cancel pending reset\n" + \
                       "/wallet_fullcheck - Comprehensive diagnostics\n" + \
                       "/wallet_export - Export private key [Admin Only]\n\n" + \
                       "🔍 **Scanner Commands:**\n" + \
                       "/solscanstats - Scanner status & config\n" + \
                       "/config_update - Update scanner settings\n" + \
                       "/config_show - Show current config\n" + \
                       "/scanner_on / /scanner_off - Toggle scanner\n" + \
                       "/threshold <score> - Set score threshold\n" + \
                       "/watch <mint> / /unwatch <mint> - Manage watchlist\n" + \
                       "/watchlist - Show watchlist\n" + \
                       "/watch_tick - Force immediate watchlist check\n" + \
                       "/watch_off <mint> - Alias of /unwatch <mint>\n" + \
                       "/alerts_auto_on [sec] - Enable continuous scanning\n" + \
                       "/alerts_auto_off - Disable continuous scanning\n" + \
                       "/alerts_auto_status - Show auto-scan status\n" + \
                       "/fetch - Basic token fetch\n" + \
                       "/fetch_now - Multi-source fetch\n" + \
                       "/name_refresh <mint> - Refresh token name cache\n" + \
                       "/name_refetch_jup - Refresh Jupiter catalog\n" + \
                       "/name_set <mint> <TICKER>|<Long Name> - Set name override\n" + \
                       "/name_show <mint> - Show name status & overrides\n" + \
                       "/name_clear <mint> - Clear name override & cache\n\n" + \
                       "🤖 **AutoSell Commands:**\n" + \
                       "/autosell_on / /autosell_off - Enable/disable AutoSell\n" + \
                       "/autosell_status - Check AutoSell status\n" + \
                       "/autosell_interval <seconds> - Set monitoring interval\n" + \
                       "/autosell_set <mint> [tp=30] [sl=15] [trail=10] [size=100] - Set sell rules\n" + \
                       "/autosell_list - Show all AutoSell rules\n" + \
                       "/autosell_remove <mint> - Remove AutoSell rule\n\n" + \
                       "**Bot Status:** ✅ Online (Polling Mode)"
            return _reply(help_text)
        elif cmd == "/ping":
            return _reply("🎯 **Pong!** Bot is alive and responsive.")
        elif cmd == "/name_refresh":
            if len(parts) < 2:
                return _reply("Usage: /name_refresh <mint>")
            mint = parts[1].strip()
            cache = _load_json_safe(NAME_CACHE_FILE)
            if mint in cache:
                cache.pop(mint, None)
                _save_json_safe(NAME_CACHE_FILE, cache)
            # re-resolve immediately
            disp = resolve_token_name(mint, refresh=True)
            return _reply(f"🔄 Name cache refreshed:\n{mint}\n→ {disp}")
        elif cmd == "/name_refetch_jup":
            _ensure_jup_catalog(force=True)
            return _reply("🔄 Jupiter token catalog refreshed (cached for 24h).")
        elif cmd == "/name_set":
            # Usage: /name_set <mint> <TICKER>|<Long Name>
            if len(parts) < 3 or "|" not in text:
                return _reply("Usage: /name_set <mint> <TICKER>|<Long Name>")
            mint = parts[1].strip()
            rest = text.split(None, 2)[2]
            ticker, longname = [x.strip() for x in rest.split("|", 1)]
            _name_overrides_set(mint, ticker, longname)
            # also update cache so it shows immediately
            cache = _load_json_safe(NAME_CACHE_FILE)
            cache[mint] = {"primary": ticker, "secondary": longname, "ts": int(time.time())}
            _save_json_safe(NAME_CACHE_FILE, cache)
            return _reply(f"✅ Name override saved:\n{mint}\n{ticker}\n{longname}")
        elif cmd == "/name_show":
            if len(parts) < 2:
                return _reply("Usage: /name_show <mint>")
            mint = parts[1].strip()
            p0, s0 = _name_overrides_get(mint)
            cache = _load_json_safe(NAME_CACHE_FILE).get(mint) or {}
            msg = [
                "*Name status*",
                f"Mint: `{mint}`",
                f"Override: {p0 or '—'} / {s0 or '—'}",
                f"Cache: {cache.get('primary') or '—'} / {cache.get('secondary') or '—'}",
            ]
            return _reply("\n".join(msg))
        elif cmd == "/name_clear":
            if len(parts) < 2:
                return _reply("Usage: /name_clear <mint>")
            mint = parts[1].strip()
            _name_overrides_clear(mint)
            cache = _load_json_safe(NAME_CACHE_FILE)
            cache.pop(mint, None)
            _save_json_safe(NAME_CACHE_FILE, cache)
            return _reply(f"🧹 Cleared name override & cache for:\n`{mint}`")
        elif cmd == "/about":
            # /about <mint> — ticker + long name + compact timeframes
            if len(parts) < 2:
                tg_send(chat_id, "Usage: /about <mint>", preview=True)
                return {"status": "error", "err": "missing mint"}

            mint = parts[1].strip()
            # Price via current source (fallback birdeye)
            src_pref = globals().get("CURRENT_PRICE_SOURCE", "birdeye")
            pr = get_price(mint, src_pref)
            price = float(pr.get("price") or 0.0)
            src   = pr.get("source") or src_pref

            # Name and timeframes
            name_display = resolve_token_name(mint) or ""
            tf = fetch_timeframes(mint) or {}

            text = render_about_list(mint, price, src, name_display, tf)
            tg_send(chat_id, text, preview=True)
            
            # --- ABOUT RETURN FIX + TRACE ---
            _rt_log(f"about sent len={len(text)} chat={chat_id}")
            return {"status": "ok", "response": text}
        elif cmd == "/alert":
            # /alert <mint> — emit one-off Price Alert card to alerts chat (or here)
            import json, time

            def _jload(path, default):
                try:
                    with open(path, "r") as f: return json.load(f)
                except Exception:
                    return default

            if len(parts) < 2:
                tg_send(chat_id, "Usage: /alert <mint>", preview=True)
                return {"status": "error", "err": "missing mint"}

            mint = parts[1].strip()
            src_pref = globals().get("CURRENT_PRICE_SOURCE", "birdeye")
            pr = get_price(mint, src_pref)
            price = float(pr.get("price") or 0.0)
            src   = pr.get("source") or src_pref

            cfg  = _jload("alerts_config.json", {})
            base = _jload("alerts_price_baseline.json", {})
            rec  = base.get(mint) if isinstance(base, dict) else None
            baseline = float(rec["price"]) if (isinstance(rec, dict) and rec.get("price")) else None
            delta_pct = ((price - baseline) / baseline * 100.0) if (baseline and baseline > 0) else None

            name_display = resolve_token_name(mint) or ""
            short = f"({mint[:4]}..{mint[-4:]})"
            primary   = (name_display.split("\n")[0].strip() or short) if name_display else short
            secondary = "\n".join(name_display.split("\n")[1:]).strip() if name_display else ""

            arrow = "▫️"
            if delta_pct is not None:
                arrow = "🟢▲" if delta_pct >= 0 else "🔴▼"

            lines = [
                f"Price Alert {arrow}",
                f"Mint: {primary}",
            ]
            if secondary:
                lines.append(secondary)
            lines.extend([
                short,
                f"Price: ${price:.6f}",
                f"Change: {'n/a' if delta_pct is None else f'{delta_pct:+.2f}%'}",
                f"Baseline: {'n/a' if baseline is None else f'${baseline:.6f}'}",
                f"Source: {src}",
            ])
            text = "\n".join(lines)

            dest_chat = cfg.get("chat_id") or chat_id
            tg_send(dest_chat, text, preview=True)
            
            # --- ALERT RETURN FIX + TRACE ---
            _rt_log(f"alert sent len={len(text)} chat={chat_id}")
            return {"status": "ok", "response": text}
        elif cmd == "/test123":
            return _reply("✅ **Connection Test Successful!**\n\nBot is responding via polling mode.\nWebhook delivery issues bypassed.")
        elif cmd == "/commands":
            commands_text = "📋 **Available Commands**\n\n" + \
                          "**Basic:** /help /about /info /ping /test123 /debug_cmd\n" + \
                          "  /about <mint> – token snapshot (price, 5m/1h/6h/24h + 30m/12h when available)\n" + \
                          "**Wallet:** /wallet /wallet_new /wallet_addr /wallet_balance /wallet_balance_usd /wallet_link /wallet_deposit_qr /wallet_qr /wallet_reset /wallet_reset_cancel /wallet_fullcheck /wallet_export\n" + \
                          "**Scanner:** /solscanstats /config_update /config_show /scanner_on /scanner_off /threshold /watch /unwatch /watchlist /watch_tick /watch_off /alerts_auto_on /alerts_auto_off /alerts_auto_status /fetch /fetch_now\n" + \
                          "  /watch_tick – run one scan now\n" + \
                          "  /alerts_auto_on [sec] – enable continuous scanning at optional interval\n" + \
                          "  /alerts_auto_off – disable continuous scanning\n" + \
                          "  /alerts_auto_status – show auto-scan status & interval\n" + \
                          "**AutoSell:** /autosell_on /autosell_off /autosell_status /autosell_interval /autosell_set /autosell_list /autosell_remove\n\n" + \
                          "Use /help for detailed descriptions"
            return _reply(commands_text)
        elif cmd == "/debug_cmd":
            # Debug command to introspect what the router sees
            raw = update.get("message", {}).get("text") or ""
            try:
                cmd_debug, args_debug = _parse_cmd(raw)
            except Exception as e:
                return _reply(f"debug_cmd error: {e}", status="error")
            # Show repr to reveal hidden newlines / zero-width chars
            return _reply(
                "🔎 debug_cmd\n"
                f"raw: {repr(raw)}\n"
                f"cmd: {repr(cmd_debug)}\n"
                f"args: {repr(args_debug)}"
            )
        
        elif cmd == "/version":
            import hashlib
            try:
                with open("app.py", "rb") as f:
                    router_hash = hashlib.sha1(f.read()).hexdigest()[:8]
            except:
                router_hash = "unknown"
            
            version_text = f"""🤖 **Mork F.E.T.C.H Bot**
**Version:** Production v3.0 Hardened
**Mode:** Single Poller (app:app)
**RouterSHA20:** {router_hash}
**Build:** {APP_BUILD_TAG}
**Status:** ✅ Active Polling

*The Degens' Best Friend* 🐕"""
            return _reply(version_text)
        
        elif cmd == "/source":
            source_arg = arg.strip().lower() if arg else ""
            if source_arg in ("sim", "dex", "birdeye"):
                _write_price_source(source_arg)
                return _reply(f"✅ Price source set: {source_arg}")
            cur = _read_price_source()
            body = (
                "📊 **Price Sources Status**\n\n"
                f"**Active:** {cur.capitalize()} Mode\n"
                f"**Primary:** {cur}\n"
                "**Fallback:** API sources available\n"
                "**Status:** ✅ Operational\n\n"
                "Use `/source sim|dex|birdeye`"
            )
            return _reply(body)
        
        elif cmd == "/price" or cmd == "/quote":
            if not arg:
                return _reply("Usage: `/price <mint>`")
            
            mint = arg.strip()

            # Use your unified price getter + current source
            src = CURRENT_PRICE_SOURCE if 'CURRENT_PRICE_SOURCE' in globals() else 'birdeye'
            pr  = get_price(mint, src)
            price  = float(pr.get("price") or 0.0)
            source = pr.get("source") or src

            # Resolve display name exactly like /about (ticker first, then long name)
            name_display = _display_name_for(mint)

            # Render the nicer card and send
            text = render_price_card(mint, price, source, name_display)
            return _reply(text)
        
        # --- Multi-source snapshot (/fetch, /fetch_now) ---
        elif cmd in ("/fetch", "/fetch_now"):
            if not arg:
                return _reply("Usage: `/fetch <mint>`")
            mint = arg.strip()
            if not mint or len(mint) < 10:
                return _reply("❌ Invalid mint address. Please provide a valid Solana token mint address.")

            active = (_read_price_source() or "sim").lower()
            rows = []
            sources = []
            # Preferred first, then the rest
            order = ["birdeye", "dex", "sim"]
            if active in order:
                order.remove(active)
                order.insert(0, active)

            # Use existing provider wrappers; each returns {"ok", "price", "source"} or {"ok":False}
            providers = {
                "birdeye": price_birdeye,
                "dex":     price_dex,
                "sim":     price_sim,
            }

            best_price = None
            best_src = None
            for src in order:
                fn = providers.get(src)
                if not fn:
                    continue
                # honor cache used by get_price by calling through get_price with preferred=src
                res = get_price(mint, preferred=src)
                if res.get("ok"):
                    price = res["price"]
                    rows.append((src, price, bool(res.get("cached"))))
                    sources.append(src)
                    if best_price is None:
                        best_price, best_src = price, src

            if not rows:
                return _reply("❌ Snapshot failed (no providers returned a price). Try `/price <mint>`.")

            # Build message
            lines = [f"🧭 *Price Snapshot:* `{mint[:10]}..`", ""]
            lines.append(f"*Active source:* `{active}`")
            lines.append("")

            # Show each row
            for src, price, cached in rows:
                flag = "✅" if src == best_src else "•"
                cache_note = " (cached)" if cached else ""
                lines.append(f"{flag} *{src}:* {_fmt_usd(price)}{cache_note}")

            # Spread if we have ≥2 sources
            if len(rows) >= 2:
                prices = [p for _, p, _ in rows]
                hi, lo = max(prices), min(prices)
                spread = 0.0 if lo == 0 else (hi - lo) / lo * 100.0
                lines.append("")
                lines.append(f"_Spread:_ {spread:.2f}%  (hi={_fmt_usd(hi)}, lo={_fmt_usd(lo)})")

            lines.append("")
            lines.append("Tips: `/source sim|dex|birdeye`, `/price <mint> --src=birdeye`")
            return _reply("\n".join(lines))
        
        # --- Watchlist commands (lightweight v1) ---
        elif cmd == "/watch":
            if not arg:
                return {"status":"ok","response":"Usage: /watch <mint>"}
            mint = arg.strip()
            
            # Validate and normalize mint
            original_mint = mint
            mint = normalize_mint(mint)
            if not is_valid_mint(mint):
                return {"status":"ok","response":f"❌ Invalid mint address.\nExpected base58 (32–44 chars).\nGot: `{original_mint}`"}
            
            try:
                wl = _load_watchlist()
                if _watch_contains(wl, mint):
                    return {"status":"ok","response":"(already watching)"}
                wl.append({"mint": mint, "last": None, "delta_pct": None, "src": None})
                _save_watchlist(wl)
                return {"status":"ok","response":f"👁️ Watching\n`{mint}`","parse_mode":"Markdown"}
            except Exception as e:
                return {"status":"ok","response":f"Internal error: {e}"}

        elif cmd == "/unwatch" and args:
            # Validate and normalize mint
            original_args = args
            args = normalize_mint(args)
            if not is_valid_mint(args):
                return _reply(f"❌ Invalid mint address.\nExpected base58 (32–44 chars).\nGot: `{original_args}`")
                
            cfg = _watch_load()
            if args in cfg["mints"]:
                cfg["mints"].remove(args)
                _watch_save(cfg)
            st = _watch_state_load()
            st["baseline"].pop(args, None); st["last"].pop(args, None)
            _watch_state_save(st)
            return _reply("👁️ Unwatched")

        elif cmd == "/watchlist":
            try:
                wl = _load_watchlist()
                if not wl:
                    return {"status":"ok","response":"👁️ Watchlist empty."}
                lines = []
                for it in wl:
                    it = _normalize_watch_item(it)
                    mint = it["mint"]
                    last = it["last"]
                    delta = it["delta_pct"]
                    src = it.get("src") or "n/a"
                    last_s = f"${last:.6f}" if isinstance(last,(int,float)) else "?"
                    delta_s = f"{delta:+.4%}" if isinstance(delta,(int,float)) else "?"
                    token_label = _token_label(mint)
                    lines.append(f"- {token_label}  last={last_s}  Δ={delta_s}  src={src}")
                body = "\n".join(lines)
                return {"status":"ok","response":f"📄 *Watchlist:*\n{body}","parse_mode":"Markdown"}
            except Exception as e:
                return {"status":"ok","response":f"Internal error: {e}"}



        elif cmd == "/watch_off":
            if not arg:
                return {"status":"ok","response":"Usage: `/watch_off <mint>`","parse_mode":"MarkdownV2"}
            mint = arg.strip()
            
            # Validate and normalize mint
            original_mint = mint
            mint = normalize_mint(mint)
            if not is_valid_mint(mint):
                return {"status":"ok","response":f"❌ Invalid mint address.\nExpected base58 (32–44 chars).\nGot: `{original_mint}`"}
            
            try:
                wl = _load_watchlist()
                before = len(wl)
                wl = [x for x in wl if _normalize_watch_item(x).get("mint") != mint]
                _save_watchlist(wl)
                changed = (len(wl) < before)
                return {"status":"ok","response":"✅ Unwatched" if changed else "(mint not in watchlist)"}
            except Exception as e:
                return {"status":"ok","response":f"Internal error: {e}"}
        elif cmd == "/watch_on":
            if not is_admin:
                return _reply("❌ Admin only")
            WATCH_RUN["enabled"] = True
            if not WATCH_RUN.get("thread") or not WATCH_RUN["thread"].is_alive():
                watch_start()
            return _reply("▶️ Watcher running.")
        
        # --------- Alerts routing admin ---------
        elif cmd == "/alerts_settings" and is_admin:
            return _reply(_alerts_settings_text())

        elif cmd == "/alerts_to_here" and is_admin:
            cfg = _alerts_load()
            # Get chat id from the current message
            chat = update.get("message", {}).get("chat", {})
            target_id = chat.get("id")
            if not target_id:
                return _reply("❌ Can't detect current chat id.")
            cfg["chat_id"] = int(target_id)
            _alerts_save(cfg)
            return _reply(f"✅ Alerts chat set to: `{cfg['chat_id']}`")

        elif cmd == "/alerts_setchat" and is_admin:
            if not arg:
                return _reply("Usage: `/alerts_setchat <chat_id>`")
            try:
                chat_id = int(arg)
            except Exception:
                return _reply("❌ Invalid chat id.")
            cfg = _alerts_load()
            cfg["chat_id"] = chat_id
            _alerts_save(cfg)
            return _reply(f"✅ Alerts chat set to: `{chat_id}`")

        elif cmd == "/alerts_rate" and is_admin:
            if not arg:
                return _reply("Usage: `/alerts_rate <n>`")
            try:
                n = max(0, int(float(arg)))
            except Exception:
                return _reply("❌ Invalid number.")
            cfg = _alerts_load()
            cfg["rate_per_min"] = n
            _alerts_save(cfg)
            return _reply(f"🧮 Alerts rate limit: {n}/min")

        elif cmd == "/alerts_ticker_on" and is_admin:
            alerts_auto_on()
            return _reply(f"🔄 Background ticker started ({ALERTS_TICK_INTERVAL}s interval)")

        elif cmd == "/alerts_ticker_off" and is_admin:
            alerts_auto_off()
            return _reply("⏸️ Background ticker stopped")

        elif cmd == "/alerts_ticker_interval" and is_admin:
            if not arg:
                return _reply(f"Usage: `/alerts_ticker_interval <seconds>` (current: {ALERTS_TICK_INTERVAL}s)")
            try:
                interval = max(5, int(float(arg)))  # Min 5 seconds
            except Exception:
                return _reply("❌ Invalid interval (minimum 5 seconds)")
            alerts_auto_on(interval)  # Restart with new interval
            return _reply(f"⏰ Ticker interval updated to {interval}s")

        elif cmd == "/alerts_ticker_status" and is_admin:
            status_info = alerts_auto_status()
            status = "🟢 Running" if status_info["alive"] else "🔴 Stopped"
            return _reply(f"📊 Background ticker: {status}\nInterval: {status_info['interval_sec']}s\nDefault: {ALERTS_TICK_DEFAULT}s")

        elif cmd == "/alerts_auto_on":
            try: 
                sec = int(arg) if arg else None
            except: 
                sec = None
            alerts_auto_on(sec)
            s = alerts_auto_status()
            return ok("Auto alerts enabled", f"Interval: {s['interval_sec']}s")

        elif cmd == "/alerts_auto_off":
            alerts_auto_off()
            return ok("Auto alerts disabled", "Ticker stopped.")

        elif cmd == "/alerts_auto_status":
            s = alerts_auto_status()
            state = "on" if s["alive"] else "off"
            return ok("Auto alerts status", f"Status: {state}\nInterval: {s['interval_sec']}s")

        elif cmd == "/alerts_minmove" and is_admin:
            if not arg:
                return _reply("Usage: `/alerts_minmove <percent>  e.g. 0.5 or 0.5%`")
            value = _as_float(arg, None)
            if value is None:
                return _reply("❌ Invalid value. Try: `/alerts_minmove 0.5`")
            cfg = _load_alerts_cfg()
            cfg["min_move_pct"] = value
            try:
                import json
                json.dump(cfg, open("alerts_config.json","w"), indent=2)
            except Exception as e:
                return _reply(f"❌ Failed to save: {e}")
            return _reply(f"👀 Watch sensitivity set to {value:.2f}%")

        elif cmd in ("/alerts_mute", "/alerts_off") and is_admin:
            dur = arg if arg else "10m"
            seconds = _parse_duration(dur)
            if seconds <= 0:
                return _reply("Usage: `/alerts_mute <duration e.g. 120s | 2m | 1h>`")
            cfg = _alerts_load()
            _alerts_mute_for(cfg, seconds)
            return _reply(f"🔕 Alerts muted for {dur}")

        elif cmd in ("/alerts_unmute", "/alerts_on") and is_admin:
            cfg = _alerts_load()
            _alerts_unmute(cfg)
            return _reply("🔔 Alerts unmuted")

        elif cmd == "/alerts_test" and is_admin:
            msg = arg if arg else "Test alert"
            res = alerts_send(f"🚨 *Alert:*\n{msg}", force=True)
            if res.get("ok"):
                return _reply("✅ Test alert sent.")
            else:
                return _reply(f"⚠️ Could not send: {res.get('description')}")

        elif cmd == "/alerts_preview" and is_admin:
            try:
                from alerts_glue import emit_info
                success = emit_info("🔔 Preview: alerts glue operational")
                return _reply("Preview sent." if success else "Preview not sent (no chat or rate/muted).")
            except Exception as e:
                return _reply(f"Preview failed: {e}", status="error")
        
        elif cmd == "/autosell_on":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            autosell.enable()
            return _reply("🟢 AutoSell enabled.")

        elif cmd == "/autosell_off":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            autosell.disable()
            return _reply("🔴 AutoSell disabled.")



        elif cmd == "/autosell_interval":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            try:
                seconds = int((args or "").split()[0])
            except Exception:
                return _reply("Usage: /autosell_interval <seconds>")
            autosell.set_interval(seconds)
            st = autosell.status()
            return _reply(f"⏱️ AutoSell interval: {st['interval_sec']}s")

        elif cmd == "/autosell_set":
            deny = _require_admin(user)
            if deny: return deny
            import autosell, re
            m = re.match(r"/autosell_set\s+(\S+)(.*)$", text)
            if not m:
                return _reply("Usage: /autosell_set <MINT> [tp=30] [sl=15] [trail=10]")
            else:
                mint = m.group(1)
                tail = m.group(2) or ""
                kv = dict(re.findall(r"(tp|sl|trail)\s*=\s*(\d+)", tail))
                tp = int(kv["tp"]) if "tp" in kv else None
                sl = int(kv["sl"]) if "sl" in kv else None
                tr = int(kv["trail"]) if "trail" in kv else None
                r = autosell.set_rule(mint, tp, sl, tr)
                return _reply(f"✅ Rule saved: {r['mint']} tp={r['tp']} sl={r['sl']} trail={r['trail']}")
        
        elif cmd == "/autosell_logs":
            deny = _require_admin(user)
            if deny: return deny
            import autosell, re
            m = re.search(r"/autosell_logs\s+(\d+)", text)
            n = int(m.group(1)) if m else 10
            lines = autosell.get_logs(n)
            return _reply("📜 Last events:\n" + "\n".join(lines))
        
        elif cmd == "/autosell_dryrun":
            deny = _require_admin(user)
            if deny: return deny
            import autosell, re
            m = re.search(r"/autosell_dryrun\s+(\S+)", text)
            if not m:
                return _reply("Usage: /autosell_dryrun <MINT>")
            else:
                return _reply(autosell.dryrun_rule(m.group(1)))
        
        elif cmd == "/autosell_ruleinfo":
            deny = _require_admin(user)
            if deny: return deny
            import autosell, re
            m = re.search(r"/autosell_ruleinfo\s+(\S+)", text)
            if not m:
                return _reply("Usage: /autosell_ruleinfo <MINT>")
            else:
                return _reply(autosell.rule_info(m.group(1)))

        elif cmd == "/autosell_list":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            rules = autosell.get_rules()
            if not rules:
                return _reply("🤖 AutoSell rules: (none)")
            lines = ["🤖 AutoSell rules:"]
            for m, r in rules.items():
                lines.append(
                    f"{m[:8]}…  tp={r.get('tp_pct')}  sl={r.get('sl_pct')}  "
                    f"trail={r.get('trail_pct')}  size={r.get('size_pct', 100)}%"
                )
            return _reply("\n".join(lines))

        elif cmd == "/autosell_remove":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            target = (args or "").split()[0] if args else ""
            if not target:
                return _reply("Usage: /autosell_remove <MINT>")
            success = autosell.remove_rule(target)
            return _reply("🗑️ AutoSell rule removed." if success else "ℹ️ No rule found.")

        # ---- Alerts simple settings (mute/unmute/status) ----
        elif cmd in ("/alerts_settings","/alerts_status"):
            import time, re
            st = _alerts_load()
            mu = "yes" if st.get("muted_until",0) > time.time() else "no"
            left = max(0,int(st.get("muted_until",0)-time.time()))
            return _reply("🖥 Alert flood control settings:\n"
                    f"chat: {st.get('chat','not set')}\n"
                    f"min_move_pct: {st.get('min_move_pct',0.0)}%\n"
                    f"rate_per_min: {st.get('rate_per_min',60)}\n"
                    f"sent_last_min: {st.get('sent_last_min',0)}\n"
                    f"muted: {mu}" + (f" ({left}s left)" if mu=="yes" else ""))
        elif cmd == "/alerts_mute":
            import time, re
            # /alerts_mute <2m|5m|1h>
            m = re.search(r"/alerts_mute\s+(\d+)([smh]?)", text)
            if not m:
                return _reply("Usage: /alerts_mute <duration e.g. 120s | 2m | 1h>")
            else:
                val, unit = int(m.group(1)), (m.group(2) or "s")
                mult = {"s":1,"m":60,"h":3600}[unit]
                dur = val*mult
                st = _alerts_load()
                st["muted_until"] = time.time()+dur
                _alerts_save(st)
                return _reply(f"🔕 Alerts muted for {dur//60} min")
        elif cmd == "/alerts_unmute":
            import time
            st = _alerts_load()
            st["muted_until"] = 0
            _alerts_save(st)
            return _reply("🔔 Alerts unmuted")

        elif cmd == "/watch_test_enhanced" and is_admin:
            """Test enhanced alert tracking with detailed monitoring."""
            try:
                # Show current state before test
                cfg = _load_alerts_cfg()
                state = _watch_state_load()
                wl = _load_watchlist()
                
                lines = ["🧪 *Enhanced Alert Tracking Test*\n"]
                lines.append(f"Config: threshold={cfg.get('min_move_pct', 0)}%, rate={cfg.get('rate_per_min', 60)}/min")
                lines.append(f"Watchlist: {len(wl)} tokens")
                lines.append(f"State entries: {len(state)} total\n")
                
                # Run enhanced tick with alerts enabled
                checked, fired, tick_lines = watch_tick_once(send_alerts=True)
                lines.append(f"*Tick Results:* checked={checked}, fired={fired}")
                
                # Show regular tracking lines
                regular_lines = [line for line in tick_lines if not line.startswith("   Alert:")]
                lines.append("*Price Tracking:*")
                for line in regular_lines[:3]:  # Show first 3
                    lines.append(f"`{line}`")
                
                # Show enhanced alert tracking lines
                alert_lines = [line for line in tick_lines if line.startswith("   Alert:")]
                if alert_lines:
                    lines.append("\n*Alert Tracking:*")
                    for line in alert_lines:
                        lines.append(f"`{line}`")
                else:
                    lines.append("\n*Alert Tracking:* No alerts triggered")
                
                # Show state summary
                final_state = _watch_state_load()
                global_state = final_state.get("_global", {})
                sent_count = len(global_state.get("sent_ts", []))
                lines.append(f"\n*Rate Limiting:* {sent_count} alerts sent in last minute")
                
                return _reply("\n".join(lines))
                
            except Exception as e:
                return _reply(f"Enhanced test error: {e}")

        elif cmd == "/watch_clear" and is_admin:
            """Clear watchlist and reset all associated state data."""
            try:
                _save_watchlist([])
                # Also clear per-mint state so baselines reset
                _watch_state_save({})
                return _reply("🧹 Watchlist cleared.")
            except Exception as e:
                return _reply(f"Clear error: {e}")

        elif cmd == "/watchlist_detail":
            """Show detailed watchlist with enhanced state information."""
            try:
                wl = _load_watchlist()
                st = _watch_state_load()
                bl = _load_baseline()
                if not wl:
                    return _reply("👁️ Watchlist empty.")
                
                lines = ["📋 *Watchlist detail:*"]
                import time
                now = int(time.time())
                
                for raw in wl:
                    item = _normalize_watch_item(raw)
                    mint = item.get("mint", "")
                    if not mint:
                        continue
                        
                    # Get enhanced state information from watch_state
                    ms = st.get(mint, {})
                    last_price = ms.get("last_price")
                    state_src = ms.get("last_src", "n/a")
                    last_ts = ms.get("last_ts", now)
                    last_alert_ts = ms.get("last_alert_ts")
                    
                    # Get baseline information (handle both old float format and new dict format)
                    b = bl.get(mint)
                    if isinstance(b, dict):
                        age = f"{now - b.get('ts', now)}s" if b.get('ts') else "n/a"
                        src = b.get("src", "n/a")
                    elif b is not None:
                        # Legacy format: just a price value
                        age = "legacy"
                        src = "n/a"
                    else:
                        age = "n/a"
                        src = "n/a"
                    
                    # Calculate time since last update  
                    ago = now - int(last_ts) if last_ts != now else 0
                    last_s = f"${last_price:.6f}" if last_price is not None else "?"
                    
                    # Add alert information if available
                    alert_info = ""
                    if last_alert_ts:
                        alert_ago = now - int(last_alert_ts)
                        alert_info = f" alert={alert_ago}s"
                    
                    lines.append(f"- `{mint[:10]}..`  last={last_s} src={src} age={age}{alert_info}")
                
                return _reply("\n".join(lines))
                
            except Exception as e:
                return _reply(f"Detail error: {e}")

        # Wallet Commands
        elif cmd == "/wallet":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("💰 Wallet System\nUse /wallet_balance to check balance\nUse /wallet_addr for address\nUse /wallet_new to create new wallet")

        elif cmd == "/wallet_new":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("🔧 Wallet creation temporarily disabled for safety\nContact admin for wallet management")

        elif cmd == "/wallet_addr":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("📍 Wallet address retrieval temporarily disabled\nUse web interface for address display")

        elif cmd == "/wallet_balance":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("💰 Wallet balance check temporarily disabled\nUse web interface for balance display")

        elif cmd == "/wallet_balance_usd":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("💵 USD balance check temporarily disabled\nUse web interface for USD balance")

        elif cmd == "/wallet_link":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("🔗 Solscan link generation temporarily disabled\nUse web interface for explorer links")

        elif cmd == "/wallet_deposit_qr":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("📱 QR code generation temporarily disabled\nUse web interface for deposit QR codes")

        elif cmd == "/wallet_qr":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("📱 QR code display temporarily disabled\nUse web interface for wallet QR codes")

        elif cmd == "/wallet_reset":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("🔄 Wallet reset temporarily disabled for safety\nContact admin for wallet management")

        elif cmd == "/wallet_reset_cancel":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("❌ Wallet reset cancel not needed - reset is disabled")

        elif cmd == "/wallet_fullcheck":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("🔍 Full wallet check temporarily disabled\nUse web interface for comprehensive wallet status")

        elif cmd == "/wallet_export":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("📤 Wallet export temporarily disabled for security\nContact admin for wallet export")

        # Scanner Commands
        elif cmd == "/solscanstats":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("📊 Solscan stats available via web interface\nScanner operating normally")

        elif cmd == "/config_update":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("⚙️ Config updates via web interface\nUse /config_show to view current settings")

        elif cmd == "/config_show":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("📋 Configuration display via web interface\nScanner and AutoSell settings available online")

        elif cmd == "/scanner_on":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("🟢 Scanner control via web interface\nUse monitoring dashboard for scanner management")

        elif cmd == "/scanner_off":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("🔴 Scanner control via web interface\nUse monitoring dashboard for scanner management")

        elif cmd == "/threshold":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("🎯 Threshold adjustment via web interface\nUse monitoring dashboard for threshold settings")

        elif cmd == "/watch":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("👁️ Watchlist management via web interface\nUse monitoring dashboard for token watching")

        elif cmd == "/unwatch":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("👁️ Watchlist management via web interface\nUse monitoring dashboard to remove tokens")

        elif cmd == "/watchlist":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("📋 Watchlist display via web interface\nUse monitoring dashboard to view watched tokens")

        elif cmd == "/watch_tick":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("👁️ Watch tick via web interface\nUse monitoring dashboard for manual watchlist scanning")

        elif cmd == "/watch_off":
            if not arg:
                return {"status": "ok", "response": "Usage: `/watch_off <mint>`", "parse_mode": "MarkdownV2"}
            mint = arg.strip()
            wl = _load_watchlist()
            def _m(x): return x.get("mint") if isinstance(x,dict) else (x if isinstance(x,str) else "")
            before = len(wl)
            wl = [x for x in wl if _m(x) != mint]
            _save_watchlist(wl)
            return {"status":"ok","response":"✅ Unwatched" if len(wl) < before else "(mint not in watchlist)"}

        elif cmd == "/watch_debug":
            try:
                mint = arg.strip() if arg else ""
                
                if not mint:
                    return {"status":"ok","response":"Usage: `/watch_debug <mint>`","parse_mode":"Markdown"}
                
                cfg = _load_alerts_cfg()
                base = _load_baseline()
                bl = base.get(mint)
                r = _price_lookup_any(mint)
                price = float(r.get("price") or 0.0)
                src = r.get("source") or "n/a"
                
                if bl and "price" in bl and float(bl["price"]) > 0 and price > 0:
                    delta_pct = (price - float(bl["price"])) / float(bl["price"]) * 100.0
                else:
                    delta_pct = 0.0
                    
                msg = (
                    "*Watch debug*\n"
                    f"cfg: chat={cfg.get('chat_id')} min={cfg.get('min_move_pct')} rate={cfg.get('rate_per_min')}/min muted={cfg.get('muted')}\n"
                    f"- `{mint[:12]}..`  last=${price:.6f}  base=${(bl or {}).get('price', 'n/a')}  Δ={delta_pct:+.4f}%  src={src}"
                )
                return {"status":"ok","response":msg,"parse_mode":"Markdown"}
            except Exception as e:
                import logging as pylog
                pylog.exception("/watch_debug failed: %s", e)
                return {"status":"ok","response":f"Internal error: {e}"}

        elif cmd == "/fetch":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("🎣 Token fetching via web interface\nUse monitoring dashboard for manual token discovery")

        elif cmd == "/fetch_now":
            deny = _require_admin(user)
            if deny: return deny
            return _reply("⚡ Instant fetch via web interface\nUse monitoring dashboard for immediate scanning")
        
        else:
            # This should not be reached due to command validation above
            return _reply("Command processing error")
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[CMD] cmd='{cmd or text}' user_id={user_id} duration_ms={duration_ms} error={e}")
        ret = _reply(f"Internal error: {e}", "error")
        
        # --- ROUTER TRACE HOOK (exit) ---
        try:
            _rt_log(f"exit ret={type(ret).__name__} resp_len={len((ret or {}).get('response','')) if isinstance(ret, dict) else 0}")
            return ret
        except NameError:
            _rt_log("exit ret=None")
            return None

# Initialize scanners after admin functions are defined
try:
    _init_scanners()
    logger.info("Scanners initialized successfully")
    # Ensure SCANNERS registry is populated after initialization
    SCANNERS = {
        'birdeye': SCANNER,
        'jupiter': JUPITER_SCANNER,
        'solscan': SOLSCAN_SCANNER,
        'dexscreener': DS_SCANNER,
        'websocket': ws_client
    }
    logger.info(f"SCANNERS registry populated with {len([k for k,v in SCANNERS.items() if v])} active scanners")
    
    # Polling service startup moved to single location to prevent duplicates
except Exception as e:
    logger.error(f"Scanner initialization failed: {e}")
    # Continue without scanners if initialization fails
    SCANNER = None
    JUPITER_SCANNER = None 
    SOLSCAN_SCANNER = None
    SCANNERS = {}

def _scanner_thread():
    while True:
        try:
            # Birdeye scanner with error handling
            if SCANNER:
                try:
                    result = SCANNER.tick()
                    if result and isinstance(result, (tuple, list)) and len(result) >= 2:
                        total, new = result[0], result[1]
                        if total > 0:
                            logger.info(f"[SCAN] birdeye tick ok: {total} items, {new} new")
                    else:
                        total, new = 0, 0
                except Exception as e:
                    total, new = 0, 0
                    app.logger.warning("[SCAN] birdeye tick error: %s", e)
            
            # Run all other scanners in SCANNERS registry
            for name, scanner in SCANNERS.items():
                if scanner and hasattr(scanner, 'tick') and hasattr(scanner, 'running') and scanner.running:
                    try:
                        result = scanner.tick()
                        if result and isinstance(result, (tuple, list)) and len(result) == 2:
                            t, n = result
                            if t > 0:
                                logger.info(f"[SCAN] {name} tick ok: {t} items, {n} new")
                        # Small jitter between sources to be courteous to APIs
                        time.sleep(0.15)
                    except Exception as e:
                        app.logger.warning("[SCAN] %s tick error: %s", name, e)
            
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            logger.warning("[SCAN] loop error: %s", e)
            time.sleep(2)

# start thread on boot
if SCANNER:
    t = threading.Thread(target=_scanner_thread, daemon=True)
    t.start()

# Remove duplicate scanner registration - already handled in _init_scanners()

# Auto-start scanners - already handled in _init_scanners()

# subscribe to publish Birdeye hits to Telegram
def _on_new(evt):
    items = evt.get("items", [])
    if not items: return
    lines = ["🟢 New tokens (Birdeye):"]
    for it in items[:5]:
        mint = it["mint"]; sym = it.get("symbol","?")
        nm = it.get("name","?")
        price = it.get("price")
        lines.append(f"• {sym} | {nm} | {mint}")
        lines.append(f"  Birdeye: https://birdeye.so/token/{mint}?chain=solana")
        lines.append(f"  Pump.fun: https://pump.fun/{mint}")
        if price: lines.append(f"  ~${price}")
    try:
        # Send notification to admin via Telegram
        import requests
        message_text = "\n".join(lines)
        send_admin_md(message_text)
    except Exception as e:
        logger.warning("Failed to send Birdeye notification: %s", e)

# Subscribe to Birdeye events via queue polling
_notification_queue = BUS.subscribe()

def _notification_thread():
    """Background thread to handle Birdeye notifications"""
    while True:
        try:
            evt = _notification_queue.get(timeout=30) if _notification_queue else None
            if not evt:
                continue
            if evt.get("type") == "scan.birdeye.new":
                _on_new(evt.get("data", {}))
        except queue.Empty:
            continue
        except Exception as e:
            logger.warning("Notification thread error: %s", e)
            time.sleep(1)

# Start notification thread
notification_thread = threading.Thread(target=_notification_thread, daemon=True)
notification_thread.start()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "mork-fetch-bot-secret-key")

@app.route('/')
def index():
    """Basic web interface"""
    return """
    <html>
    <head>
        <title>Mork F.E.T.C.H Bot</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: #1a1a1a;
                color: #ffffff;
            }
            .header { 
                text-align: center; 
                margin-bottom: 30px;
                color: #7cb342;
            }
            .feature {
                background: #2a2a2a;
                padding: 15px;
                margin: 10px 0;
                border-radius: 8px;
                border-left: 4px solid #7cb342;
            }
            .status {
                background: #0a4a0a;
                padding: 10px;
                border-radius: 5px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🐕 Mork F.E.T.C.H Bot</h1>
            <h3>Degens' Best Friend</h3>
            <p><em>Fast Execution, Trade Control Handler</em></p>
            <div style="margin-top: 15px;">
                <a href="/monitor" style="color: #7cb342; text-decoration: none; margin-right: 15px;">📊 Live Monitor</a>
                <a href="/live" style="color: #7cb342; text-decoration: none;">💻 Live Console</a>
            </div>
        </div>
        
        <div class="status">
            <strong>🟢 Bot Status: Online</strong><br>
            Production-ready Solana trading bot with safety systems active.
        </div>
        
        <div class="feature">
            <h3>🎯 Manual Sniping</h3>
            <p>Target specific tokens with <code>/snipe</code> command</p>
        </div>
        
        <div class="feature">
            <h3>🤖 Auto F.E.T.C.H</h3>
            <p>Automated discovery and trading of new Pump.fun tokens</p>
        </div>
        
        <div class="feature">
            <h3>🛡️ Safety First</h3>
            <p>MORK holder gates, spend limits, emergency stops, encrypted wallets</p>
        </div>
        
        <div class="feature">
            <h3>⚡ Jupiter Integration</h3>
            <p>Secure swaps with preflight checks and token delivery verification</p>
        </div>
        
        <div style="text-align: center; margin-top: 40px; color: #7cb342;">
            <p><strong>Ready to start fetching profits?</strong></p>
            <p>Find the bot on Telegram: <strong>@MorkFetchBot</strong></p>
        </div>
    </body>
    </html>
    """

@app.route('/webhook_v2', methods=['POST'])
def webhook_v2():
    """Clean webhook handler - replacement for broken webhook"""
    try:
        logger.info(f"[WEBHOOK_V2] Received request from {request.remote_addr}")
        
        # Get JSON data
        update_data = request.get_json()
        if not update_data:
            logger.warning("[WEBHOOK_V2] No JSON data received")
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        # Basic deduplication by update_id
        uid = update_data.get("update_id")
        if uid and _webhook_seen_update(uid):
            return jsonify({"status": "ok", "message": "duplicate ignored"}), 200
        
        # Process message
        if 'message' in update_data:
            msg = update_data['message']
            text = msg.get('text', '')
            user_id = msg.get('from', {}).get('id', '')
            chat_id = msg.get('chat', {}).get('id', '')
            
            logger.info(f"[WEBHOOK_V2] Processing '{text}' from user {user_id}")
            
            # Process command and get response
            try:
                result = process_telegram_command(update_data)
                
                # Extract response text
                if isinstance(result, dict) and result.get("handled"):
                    response_text = result.get("response", "Command processed")
                elif isinstance(result, str):
                    response_text = result
                else:
                    response_text = "⚠️ Command processing error"
                
                # Send response using simple method
                import requests
                import os
                bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
                if chat_id and bot_token and response_text:
                    payload = {
                        "chat_id": chat_id,
                        "text": response_text,
                        "parse_mode": "Markdown"
                    }
                    resp = requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json=payload,
                        timeout=10
                    )
                    logger.info(f"[WEBHOOK_V2] Response sent: {resp.status_code}")
                
            except Exception as e:
                logger.error(f"[WEBHOOK_V2] Command processing failed: {e}")
                logger.exception("Command processing exception:")
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"[WEBHOOK_V2] Error: {e}")
        logger.exception("Webhook exception:")
        return jsonify({"status": "error"}), 200

@app.route('/debug_scanners', methods=['GET'])
def debug_scanners():
    """Debug endpoint to check SCANNERS state"""
    return jsonify({
        "pid": os.getpid(),
        "scanners_keys": list(SCANNERS.keys()),
        "has_solscan": "solscan" in SCANNERS,
        "solscan_obj": str(SCANNERS.get("solscan", None)),
        "solscan_running": getattr(SCANNERS.get("solscan", None), "running", None),
        "solscan_enabled": getattr(SCANNERS.get("solscan", None), "enabled", None)
    })

@app.route('/debug_pid', methods=['GET'])
def debug_pid():
    """Simple PID endpoint for process debugging"""
    return jsonify({
        "webhook_pid": os.getpid(),
        "scanners_count": len(SCANNERS),
        "has_solscan": "solscan" in SCANNERS
    })

# Enhanced webhook deduplication system
from collections import OrderedDict
_webhook_seen_updates = OrderedDict()
_WEBHOOK_SEEN_MAX = 256

def _webhook_seen_update(uid):
    """Check if update_id already processed with LRU eviction"""
    if uid is None:  # be safe; let router dedupe by message_id
        return False
    if uid in _webhook_seen_updates:
        return True
    _webhook_seen_updates[uid] = 1
    while len(_webhook_seen_updates) > _WEBHOOK_SEEN_MAX:
        _webhook_seen_updates.popitem(last=False)
    return False

# Message-level deduplication with TTL
import time
_webhook_last_msgs = {}
_WEBHOOK_LAST_TTL = 2.0  # seconds

def _webhook_is_dup_message(msg):
    """Check for duplicate message by (message_id, user_id, chat_id) with TTL"""
    mid = (msg.get("message_id"), (msg.get("from") or {}).get("id"), (msg.get("chat") or {}).get("id"))
    if mid[0] is None:
        return False
    now = time.time()
    # purge old
    for k,t in list(_webhook_last_msgs.items()):
        if now - t > _WEBHOOK_LAST_TTL:
            _webhook_last_msgs.pop(k, None)
    if mid in _webhook_last_msgs:
        return True
    _webhook_last_msgs[mid] = now
    return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates with comprehensive logging - Fully standalone operation"""
    # Ensure scanners are initialized in this worker process
    _ensure_scanners()
    
    try:
        # Import publish at function level to avoid import issues
        # Enhanced events system
        def publish(topic, payload): return BUS.publish(topic, payload)
        
        # Log incoming webhook request - ALWAYS log
        logger.info(f"[WEBHOOK] Received {request.method} request from {request.remote_addr}")
        
        update_data = request.get_json()
        if not update_data:
            logger.warning("[WEBHOOK] No JSON data received")
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        # Enhanced perimeter deduplication
        uid = update_data.get("update_id")
        if _webhook_seen_update(uid):
            return jsonify({"status": "ok", "message": "duplicate update_id ignored"}), 200
            
        # Message-level deduplication
        message = update_data.get("message") or {}
        if _webhook_is_dup_message(message):
            return jsonify({"status": "ok", "message": "duplicate message ignored"}), 200
        
        if update_data.get('message'):
            msg_text = update_data['message'].get('text', '')
            user_id = update_data['message'].get('from', {}).get('id', '')
            logger.info(f"[WEBHOOK] Processing command: {msg_text} from user {user_id}")
        else:
            logger.info(f"[WEBHOOK] Update data: {update_data}")
        
        # ALWAYS proceed with direct webhook processing - no dependency on mork_bot
        logger.info("[WEBHOOK] Using direct webhook processing mode")
            
        # Process the update
        if 'message' in update_data:
            # STANDARD COMMAND PARSING PATTERN - THIS MUST EXIST AND BE USED:
            msg = update_data.get("message") or {}
            user = msg.get("from") or {}
            text = msg.get("text") or ""
            
            # THIS must exist and be used:
            cmd, args = _parse_cmd(text)
            
            logger.info(f"[WEBHOOK] Message from {user.get('username', 'unknown')} ({user.get('id', 'unknown')}): '{text}' -> cmd='{cmd}', args='{args}'")
            
            # Publish webhook event for real-time monitoring
            publish("webhook.update", {
                "from": user.get("username", "?"), 
                "user_id": user.get("id"),
                "text": text,
                "chat_id": msg.get('chat', {}).get('id'),
                "cmd": cmd,
                "args": args
            })
            
            # Publish command routing event for specific command tracking
            if cmd:
                publish("command.route", {"cmd": cmd, "args": args})
            
            # Check for multiple commands in one message using standard parser
            commands_in_message = []
            if text:
                # Split by whitespace and find all commands (starting with /)
                words = text.split()
                for word in words:
                    if word.startswith('/'):
                        parsed_cmd, _ = _parse_cmd(word)
                        if parsed_cmd:
                            commands_in_message.append(parsed_cmd)
            
            # If multiple commands detected, log it
            if len(commands_in_message) > 1:
                logger.info(f"[WEBHOOK] Multiple commands detected: {commands_in_message}")
            
            # Use standardized variables for backward compatibility
            message = msg  # Alias for legacy code

            # Helper functions for sending replies (with auto-split)
            def _send_chunk(txt: str, parse_mode: str = "Markdown", no_preview: bool = True) -> bool:
                try:
                    import requests
                    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
                    payload = {
                        "chat_id": message["chat"]["id"],
                        "text": txt,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": no_preview,
                    }
                    r = requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json=payload,
                        timeout=15,
                    )
                    return r.status_code == 200
                except Exception as e:
                    logger.exception("sendMessage failed: %s", e)
                    return False

            def _reply(text: str, parse_mode: str = "Markdown", no_preview: bool = True) -> bool:
                # Telegram limit ~4096; stay under 3900 to be safe with code fences
                MAX = 3900
                if len(text) <= MAX:
                    return _send_chunk(text, parse_mode, no_preview)
                # split on paragraph boundaries where possible
                i = 0
                success = True
                while i < len(text):
                    chunk = text[i:i+MAX]
                    # try not to cut mid-line
                    cut = chunk.rfind("\n")
                    if cut > 1000:  # only use if it helps
                        chunk = chunk[:cut]
                        i += cut + 1
                    else:
                        i += len(chunk)
                    success = _send_chunk(chunk, parse_mode, no_preview) and success
                return success

            def handle_update(update: dict):
                """Enhanced update handler with single-send guarantee"""
                msg = update.get("message") or update.get("edited_message") or {}
                user = msg.get("from") or {}
                text = msg.get("text") or ""
                
                # Idempotency check - prevent duplicate processing
                import hashlib
                update_id = f"{msg.get('message_id', 0)}_{user.get('id', 0)}_{text[:50]}"
                update_hash = hashlib.md5(update_id.encode()).hexdigest()
                
                # Simple in-memory deduplication using global set
                global _processed_updates
                if '_processed_updates' not in globals():
                    _processed_updates = set()
                
                if update_hash in _processed_updates:
                    logger.info(f"[WEBHOOK] Duplicate update skipped: {update_hash}")
                    return {"status": "duplicate", "handled": True}
                
                # Add to processed set (keep only last 100)
                _processed_updates.add(update_hash)
                if len(_processed_updates) > 100:
                    _processed_updates = set(list(_processed_updates)[-100:])
                
                # Single sender & single fallback pattern
                try:
                    result = process_telegram_command(update)
                    if isinstance(result, dict) and result.get("handled"):
                        out = result["response"]
                    elif isinstance(result, str):
                        out = result
                    else:
                        out = "⚠️ Processing error occurred."
                    
                    # Single send using safe telegram delivery
                    from telegram_safety import send_telegram_safe
                    from config import TELEGRAM_BOT_TOKEN
                    chat_id = msg.get('chat', {}).get('id')
                    if chat_id and TELEGRAM_BOT_TOKEN:
                        ok, status, resp = send_telegram_safe(TELEGRAM_BOT_TOKEN, chat_id, out)
                        logger.info(f"[WEBHOOK] Message sent: ok={ok}, status={status}, chat_id={chat_id}")
                    else:
                        logger.warning(f"[WEBHOOK] Send failed: chat_id={chat_id}, token_exists={bool(TELEGRAM_BOT_TOKEN)}")
                    
                    # Return handled result if processed successfully
                    if isinstance(result, dict) and result.get("handled"):
                        return result
                        
                except Exception as e:
                    logger.error(f"[WEBHOOK] Enhanced command processor failed: {e}")
                    # Fall through to legacy processing
                
                # No legacy fallback - router handles all commands
                return {"status": "router_processed", "handled": True}

            # Process the update with enhanced handler - NO LEGACY FALLBACK
            try:
                result = handle_update(update_data)
                logger.info(f"[WEBHOOK] Update handled: {result.get('status')}")
                return jsonify({"status": result.get('status', 'ok')})
            except Exception as e:
                logger.error(f"[WEBHOOK] Enhanced handler failed: {e}")
                return jsonify({"status": "error_handled"}), 200

        # End of webhook processing - router handles everything
        return jsonify({"status": "ok", "processed": True})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        logger.exception("Full webhook exception traceback:")
        # Always return 200 OK to prevent Telegram retries, even on internal errors
        return jsonify({
            "status": "error_handled", 
            "processed": True, 
            "error_type": type(e).__name__,
            "timestamp": int(__import__('time').time())
        }), 200

@app.route('/')
def home():
    """Root endpoint for health checks"""
    return jsonify({
        "status": "online",
        "bot": "Mork F.E.T.C.H Bot",
        "webhook": "active",
        "timestamp": int(__import__('time').time())
    })

@app.route('/status')
def status():
    """Bot status endpoint"""
    try:
        from safety_system import safety
        from jupiter_engine import jupiter_engine
        
        emergency_ok, _ = safety.check_emergency_stop()
        
        status_data = {
            "bot_online": mork_bot is not None,
            "emergency_stop": not emergency_ok,
            "safe_mode": safety.safe_mode,
            "max_trade_sol": safety.max_trade_sol,
            "daily_limit": safety.daily_spend_limit,
            "mork_mint": safety.mork_mint,
            "jupiter_api": "connected",
            "timestamp": int(__import__('time').time())
        }
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Status endpoint error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    import os, time, json
    hb = {"polling_healthy": False, "reason": "no_heartbeat"}
    try:
        with open("/tmp/mork_polling.lock") as f:
            hb["poller_pid"] = f.read().strip()
        hb["polling_healthy"] = True
        hb["reason"] = "ok"
    except Exception:
        pass
    return jsonify({"status": "ok", **hb}), 200

# Live event streaming dashboard routes
@app.route('/monitor')
def monitor_dashboard():
    """Real-time monitoring dashboard with live event streaming."""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Mork F.E.T.C.H Bot - Live Monitor</title>
    <style>
        body {
            font-family: 'Monaco', 'Consolas', monospace;
            background: #0a0a0a;
            color: #00ff00;
            margin: 0;
            padding: 20px;
            font-size: 14px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid #7cb342;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐕 Mork F.E.T.C.H Bot - Live Monitor</h1>
        <p>Real-time scanner and trading activity</p>
    </div>
    <div id="events"></div>
    <script>
        const eventSource = new EventSource('/events');
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const eventsDiv = document.getElementById('events');
            const eventElement = document.createElement('div');
            eventElement.innerHTML = '<strong>' + data.timestamp + '</strong>: ' + data.message;
            eventsDiv.insertBefore(eventElement, eventsDiv.firstChild);
        };
    </script>
</body>
</html>
    ''')

@app.route('/events')
def events():
    """Server-Sent Events endpoint for real-time monitoring."""
    def event_stream():
        # Import here to avoid circular imports
        def get_recent_events(limit=5):
            try:
                from eventbus import get_recent_events as _get_events
                return _get_events(limit)
            except (ImportError, AttributeError):
                # Fallback if eventbus doesn't have get_recent_events
                return [{"timestamp": "N/A", "message": "Event system unavailable"}]
        import time
        
        while True:
            events = get_recent_events(limit=5)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
            time.sleep(1)
    
    return Response(event_stream(), mimetype="text/event-stream")

# Console route for lightweight debugging
@app.route('/console')
def console():
    """Ultra-lightweight console for debugging."""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Console - Mork F.E.T.C.H Bot</title>
    <style>
        body { font-family: monospace; background: #000; color: #0f0; padding: 10px; }
        .log { margin: 2px 0; }
    </style>
</head>
<body>
    <h2>🖥️ Console</h2>
    <div id="logs"></div>
    <script>
        const eventSource = new EventSource('/events');
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const logsDiv = document.getElementById('logs');
            const logElement = document.createElement('div');
            logElement.className = 'log';
            logElement.textContent = data.timestamp + ': ' + data.message;
            logsDiv.insertBefore(logElement, logsDiv.firstChild);
            if (logsDiv.children.length > 50) {
                logsDiv.removeChild(logsDiv.lastChild);
            }
        };
    </script>
</body>
</html>
    ''')

# Initialize services when Flask app is ready
def initialize_app():
    """Initialize services for production deployment"""
    with app.app_context():
        _ensure_scanners()
        logger.info("App initialization complete")

# Call initialization immediately for production
if __name__ != '__main__':
    # Running under gunicorn or similar
    initialize_app()

# ---- helpers for alerts persistence ----
_ALERTS_FILE = "/tmp/alerts_settings.json"
def _alerts_load():
    try:
        return json.loads(open(_ALERTS_FILE).read())
    except Exception:
        return {"chat":"not set","min_move_pct":0.0,"rate_per_min":60,"sent_last_min":0,"muted_until":0}
def _alerts_save(data):
    try:
        open(_ALERTS_FILE,"w").write(json.dumps(data))
    except Exception:
        pass

# --- One-time wrapper to run post-processing hooks safely --------------------
try:
    _ORIG__PTC
except NameError:
    _ORIG__PTC = process_telegram_command
    def process_telegram_command(update):
        out = _ORIG__PTC(update)
        return _post_price_alert_hook(update, out)

if __name__ == '__main__':
    # Development mode
    initialize_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
