"""
Flask Web Application for Mork F.E.T.C.H Bot
Handles Telegram webhooks and provides web interface
"""

import os
import logging
import threading
import time
from flask import Flask, request, jsonify, Response, stream_with_context, render_template_string

# Disable scanners by default for the poller process.
FETCH_ENABLE_SCANNERS = os.getenv("FETCH_ENABLE_SCANNERS", "0") == "1"

APP_BUILD_TAG = time.strftime("%Y-%m-%dT%H:%M:%S")
APP_START_TS = int(time.time())

# Define all commands at module scope to avoid UnboundLocalError
ALL_COMMANDS = [
    "/help", "/ping", "/info", "/status", "/version", "/test123", "/commands", "/debug_cmd", "/price",
    "/wallet", "/wallet_new", "/wallet_addr", "/wallet_balance", "/wallet_balance_usd", 
    "/wallet_link", "/wallet_deposit_qr", "/wallet_qr", "/wallet_reset", "/wallet_reset_cancel", 
    "/wallet_fullcheck", "/wallet_export", "/solscanstats", "/config_update", "/config_show", 
    "/scanner_on", "/scanner_off", "/threshold", "/watch", "/unwatch", "/watchlist", 
    "/fetch", "/fetch_now", "/autosell_on", "/autosell_off", "/autosell_status", 
    "/autosell_interval", "/autosell_set", "/autosell_list", "/autosell_remove",
    "/autosell_save", "/autosell_load", "/autosell_reset", "/autosell_backup", "/autosell_break",
    "/autosell_events", "/autosell_eval", "/autosell_logs", "/autosell_dryrun", "/autosell_ruleinfo",
    "/uptime", "/health", "/pricesrc", "/price_ttl", "/price_cache_clear",
    "/watch", "/unwatch", "/watchlist", "/watch_sens"
]
from config import DATABASE_URL, TELEGRAM_BOT_TOKEN, ASSISTANT_ADMIN_TELEGRAM_ID
from events import BUS

# Define publish function for compatibility
def publish(topic: str, payload: dict):
    """Publish events to the new EventBus system."""
    return BUS.publish(topic, payload)
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

