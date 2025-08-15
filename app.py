"""
Flask Web Application for Mork F.E.T.C.H Bot
Handles Telegram webhooks and provides web interface
"""

import os
import logging
import threading
from flask import Flask, request, jsonify, Response, stream_with_context, render_template_string
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

# --- BEGIN PATCH: imports & singleton (place near other imports at top of app.py) ---
from birdeye import get_scanner, set_scan_mode, birdeye_probe_once, SCAN_INTERVAL
from birdeye_ws import get_ws
from dexscreener_scanner import get_ds_client
from jupiter_scan import JupiterScan
# Solscan Pro import moved to conditional loading

# Initialize components after admin functions are defined
def _init_scanners():
    global SCANNER, ws_client, DS_SCANNER, JUPITER_SCANNER, SOLSCAN_SCANNER, SCANNERS
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
    print(f"[router] ENTER {__file__}:{__name__}")
    msg = update.get("message") or {}
    user = msg.get("from") or {}
    text = msg.get("text") or ""
    cmd, args = _parse_cmd(text)

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
        
        # Temporary AutoSell safety override
        if (text or "").lstrip().startswith("/autosell"):
            return _reply("🛑 AutoSell temporarily disabled while we tidy routing.")
        
        # Basic command routing with streamlined logic
        if not is_command:
            return _reply("Not a command", "ignored")
        
        # Define public commands that don't require admin access
        public_commands = ["/help", "/ping", "/info", "/test123", "/commands", "/debug_cmd"]
        
        # Check if this is a recognized command
        all_commands = public_commands + [
            "/wallet", "/wallet_new", "/wallet_addr", "/wallet_balance", "/wallet_balance_usd", 
            "/wallet_link", "/wallet_deposit_qr", "/wallet_qr", "/wallet_reset", "/wallet_reset_cancel", 
            "/wallet_fullcheck", "/wallet_export", "/solscanstats", "/config_update", "/config_show", 
            "/scanner_on", "/scanner_off", "/threshold", "/watch", "/unwatch", "/watchlist", 
            "/fetch", "/fetch_now", "/autosell_on", "/autosell_off", "/autosell_status", 
            "/autosell_interval", "/autosell_set", "/autosell_list", "/autosell_remove"
        ]
        
        # If command is not recognized, show unknown command message
        if cmd not in all_commands:
            print(f"[route] UNKNOWN raw={repr(text)} parsed_cmd={cmd} args={args}")
            clean = (text or "").replace("\n", " ")
            return _reply(f"❓ Unknown command: {clean}\nUse /help for available commands.")
        
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
        
        # AutoSell Commands - Core functionality
        elif cmd == "/autosell_on":
            if not is_admin:
                return _reply("⛔ Admin only")
            try:
                import autosell
                autosell.enable()
                return _reply("🟢 AutoSell enabled.")
            except Exception as e:
                return _reply(f"❌ AutoSell enable failed: {e}")
        
        elif cmd == "/autosell_off":
            if not is_admin:
                return _reply("⛔ Admin only")
            try:
                import autosell
                autosell.disable()
                return _reply("🔴 AutoSell disabled.")
            except Exception as e:
                return _reply(f"❌ AutoSell disable failed: {e}")
        
        elif cmd == "/autosell_status":
            if not is_admin:
                return _reply("⛔ Admin only")
            try:
                import autosell
                st = autosell.status()
                status_text = "🤖 **AutoSell Status**\n\n" + \
                             f"**Enabled:** {st['enabled']}\n" + \
                             f"**Interval:** {st['interval_sec']}s\n" + \
                             f"**Rules:** {st['rules_count']}\n" + \
                             f"**Thread alive:** {st['thread_alive']}"
                return _reply(status_text)
            except Exception as e:
                return _reply(f"❌ AutoSell status failed: {e}")
        
        elif cmd == "/autosell_interval":
            if not is_admin:
                return _reply("⛔ Admin only")
            try:
                import autosell
                if not args:
                    return _reply("📝 Usage: /autosell_interval <seconds>")
                seconds = int(args.split()[0])
                autosell.set_interval(seconds)
                st = autosell.status()
                return _reply(f"⏱️ AutoSell interval: {st['interval_sec']}s")
            except ValueError:
                return _reply("❌ Invalid number format")
            except Exception as e:
                return _reply(f"❌ AutoSell interval failed: {e}")
        
        elif cmd == "/autosell_set":
            if not is_admin:
                return _reply("⛔ Admin only")
            try:
                import autosell
                parts = args.split()
                if not parts:
                    return _reply("📝 Usage: /autosell_set <MINT> [tp=30] [sl=15] [trail=10] [size=100]")
                mint = parts[0]
                kv = {"tp": None, "sl": None, "trail": None, "size": None}
                for p in parts[1:]:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        try:
                            kv[k.lower()] = float(v)
                        except:
                            pass
                autosell.set_rule(mint, kv["tp"], kv["sl"], kv["trail"], kv["size"])
                return _reply(
                    f"✅ AutoSell set for {mint[:8]}…\n" +
                    f"**TP:** {kv['tp']} **SL:** {kv['sl']} **Trail:** {kv['trail']} **Size:** {kv['size']}"
                )
            except Exception as e:
                return _reply(f"❌ AutoSell set failed: {e}")
        
        elif cmd == "/autosell_list":
            if not is_admin:
                return _reply("⛔ Admin only")
            try:
                import autosell
                rules = autosell.get_rules()
                if not rules:
                    return _reply("🤖 **AutoSell rules:** (none)")
                lines = ["🤖 **AutoSell rules:**\n"]
                for m, r in rules.items():
                    lines.append(
                        f"**{m[:8]}…** tp={r.get('tp_pct')} sl={r.get('sl_pct')} " +
                        f"trail={r.get('trail_pct')} size={r.get('size_pct', 100)}%"
                    )
                return _reply("\n".join(lines))
            except Exception as e:
                return _reply(f"❌ AutoSell list failed: {e}")
        
        elif cmd == "/autosell_remove":
            if not is_admin:
                return _reply("⛔ Admin only")
            try:
                import autosell
                if not args:
                    return _reply("📝 Usage: /autosell_remove <MINT>")
                ok = autosell.remove_rule(args.split()[0])
                return _reply("🗑️ AutoSell rule removed." if ok else "ℹ️ No rule found.")
            except Exception as e:
                return _reply(f"❌ AutoSell remove failed: {e}")
        
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
            evt = _notification_queue.get(timeout=30)
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
    """New webhook endpoint to bypass deployment caching issues - FORCE REFRESH"""
    return webhook()

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

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates with comprehensive logging - Fully standalone operation"""
    # ULTRA BASIC DEBUG - First line of function
    import time
    import os  # Import locally to avoid scoping issues
    timestamp = time.time()
    print(f"[WEBHOOK-DEBUG-{timestamp}] Function entry - PID {os.getpid()}")
    app.logger.info(f"[WEBHOOK-ULTRA-ENTRY] Function entry - PID {os.getpid()} timestamp={timestamp}")
    
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
        
        if update_data.get('message'):
            msg_text = update_data['message'].get('text', '')
            user_id = update_data['message'].get('from', {}).get('id', '')
            logger.info(f"[WEBHOOK] Processing command: {msg_text} from user {user_id}")
            
            # ULTRA DEBUG: Track /solscanstats at the earliest possible point
            if msg_text and msg_text.strip() == "/solscanstats":
                logger.info(f"[WEBHOOK-ULTRA-DEBUG] /solscanstats detected at entry! user_id={user_id}")
                # Add SCANNERS registry debugging for /solscanstats
                try:
                    logger.info("[WEBHOOK][SOLSCAN] pid=%s keys=%s has_solscan=%s",
                               os.getpid(), list(SCANNERS.keys()), "solscan" in SCANNERS)
                except Exception:
                    pass
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
                
                # Simple in-memory deduplication (last 100 updates)
                if not hasattr(handle_update, "_processed_updates"):
                    handle_update._processed_updates = set()
                
                if update_hash in handle_update._processed_updates:
                    logger.info(f"[WEBHOOK] Duplicate update skipped: {update_hash}")
                    return {"status": "duplicate", "handled": True}
                
                # Add to processed set (keep only last 100)
                handle_update._processed_updates.add(update_hash)
                if len(handle_update._processed_updates) > 100:
                    handle_update._processed_updates = set(list(handle_update._processed_updates)[-100:])
                
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
                    chat_id = msg.get('chat', {}).get('id')
                    if chat_id:
                        send_telegram_safe(BOT_TOKEN, chat_id, out)
                    
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
                return jsonify({"status": "ok"})
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
        from eventbus import get_recent_events
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
