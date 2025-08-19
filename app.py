"""
Flask Web Application for Mork F.E.T.C.H Bot
Handles Telegram webhooks and provides web interface
"""

import os
import logging
import threading
import time
import requests
import hashlib
import inspect
import json
import textwrap
import re
from datetime import datetime, timedelta, time as dtime, timezone
from flask import Flask, request, jsonify, Response, stream_with_context, render_template_string

# Disable scanners by default for the poller process.
FETCH_ENABLE_SCANNERS = os.getenv("FETCH_ENABLE_SCANNERS", "0") == "1"

APP_BUILD_TAG = time.strftime("%Y-%m-%dT%H:%M:%S")

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

# Define all commands at module scope to avoid UnboundLocalError
ALL_COMMANDS = [
    "/help", "/ping", "/info", "/test123", "/commands", "/debug_cmd", "/version", "/source", "/price", "/quote", "/fetch", "/fetch_now",
    "/wallet", "/wallet_new", "/wallet_addr", "/wallet_balance", "/wallet_balance_usd", 
    "/wallet_link", "/wallet_deposit_qr", "/wallet_qr", "/wallet_reset", "/wallet_reset_cancel", 
    "/wallet_fullcheck", "/wallet_export", "/solscanstats", "/config_update", "/config_show", 
    "/scanner_on", "/scanner_off", "/threshold", "/watch", "/unwatch", "/watchlist", 
    "/autosell_on", "/autosell_off", "/autosell_status", 
    "/autosell_interval", "/autosell_set", "/autosell_list", "/autosell_remove",
    "/autosell_logs", "/autosell_dryrun", "/autosell_ruleinfo", "/alerts_settings", 
    "/alerts_to_here", "/alerts_setchat", "/alerts_rate", "/alerts_minmove",
    "/alerts_mute", "/alerts_unmute", "/alerts_on", "/alerts_off", "/alerts_test",
    "/digest_status", "/digest_time", "/digest_on", "/digest_off", "/digest_test"
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

# simple 15s cache: key=(source,mint) -> {price,ts}
_PRICE_CACHE = {}
_PRICE_TTL_S = 15

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
def price_birdeye(mint, timeout=6):
    key = os.getenv("BIRDEYE_API_KEY") or os.getenv("BIRDEYE_KEY")
    if not key:
        return {"ok": False, "err": "birdeye key missing"}
    try:
        url = f"https://public-api.birdeye.so/defi/price?address={mint}"
        headers = {
            "accept": "application/json",
            "x-api-key": key,
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return {"ok": False, "err": f"birdeye http {r.status_code}"}
        j = r.json() or {}
        data = j.get("data") or {}
        price = float(data.get("value") or 0)
        if price <= 0:
            return {"ok": False, "err": "birdeye invalid price"}
        return {"ok": True, "price": price, "source": "birdeye"}
    except Exception as e:
        return {"ok": False, "err": f"birdeye error: {e}"}

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
        return {"status":"ok","response":"", "handled":True}  # swallow duplicate
    
    user = msg.get("from") or {}
    text = msg.get("text") or ""
    clean = (text or "").strip() 
    cmd, args = _parse_cmd(clean)

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
            return {"status":"ok","response": cmd_digest_status()}
        elif cmd == "/digest_on":
            return {"status":"ok","response": cmd_digest_on()}
        elif cmd == "/digest_off":
            return {"status":"ok","response": cmd_digest_off()}
        elif cmd == "/digest_time":
            return {"status":"ok","response": cmd_digest_time(args)}
        elif cmd == "/digest_test":
            return {"status":"ok","response": cmd_digest_test(args)}

    if cmd == "/autosell_status":
        try:
            import autosell
            st = autosell.status()
        except Exception as e:
            return {"status":"error","response": f"AutoSell status unavailable: {e}"}
        interval = st.get("interval_sec") or st.get("interval") or "n/a"
        alive    = st.get("alive", "n/a")
        rules    = st.get("rules") or []
        text = (f"🤖 AutoSell Status\n"
                f"Enabled: {st.get('enabled')}\n"
                f"Interval: {interval}s\n"
                f"Rules: {len(rules)}\n"
                f"Thread alive: {alive}")
        return {"status":"ok","response": text}
    # --- HOTFIX_EXT_ROUTES_END ---

    # Unified reply function - single source of truth for response format
    def _reply(body: str, status: str = "ok"):
        return {"status": status, "response": body, "handled": True}
    
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
        public_commands = ["/help", "/ping", "/info", "/status", "/test123", "/commands", "/debug_cmd", "/version", "/source", "/price", "/quote", "/fetch", "/fetch_now", "/digest_status", "/digest_time", "/digest_on", "/digest_off", "/digest_test", "/autosell_status", "/autosell_logs", "/autosell_dryrun", "/alerts_settings"]
        
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
                       "/info - Bot information\n" + \
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
                       "/fetch - Basic token fetch\n" + \
                       "/fetch_now - Multi-source fetch\n\n" + \
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
        elif cmd == "/info":
            info_text = f"""🤖 **Mork F.E.T.C.H Bot Info**

**Status:** ✅ Online (Polling Mode)
**Version:** Production v2.0
**Mode:** Telegram Polling (Webhook Bypass)
**Scanner:** Solscan Active
**Wallet:** Enabled
**Admin:** {user.get('username', 'Unknown')}

*The Degens' Best Friend* 🐕"""
            return _reply(info_text)
        elif cmd == "/test123":
            return _reply("✅ **Connection Test Successful!**\n\nBot is responding via polling mode.\nWebhook delivery issues bypassed.")
        elif cmd == "/commands":
            commands_text = "📋 **Available Commands**\n\n" + \
                          "**Basic:** /help /info /ping /test123 /debug_cmd\n" + \
                          "**Wallet:** /wallet /wallet_new /wallet_addr /wallet_balance /wallet_balance_usd /wallet_link /wallet_deposit_qr /wallet_qr /wallet_reset /wallet_reset_cancel /wallet_fullcheck /wallet_export\n" + \
                          "**Scanner:** /solscanstats /config_update /config_show /scanner_on /scanner_off /threshold /watch /unwatch /watchlist /fetch /fetch_now\n" + \
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
            args = (text.split(" ", 1)[1].strip() if " " in text else "").lower()
            if not args:
                active = _read_price_source()
                return _reply(f"📊 *Price Sources Status*\n\n"
                              f"*Active:* {active.title()} Mode\n"
                              f"*Primary:* {'Built-in price simulator' if active=='sim' else active}\n"
                              f"*Fallback:* API sources available\n"
                              f"*Status:* ✅ Operational\n\n"
                              f"Use `/source sim|dex|birdeye`")
            if args not in PRICE_VALID:
                return _reply("Usage: `/source sim|dex|birdeye`")
            _write_price_source(args)
            return _reply(f"✅ Price source set: {args}")
        
        elif cmd == "/price" or cmd == "/quote":
            parts = text.split()
            if len(parts) < 2:
                return _reply("Usage: `/price <mint>`")
            mint = parts[1].strip()
            # optional override flag: --src=sim|dex|birdeye
            override = None
            if len(parts) >= 3 and parts[2].startswith("--src="):
                override = parts[2].split("=",1)[1].lower()
                if override not in PRICE_VALID:
                    return _reply("Usage: `/price <mint> --src=sim|dex|birdeye`")
            if not mint or len(mint) < 10:
                return _reply("❌ Invalid mint address. Please provide a valid Solana token mint address.")
            res = get_price(mint, preferred=override)
            if not res.get("ok"):
                return _reply(f"❌ Price lookup failed\nsource: auto\nerror: {res.get('err')}")
            p = _fmt_usd(res["price"])
            src = res["source"]
            note = " (cached)" if res.get("cached") else ""
            return _reply(f"💰 *Price Lookup:* `{mint[:10]}..`\n\n*Current Price:* {p}{note}\n*Source:* {src}")
        
        # --- Multi-source snapshot (/fetch, /fetch_now) ---
        elif cmd in ("/fetch", "/fetch_now"):
            parts = text.split()
            if len(parts) < 2:
                return _reply("Usage: `/fetch <mint>`")
            mint = parts[1].strip()
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
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return _reply("Usage: `/alerts_setchat <chat_id>`")
            try:
                chat_id = int(parts[1])
            except Exception:
                return _reply("❌ Invalid chat id.")
            cfg = _alerts_load()
            cfg["chat_id"] = chat_id
            _alerts_save(cfg)
            return _reply(f"✅ Alerts chat set to: `{chat_id}`")

        elif cmd == "/alerts_rate" and is_admin:
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return _reply("Usage: `/alerts_rate <n>`")
            try:
                n = max(0, int(float(parts[1])))
            except Exception:
                return _reply("❌ Invalid number.")
            cfg = _alerts_load()
            cfg["rate_per_min"] = n
            _alerts_save(cfg)
            return _reply(f"🧮 Alerts rate limit: {n}/min")

        elif cmd == "/alerts_minmove" and is_admin:
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return _reply("Usage: `/alerts_minmove <pct>`")
            try:
                pct = max(0.0, float(parts[1]))
            except Exception:
                return _reply("❌ Invalid percent.")
            cfg = _alerts_load()
            cfg["min_move_pct"] = pct
            _alerts_save(cfg)
            return _reply(f"👀 Watch sensitivity set to {pct:.2f}%")

        elif cmd in ("/alerts_mute", "/alerts_off") and is_admin:
            parts = text.split(maxsplit=1)
            dur = "10m" if cmd == "/alerts_off" and len(parts) == 1 else (parts[1] if len(parts) > 1 else "10m")
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
            parts = text.split(maxsplit=1)
            msg = parts[1] if len(parts) > 1 else "Test alert"
            res = alerts_send(f"🚨 *Alert:*\n{msg}", force=True)
            if res.get("ok"):
                return _reply("✅ Test alert sent.")
            else:
                return _reply(f"⚠️ Could not send: {res.get('description')}")
        
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
            ok = autosell.remove_rule(target)
            return _reply("🗑️ AutoSell rule removed." if ok else "ℹ️ No rule found.")

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
        return _reply(f"Internal error: {e}", "error")

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
                ok = True
                while i < len(text):
                    chunk = text[i:i+MAX]
                    # try not to cut mid-line
                    cut = chunk.rfind("\n")
                    if cut > 1000:  # only use if it helps
                        chunk = chunk[:cut]
                        i += cut + 1
                    else:
                        i += len(chunk)
                    ok = _send_chunk(chunk, parse_mode, no_preview) and ok
                return ok

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

if __name__ == '__main__':
    # Development mode
    initialize_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