# --- Ops: watchdog + uptime ---
def _admin_chat_id():
    try: 
        return int(os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID", "0")) or None
    except: 
        return None

def _send_admin(msg: str):
    try:
        chat = _admin_chat_id()
        if chat:
            tg_send(chat, msg, preview=True)
    except Exception as e:
        print(f"[watchdog] admin send failed: {e}")

_WD = {"last_alert": 0, "alert_open": False}

def _watchdog_loop():
    import autosell
    while True:
        try:
            st = autosell.status()
            enabled = bool(st.get("enabled"))
            alive = bool(st.get("thread_alive"))
            iv = int(st.get("interval") or 10)
            last_hb = int(st.get("last_heartbeat_ts") or 0)
            age = int(time.time()) - last_hb if last_hb else 1_000_000
            bad = enabled and (not alive or age > max(30, iv*3))
            
            if bad and not _WD["alert_open"]:
                _send_admin(f"⚠️ AutoSell watchdog: thread not healthy\nenabled={enabled} alive={alive} hb_age={age}s interval={iv}s")
                _WD["alert_open"] = True
                _WD["last_alert"] = int(time.time())
            elif not bad and _WD["alert_open"]:
                _send_admin("✅ AutoSell watchdog: recovered")
                _WD["alert_open"] = False
        except Exception as e:
            print(f"[watchdog] loop error: {e}")
        time.sleep(30)

# Start watchdog if enabled
if os.environ.get("FETCH_WATCHDOG", "1") == "1":
    try:
        t = threading.Thread(target=_watchdog_loop, name="watchdog", daemon=True)
        t.start()
        print("[watchdog] started")
    except Exception as e:
        print(f"[watchdog] failed to start: {e}")

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
        return head.lower(), s[len(head):].strip()
    return f"/{m.group(1).lower()}", (m.group(2) or "").strip()

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
        public_commands = ["/help", "/ping", "/info", "/status", "/version", "/test123", "/commands", "/debug_cmd", "/price"]
        
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
        
        # /version — show build stamp
        elif cmd == "/version":
            import json, os
            stamp = []
            try:
                info = json.load(open("build-info.json"))
                stamp.append(f"🏷 Release: {info.get('label','stable')} {info.get('release_ts_utc','')}")
                stamp.append(f"Mode: {info.get('mode','?')}")
                stamp.append(f"Router: {info.get('router_hash','?')}")
            except Exception:
                stamp.append("🏷 No build-info.json found")
            return _reply("\n".join(stamp))
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

        elif cmd == "/price":
            # public: /price <mint>
            a = (args or "").strip()
            if not a:
                return _reply("Usage: /price <mint>")
            try:
                import autosell
                px, src = autosell._get_price(a)
                if px is None:
                    # show simulated so users get *some* answer
                    spx = autosell._sim_price(a)
                    return _reply(f"📈 {a}\nprice: ~${spx:.6f} (sim)\nsource: none (fallback to simulator)")
                return _reply(f"📈 {a}\nprice: ${px:.6f}\nsource: {src}")
            except Exception as e:
                return _reply(f"⚠️ Price lookup failed: {e}")
        
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

        elif cmd == "/autosell_status":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            st = autosell.status()
            lines = [
                "🤖 AutoSell Status",
                f"Enabled: {st.get('enabled')}",
                f"Interval: {st.get('interval')}s",
                f"Rules: {len(st.get('rules', []))}",
                f"Thread alive: {st.get('thread_alive')}",
                f"Ticks: {st.get('ticks')}",
                f"Dry-run: {st.get('dry_run')}",
            ]
            return _reply("\n".join(lines))

        elif cmd == "/autosell_interval":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            arg = (args or "").strip()
            if not arg.isdigit():
                return _reply("Usage: /autosell_interval <seconds>")
            st = autosell.set_interval(int(arg))
            return _reply(f"⏱ Interval set to {st.get('interval')}s.")

        elif cmd == "/autosell_set":
            deny = _require_admin(user)
            if deny: return deny
            import autosell, re
            if not args:
                return _reply("Usage: /autosell_set <MINT> [tp=30] [sl=15] [trail=10] [size=100]")
            parts = args.split()
            mint = parts[0]
            kv = {}
            for tok in parts[1:]:
                m = re.match(r"(?i)^(tp|sl|trail|size)=(\d+)$", tok.strip())
                if m: kv[m.group(1).lower()] = int(m.group(2))
            try:
                rule = autosell.set_rule(mint, **kv)
            except Exception as e:
                return _reply(f"❌ {e}")
            bits = [f"{k}={v}" for k,v in rule.items() if k!="mint"]
            return _reply("✅ Rule saved: " + rule["mint"] + (" " + " ".join(bits) if bits else ""))

        elif cmd == "/autosell_list":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            rules = autosell.list_rules()
            if not rules:
                return _reply("📄 No AutoSell rules yet.")
            lines = ["📄 AutoSell rules:"]
            for r in rules:
                bits = [f"mint={r['mint']}"]
                for k in ("tp","sl","trail","size"):
                    if k in r: bits.append(f"{k}={r[k]}")
                lines.append(" - " + " ".join(bits))
            return _reply("\n".join(lines))

        elif cmd == "/autosell_remove":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            mint = (args or "").strip()
            if not mint:
                return _reply("Usage: /autosell_remove <mint>")
            n = autosell.remove_rule(mint)
            return _reply("🧹 Removed rule" + ("s" if n>1 else "") + f": {n}")

        elif cmd == "/autosell_logs":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            n = 10
            a = (args or "").strip()
            if a.isdigit(): n = max(1, min(int(a), 100))
            lines = autosell.events(n)
            return _reply("📜 Last events:\n" + "\n".join(lines) if lines else "📜 No events yet.")

        elif cmd == "/autosell_dryrun":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            m = (args or "").strip() or None
            lines = autosell.dryrun_eval(m)
            return _reply("\n".join(lines))

        elif cmd == "/autosell_ruleinfo":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            m = (args or "").strip()
            if not m: return _reply("Usage: /autosell_ruleinfo <mint>")
            rules = [r for r in autosell.list_rules() if r.get("mint","").lower()==m.lower()]
            if not rules: return _reply("No such rule.")
            r = rules[0]
            bits = [f"{k}={r[k]}" for k in ("tp","sl","trail","size","ref","peak") if k in r]
            return _reply("🔎 Rule info: " + r["mint"] + (" " + " ".join(bits) if bits else ""))

        elif cmd == "/autosell_save":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            ok = autosell.force_save()
            return _reply("💾 Saved." if ok else "❌ Save failed.")

        elif cmd == "/autosell_load":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            st = autosell.reload()
            return _reply("📥 Loaded. Rules: %s Enabled: %s Interval: %ss" %
                          (len(autosell.list_rules()), st.get("enabled"), st.get("interval")))

        elif cmd == "/autosell_reset":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            autosell.reset()
            return _reply("♻️ AutoSell state cleared (disabled, rules wiped).")

        elif cmd == "/autosell_backup":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            ok = autosell.force_save()
            return _reply("💾 Backup written." if ok else "❌ Backup failed.")

        # test-only to trigger watchdog alert (admin)
        elif cmd == "/autosell_break":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            autosell.test_break()
            return _reply("🧨 AutoSell thread break requested (watchdog should alert if enabled).")

        elif cmd == "/uptime":
            up = int(time.time()) - APP_START_TS
            hrs = up//3600; mins=(up%3600)//60; secs=up%60
            return _reply(f"⏳ Uptime: {hrs}h {mins}m {secs}s")

        elif cmd == "/health":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            st = autosell.status()
            up = int(time.time()) - APP_START_TS
            hb_age = int(time.time()) - int(st.get("last_heartbeat_ts") or 0)
            lines = [
                "🩺 Health",
                f"Uptime: {up}s",
                f"AutoSell: enabled={st.get('enabled')} alive={st.get('thread_alive')} interval={st.get('interval')}s",
                f"HB age: {hb_age}s  ticks={st.get('ticks')}",
                f"Rules: {len(st.get('rules', []))}",
            ]
            return _reply("\n".join(lines))

        elif cmd == "/autosell_events":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            n = 10  # default
            if args and args.isdigit():
                n = max(1, min(int(args), 100))
            events = autosell.events(n)
            if not events:
                return _reply("📜 No AutoSell events yet.")
            lines = [f"📜 Last {len(events)} AutoSell events:"]
            lines.extend(events)
            return _reply("\n".join(lines))

        elif cmd == "/autosell_eval":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            mint = args.strip() if args else None
            results = autosell.dryrun_eval(mint)
            lines = ["🧪 AutoSell DRY-RUN evaluation:"]
            lines.extend(results)
            return _reply("\n".join(lines))

        # --- Admin: price system controls ---
        elif cmd == "/pricesrc":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            cfg = autosell.price_config()
            return _reply("🛠 Price config\n"
                          f"source.dex: {cfg['dex_enabled']}\n"
                          f"ttl: {cfg['ttl']}s\n"
                          f"cache_size: {cfg['cache_size']}")

        elif cmd == "/price_ttl":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            a = (args or "").strip()
            if not (a.isdigit()):
                return _reply("Usage: /price_ttl <seconds>")
            val = autosell.set_price_ttl(int(a))
            return _reply(f"⏱ Price TTL set to {val}s")

        elif cmd == "/price_cache_clear":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            autosell.clear_price_cache()
            return _reply("🧹 Price cache cleared")

        # -------- Watchlist commands (admin) --------
        elif cmd == "/watch":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            m = (args or "").strip()
            if not m: return _reply("Usage: /watch <mint>")
            autosell.watch_add(m)
            return _reply(f"👁️ Watching {m}")

        elif cmd == "/unwatch":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            m = (args or "").strip()
            if not m: return _reply("Usage: /unwatch <mint>")
            n = autosell.watch_remove(m)
            return _reply("✅ Unwatched" if n else "Not found.")

        elif cmd == "/watchlist":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            wl = autosell.watch_list()
            if not wl: return _reply("👁️ Watchlist empty.")
            lines = [f"- {k}" for k in sorted(wl.keys())]
            return _reply("👁️ Watchlist:\n" + "\n".join(lines))

        elif cmd == "/watch_sens":
            deny = _require_admin(user)
            if deny: return deny
            import autosell
            a = (args or "").strip()
            if not a: 
                s = autosell.status().get("watch_sens_pct")
                return _reply(f"👁️ Watch sensitivity: {s:.2f}%")
            try:
                val = autosell.watch_set_sens(float(a))
                return _reply(f"👁️ Watch sensitivity set to {val:.2f}%")
            except Exception:
                return _reply("Usage: /watch_sens <percent>")

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

if __name__ == '__main__':
    # Development mode
    initialize_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
