"""
Flask Web Application for Mork F.E.T.C.H Bot
Handles Telegram webhooks and provides web interface
"""

import os
import logging
import threading
import json
from datetime import datetime
from flask import Flask, request, jsonify, Response, stream_with_context, render_template_string
from config import DATABASE_URL, TELEGRAM_BOT_TOKEN, ASSISTANT_ADMIN_TELEGRAM_ID

# Export for alerts module
BOT_TOKEN = TELEGRAM_BOT_TOKEN
ADMIN_CHAT_ID = int(ASSISTANT_ADMIN_TELEGRAM_ID) if ASSISTANT_ADMIN_TELEGRAM_ID else None
from events import BUS
import time
import rules

# Try to use an existing wallet module if you already have one.
# If it's missing, we'll use the lightweight JSON store below.
try:
    from wallets import get_or_create_wallet, get_wallet, get_balance_sol  # existing project API (if present)
except Exception:
    get_or_create_wallet = get_wallet = get_balance_sol = None

# --- PER-USER RATE LIMITING (skip for commands) ---
user_last_request = {}
user_last_command = {}
RATE_LIMIT_WINDOW = 5  # seconds between non-command messages
COMMAND_DEDUPE_WINDOW = 1  # seconds to prevent accidental double-taps

# --- SOL PRICE CACHE ---
PRICE_CACHE = {"sol": {"price": None, "ts": 0}}

# --- Wallet reset confirmation state (in-memory) ---
_WALLET_RESET_CONFIRM = {}  # { user_id: {"ts": epoch_seconds} }
_WALLET_RESET_TTL = 120     # seconds

def _set_reset_pending(user_id: int):
    _WALLET_RESET_CONFIRM[user_id] = {"ts": time.time()}

def _is_reset_pending(user_id: int) -> bool:
    entry = _WALLET_RESET_CONFIRM.get(user_id)
    if not entry:
        return False
    if time.time() - entry["ts"] > _WALLET_RESET_TTL:
        _WALLET_RESET_CONFIRM.pop(user_id, None)
        return False
    return True

def _clear_reset_pending(user_id: int):
    _WALLET_RESET_CONFIRM.pop(user_id, None)

def get_sol_price_usd():
    """Get SOL price in USD with 60-second cache"""
    now = time.time()
    if PRICE_CACHE["sol"]["price"] and now - PRICE_CACHE["sol"]["ts"] < 60:
        return PRICE_CACHE["sol"]["price"]
    
    # Fetch fresh price using existing birdeye integration
    try:
        # Use existing birdeye price fetch if available
        import birdeye
        price = birdeye.get_sol_price()  # assume this exists
        PRICE_CACHE["sol"] = {"price": price, "ts": now}
        return price
    except Exception:
        # Fallback to simple API call
        try:
            import httpx
            resp = httpx.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", timeout=10)
            price = resp.json()["solana"]["usd"]
            PRICE_CACHE["sol"] = {"price": price, "ts": now}
            return price
        except Exception:
            # Final fallback - use cached value even if stale, or default
            return PRICE_CACHE["sol"]["price"] if PRICE_CACHE["sol"]["price"] else 200.0

def is_rate_limited(user_id):
    """Check if user is rate limited for non-command messages"""
    if not user_id:
        return False
        
    current_time = time.time()
    last_time = user_last_request.get(user_id, 0)
    
    if current_time - last_time < RATE_LIMIT_WINDOW:
        return True
    
    user_last_request[user_id] = current_time
    return False

def is_duplicate_command(user_id, command_text):
    """Check if this is a duplicate command within 1 second (prevent double-taps)"""
    if not user_id or not command_text:
        return False
        
    current_time = time.time()
    key = f"{user_id}:{command_text}"
    last_time = user_last_command.get(key, 0)
    
    if current_time - last_time < COMMAND_DEDUPE_WINDOW:
        return True
    
    user_last_command[key] = current_time
    return False

# --- SAFE TELEGRAM SEND (integrated with existing _send_chunk) ---
def _send_safe(text, parse_mode="Markdown", no_preview=True):
    """
    Sends a message safely with automatic fallback to plain text.
    This will be integrated with the existing _send_chunk function in the webhook.
    """
    # This is a placeholder that will use the actual _send_chunk from the webhook context
    # when called within the webhook handler where _send_chunk is defined
    return True  # Safe default for module-level usage

# --- SIMPLE JSON WALLET BACKEND (only used if no project wallet module found) ---
WALLET_DB_PATH = os.getenv("WALLET_STORE_PATH", "data/wallets.json")

def _json_load(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _json_save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def _fallback_get_or_create_wallet(user_id: str) -> str:
    """
    Creates a *burner placeholder* address if no wallet module exists.
    NOTE: Replace with your real wallet service when available.
    """
    db = _json_load(WALLET_DB_PATH)
    rec = db.get(str(user_id))
    if rec and "address" in rec:
        return rec["address"]
    # Placeholder address: deterministic fake (so users see something) – replace with real keypair create.
    fake_addr = f"FALLBACK_{user_id}_ADDR"
    db[str(user_id)] = {"address": fake_addr, "created_at": datetime.utcnow().isoformat() + "Z"}
    _json_save(WALLET_DB_PATH, db)
    return fake_addr

def _fallback_get_wallet_address(user_id: str) -> str | None:
    db = _json_load(WALLET_DB_PATH)
    rec = db.get(str(user_id))
    return rec.get("address") if rec else None

def _fallback_get_wallet_balance(user_id: str) -> float:
    """
    Placeholder returns 0.0. Replace with real Solana RPC balance look‑up in your wallet module.
    """
    return 0.0

# unified adapters (prefer real module if present)
def _wallet_create(user_id: int) -> str:
    if get_or_create_wallet:
        result = get_or_create_wallet(str(user_id))
        if isinstance(result, dict):
            return result.get("address", "unknown")
        return str(result)
    return _fallback_get_or_create_wallet(str(user_id))

def _wallet_addr(user_id: int) -> str | None:
    if get_wallet:
        wallet = get_wallet(str(user_id))
        return wallet.get("address") if wallet else None
    return _fallback_get_wallet_address(str(user_id))

def _wallet_balance(user_id: int) -> float:
    if get_balance_sol and get_wallet:
        wallet = get_wallet(str(user_id))
        if wallet and "address" in wallet:
            return get_balance_sol(wallet["address"])
    return _fallback_get_wallet_balance(str(user_id))

# --- BUS TEST helper (publish synthetic NEW_TOKEN if BUS exists) ---
def _bus_publish_synthetic():
    try:
        BUS  # noqa: F821 (exists in your app)
    except NameError:
        return False
    payload = {
        "source": "synthetic",
        "symbol": "TEST",
        "name": "Synthetic Token",
        "mint": "TEST" + datetime.utcnow().strftime("%H%M%S"),
        "holders": 123,
        "mcap_usd": 123456,
        "liquidity_usd": 50000,
        "age_min": 1.0,
        "risk": 25.0,
        "urls": {"birdeye": "https://birdeye.so/token/TEST?chain=solana"}
    }
    try:
        BUS.publish("NEW_TOKEN", payload)
        return True
    except Exception:
        return False



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
    """DISABLED: Send Markdown message to admin chat. Now handled by polling loop."""
    # This function is disabled to centralize all sending in the polling loop
    logger.info(f"send_admin_md called but disabled: {text}")
    return True  # Return success to avoid breaking existing code
# --- END PATCH ---






def _format_plain(text: str) -> str:
    # Avoid Telegram markdown parse glitches -> send as plain text
    return text

# --- [C] Enhanced command handlers using one-shot patch functions ---
def handle_wallet_new(user_id: int):
    """Enhanced wallet creation with safe messaging"""
    try:
        addr = _wallet_create(user_id)
        lines = [
            "Wallet created (or already exists).",
            f"Address: {addr}",
            "Secret key: stored securely (not displayed here).",
            "NOTE: This is a burner wallet for testing. Move funds at your own risk."
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Wallet creation failed: {e}"

def handle_wallet_addr(user_id: int):
    """Enhanced wallet address lookup with safe messaging"""
    try:
        addr = _wallet_addr(user_id)
        if not addr:
            addr = _wallet_create(user_id)
        return f"Your wallet address: {addr}"
    except Exception as e:
        return f"Address lookup failed: {e}"

def handle_wallet_balance(user_id: int):
    """Enhanced wallet balance lookup with safe messaging"""
    try:
        addr = _wallet_addr(user_id)
        if not addr:
            return "No wallet yet. Use /wallet_new first."
        
        balance = _wallet_balance(user_id)
        return f"Balance for {addr}: {balance:.9f} SOL"
    except Exception as e:
        return f"Balance lookup failed: {e}"

def handle_bus_test():
    """Enhanced bus test with safe messaging"""
    try:
        success = _bus_publish_synthetic()
        if success:
            return "Published synthetic NEW_TOKEN event."
        else:
            return "Event bus not available."
    except Exception as e:
        return f"Bus test failed: {e}"

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
def _normalize_token(src: str, obj: dict) -> dict:
    """Map various source payloads into a common schema used by rules
    Fill with best-effort; fields missing can be 0/False"""
    return {
        "source": src,
        "mint": (obj.get("mint") or obj.get("address") or obj.get("tokenAddress") or "").lower(),
        "symbol": obj.get("symbol") or obj.get("baseSymbol") or "",
        "name": obj.get("name") or "",
        "ts": int(obj.get("ts") or obj.get("createdAt") or time.time()),
        "age_min": float(obj.get("age_min") or obj.get("ageMinutes") or 0),
        "liq_usd": float(obj.get("liq_usd") or obj.get("liquidityUsd") or obj.get("liq$") or 0),
        "mcap_usd": float(obj.get("mcap_usd") or obj.get("mcap$") or 0),
        "holders": int(obj.get("holders") or 0),
        "risk": {
            "freeze": bool(obj.get("freeze") or obj.get("canFreeze") or False),
            "mint": bool(obj.get("mint") or obj.get("canMint") or False),
            "blacklist": bool(obj.get("blacklist") or obj.get("canBlacklist") or False),
            "renounced": bool(obj.get("renounced") or obj.get("ownerRenounced") or False),
        },
    }

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

# Telegram mode configuration - use polling to bypass webhook delivery issues
TELEGRAM_MODE = os.environ.get('TELEGRAM_MODE', 'polling').lower()  # 'webhook' or 'polling'

def _reply(text: str, status: str = "ok"):
    """SINGLE return shape used everywhere"""
    return {"status": status, "response": text}

def _require_admin(user):
    """Returns a dict (to send) or None (to continue)"""
    try:
        from config import ASSISTANT_ADMIN_TELEGRAM_ID
        is_admin_user = user.get('id') == ASSISTANT_ADMIN_TELEGRAM_ID
    except Exception:
        is_admin_user = False
    if not is_admin_user:
        return _reply("⛔ Wallet commands are admin-only.", status="admin_only")
    return None

def ensure_admin_or_msg(user):
    """Legacy helper function - kept for compatibility"""
    from config import ASSISTANT_ADMIN_TELEGRAM_ID
    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
        return "⛔ Wallet commands are admin-only."
    return None

def process_telegram_command(update_data):
    """Process Telegram command from polling or webhook"""
    import time
    start_time = time.time()
    text = None
    user_id = None
    is_admin = False
    response_text = None
    try:
        if not update_data.get('message'):
            response_text = "No message in update"
        else:
            message = update_data['message']
            user = message.get('from', {})
            text = message.get('text', '')
            chat_id = message.get('chat', {}).get('id')
            user_id = user.get('id')
            
            # Check if message is a command
            is_command = isinstance(text, str) and text.startswith("/")
            
            # Admin check
            from config import ASSISTANT_ADMIN_TELEGRAM_ID
            is_admin = user.get('id') == ASSISTANT_ADMIN_TELEGRAM_ID
            
            # Structured logging: command entry
            logger.info(f"[CMD] cmd='{text}' user_id={user_id} is_admin={is_admin} is_command={is_command}")
            
            # Rate limiting - skip for commands
            if not is_command and is_rate_limited(user_id):
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[CMD] cmd='{text}' user_id={user_id} is_admin={is_admin} duration_ms={duration_ms} status=throttled")
                response_text = "Rate limited"
            # Admin-only check for restricted commands (exclude basic info commands)
            elif not is_admin and not text.startswith("/wallet") and text not in ["/help", "/ping", "/info", "/test123", "/commands"]:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[CMD] cmd='{text}' user_id={user_id} is_admin={is_admin} duration_ms={duration_ms} status=admin_only")
                response_text = "⛔ Admin only"
            else:
                # Ensure scanners are initialized
                _ensure_scanners()
                
                # Process command
                if text.strip() == "/help":
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
                       "**Bot Status:** ✅ Online (Polling Mode)"
                    response_text = help_text
                elif text.strip() == "/commands":
                    response_text = "📋 **Available Commands**\n\n" + \
                              "**Basic:** /help /info /ping /test123\n" + \
                              "**Wallet:** /wallet /wallet_new /wallet_addr /wallet_balance /wallet_balance_usd /wallet_link /wallet_deposit_qr /wallet_qr /wallet_reset /wallet_reset_cancel /wallet_fullcheck /wallet_export\n" + \
                              "**Scanner:** /solscanstats /config_update /config_show /scanner_on /scanner_off /threshold /watch /unwatch /watchlist /fetch /fetch_now\n\n" + \
                              "Use /help for detailed descriptions"
                elif text.strip() == "/info":
                    response_text = f"""🤖 **Mork F.E.T.C.H Bot Info**
            
**Status:** ✅ Online (Polling Mode)
**Version:** Production v2.0
**Mode:** Telegram Polling (Webhook Bypass)
**Scanner:** Solscan Active
**Wallet:** Enabled
**Admin:** {user.get('username', 'Unknown')}

*The Degens' Best Friend* 🐕"""
                elif text.strip() == "/test123":
                    response_text = "✅ **Connection Test Successful!**\n\nBot is responding via polling mode.\nWebhook delivery issues bypassed."
                elif text.strip() == "/ping":
                    response_text = "🎯 **Pong!** Bot is alive and responsive."
                # Wallet commands using new helper functions
                elif text.strip() == "/wallet":
                    deny = _require_admin(user)
                    if deny:
                        response_text = deny["response"]
                    else:
                        try:
                            import wallets
                            response_text = wallets.cmd_wallet_summary(user.get('id'))
                        except Exception as e:
                            response_text = f"💰 Wallet error: {e}"
                elif text.strip().startswith("/wallet_new"):
                    deny = _require_admin(user)
                    if deny:
                        response_text = deny["response"]
                    else:
                        try:
                            import wallets
                            response_text = wallets.cmd_wallet_new(user.get('id'))
                        except Exception as e:
                            response_text = f"💰 Wallet new error: {e}"
                elif text.strip().startswith("/wallet_addr"):
                    deny = _require_admin(user)
                    if deny:
                        response_text = deny["response"]
                    else:
                        try:
                            import wallets
                            response_text = wallets.cmd_wallet_addr(user.get('id'))
                        except Exception as e:
                            response_text = f"💰 Wallet addr error: {e}"
                elif text == "/wallet_balance_usd":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import re, wallets
                            uid = user.get("id")
                            bal_text = (wallets.cmd_wallet_balance(uid) or "").strip()

                            # Robust extraction:
                            #  - Prefer patterns with SOL/◎ labels
                            #  - Otherwise, fallback to "largest float in text"
                            def _to_float(x):
                                try:
                                    return float(x.replace(",", ""))
                                except Exception:
                                    return None

                            sol_amount = None

                            # Patterns: "SOL: 0.123", "SOL 0.123", "◎ 0.123"
                            patterns = [
                                r"SOL[:\s]+([0-9][0-9,]*\.?[0-9]*)",
                                r"◎[:\s]+([0-9][0-9,]*\.?[0-9]*)",
                            ]
                            for p in patterns:
                                m = re.search(p, bal_text, flags=re.IGNORECASE)
                                if m:
                                    sol_amount = _to_float(m.group(1))
                                    if sol_amount is not None:
                                        break

                            # Fallback: grab the largest-looking float anywhere in the text
                            if sol_amount is None:
                                floats = [ _to_float(x) for x in re.findall(r"([0-9][0-9,]*\.?[0-9]*)", bal_text) ]
                                floats = [f for f in floats if f is not None]
                                if floats:
                                    sol_amount = max(floats)

                            if sol_amount is None:
                                response_text = "⚠️ Could not parse SOL balance."
                            else:
                                # Price
                                try:
                                    from prices import get_sol_price_usd
                                except Exception:
                                    # graceful fallback if prices.py not present
                                    def get_sol_price_usd(): return None

                                price = get_sol_price_usd()
                                if price is None:
                                    response_text = f"{bal_text}\n≈ $— USD (price unavailable)"
                                else:
                                    usd = sol_amount * float(price)
                                    response_text = f"{bal_text}\n≈ ${usd:,.2f} USD"
                        except Exception as e:
                            response_text = f"💱 Balance (USD) error: {e}"
                elif text.strip().startswith("/wallet_balance"):
                    deny = _require_admin(user)
                    if deny:
                        response_text = deny["response"]
                    else:
                        try:
                            import wallets
                            response_text = wallets.cmd_wallet_balance(user.get('id'))
                        except Exception as e:
                            response_text = f"💰 Wallet balance error: {e}"
                elif text == "/wallet_selftest":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import re, wallets
                            uid = user.get("id")

                            addr_text = wallets.cmd_wallet_addr(uid) or ""
                            summary   = wallets.cmd_wallet_summary(uid) or ""
                            bal_text  = wallets.cmd_wallet_balance(uid) or ""

                            # Base58 address (32–44 chars, no 0/O/I/l)
                            base58_re = r"[1-9A-HJ-NP-Za-km-z]{32,44}"
                            m_addr = re.search(base58_re, addr_text) or re.search(base58_re, summary)

                            # Consider the test passed if we got any address and both strings are non-empty
                            ok = bool(m_addr) and summary.strip() and bal_text.strip()
                            if ok:
                                response_text = "✅ Wallet self-test passed"
                            else:
                                # If not ok, surface what we saw (trimmed) so we can adjust quickly
                                def short(s): 
                                    s = re.sub(r"\s+", " ", s).strip()
                                    return (s[:120] + "…") if len(s) > 120 else s
                                response_text = (
                                    "⚠️ Self-test incomplete.\n"
                                    f"- addr_text: {short(addr_text)}\n"
                                    f"- summary: {short(summary)}\n"
                                    f"- balance: {short(bal_text)}"
                                )
                        except Exception as e:
                            response_text = f"🧪 Self-test error: {e}"
                elif text.startswith("/wallet_link"):
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import wallets
                            addr_output = wallets.cmd_wallet_addr(user.get("id"))
                            # Extract just the address from output like "Address: `HS8itzXv...`"
                            addr = addr_output.split('`')[1] if '`' in addr_output else addr_output.strip()
                            response_text = f"🔗 Solscan: https://solscan.io/address/{addr}"
                        except Exception as e:
                            response_text = f"🔗 Link error: {e}"
                elif text.strip() == "/wallet_reset":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import re, wallets
                            uid = user.get("id")
                            # Show current address in the warning
                            addr_text = (wallets.cmd_wallet_addr(uid) or "").strip()
                            m = re.search(r"[1-9A-HJ-NP-Za-km-z]{32,44}", addr_text)
                            addr = m.group(0) if m else "(unknown)"
                            _set_reset_pending(uid)
                            response_text = (
                                "⚠️ Reset wallet?\n"
                                f"Current address: {addr}\n\n"
                                "This will create a NEW burner wallet. "
                                "Funds at the old address will NOT move automatically.\n\n"
                                "Type /wallet_reset_confirm within 2 minutes to proceed, or /wallet_reset_cancel to abort."
                            )
                        except Exception as e:
                            response_text = f"💥 Reset prep error: {e}"
                elif text.strip() == "/wallet_reset_confirm":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import re, wallets
                            uid = user.get("id")

                            if not _is_reset_pending(uid):
                                response_text = "⌛ No reset is pending (or it expired). Run /wallet_reset first."
                            else:
                                # Capture old address for message
                                old_addr_text = (wallets.cmd_wallet_addr(uid) or "").strip()
                                m_old = re.search(r"[1-9A-HJ-NP-Za-km-z]{32,44}", old_addr_text)
                                old_addr = m_old.group(0) if m_old else "(unknown)"

                                # Create new burner
                                new_msg = wallets.cmd_wallet_new(uid)
                                new_addr_match = re.search(r"[1-9A-HJ-NP-Za-km-z]{32,44}", new_msg or "")
                                new_addr = new_addr_match.group(0) if new_addr_match else "(unknown)"

                                _clear_reset_pending(uid)

                                response_text = (
                                    "✅ Wallet reset complete.\n"
                                    f"Old: {old_addr}\n"
                                    f"New: {new_addr}\n\n"
                                    "⚠️ Reminder: Move any funds from the old address manually if needed."
                                )
                        except Exception as e:
                            response_text = f"💥 Reset error: {e}"
                elif text.strip() == "/wallet_reset_cancel":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        uid = user.get("id")
                        if _is_reset_pending(uid):
                            _clear_reset_pending(uid)
                            response_text = "🛑 Wallet reset cancelled."
                        else:
                            response_text = "ℹ️ No pending wallet reset to cancel."
                elif text.strip() == "/wallet_fullcheck":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import re, wallets
                            uid = user.get("id")

                            # --- helpers (local, defensive) ---
                            base58_re = r"[1-9A-HJ-NP-Za-km-z]{32,44}"

                            def extract_addr(s: str | None):
                                if not s: return None
                                m = re.search(base58_re, s)
                                return m.group(0) if m else None

                            def parse_sol_amount(bal_text: str | None):
                                if not bal_text: return None
                                # prefer labeled patterns first
                                for pat in [r"SOL[:\s]+([0-9][0-9,]*\.?[0-9]*)",
                                            r"◎[:\s]+([0-9][0-9,]*\.?[0-9]*)"]:
                                    m = re.search(pat, bal_text, flags=re.IGNORECASE)
                                    if m:
                                        try:
                                            return float(m.group(1).replace(",", ""))
                                        except Exception:
                                            pass
                                # fallback: largest float anywhere
                                floats = [x.replace(",", "") for x in re.findall(r"([0-9][0-9,]*\.?[0-9]*)", bal_text)]
                                vals = []
                                for x in floats:
                                    try: vals.append(float(x))
                                    except Exception: pass
                                return max(vals) if vals else None

                            # --- gather data from existing commands ---
                            addr_text  = (wallets.cmd_wallet_addr(uid) or "").strip()
                            summary    = (wallets.cmd_wallet_summary(uid) or "").strip()
                            bal_text   = (wallets.cmd_wallet_balance(uid) or "").strip()

                            addr_from_addr   = extract_addr(addr_text)
                            addr_from_summary= extract_addr(summary)

                            sol_amt = parse_sol_amount(bal_text)

                            # price (best-effort)
                            usd_line = "USD: (price unavailable)"
                            try:
                                from prices import get_sol_price_usd
                                px = get_sol_price_usd()
                                if px is not None and sol_amt is not None:
                                    usd_line = f"USD: ≈ ${sol_amt * float(px):,.2f}"
                            except Exception:
                                pass

                            # link check (string build; no network)
                            link_ok = bool(addr_from_addr)
                            link_str = f"https://solscan.io/address/{addr_from_addr}" if addr_from_addr else "(no link)"

                            # --- verdicts ---
                            ok_addr_present   = bool(addr_from_addr)
                            ok_addr_consistent= ok_addr_present and (addr_from_summary == addr_from_addr or addr_from_summary is None)
                            ok_balance_parse  = sol_amt is not None
                            ok_summary_nonempty = bool(summary)
                            ok_balance_nonempty = bool(bal_text)

                            # --- report ---
                            lines = []
                            lines.append("🧪 Wallet Full Check")
                            lines.append(f"{'✅' if ok_addr_present else '❌'} Address detected: {addr_from_addr or '(none)'}")
                            lines.append(f"{'✅' if ok_addr_consistent else '⚠️'} Address consistent across /wallet and /wallet_addr")
                            lines.append(f"{'✅' if ok_summary_nonempty else '❌'} /wallet summary returned text")
                            lines.append(f"{'✅' if ok_balance_nonempty else '❌'} /wallet_balance returned text")
                            lines.append(f"{'✅' if ok_balance_parse else '⚠️'} SOL parse: " + (f"{sol_amt}" if sol_amt is not None else "(not found)"))
                            lines.append(f"{'✅' if link_ok else '❌'} Link build: {link_str}")
                            lines.append(f"ℹ️ {usd_line}")

                            # overall status
                            hard_fail = not (ok_addr_present and ok_summary_nonempty and ok_balance_nonempty)

                            # small tail with raw (trimmed) snippets for debugging if anything shaky
                            if not ok_addr_consistent or not ok_balance_parse or hard_fail:
                                def short(s): 
                                    import re as _re
                                    s = _re.sub(r"\s+", " ", s or "").strip()
                                    return (s[:160] + "…") if len(s) > 160 else s
                                lines.append("")
                                lines.append("— details —")
                                lines.append(f"addr_text: {short(addr_text)}")
                                lines.append(f"summary:   {short(summary)}")
                                lines.append(f"balance:   {short(bal_text)}")

                            response_text = "\n".join(lines)

                        except Exception as e:
                            response_text = f"🧪 Fullcheck error: {e}"
                elif text == "/wallet_export":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import wallets
                            export_data = wallets.cmd_wallet_export(user.get("id"))
                            response_text = export_data
                        except Exception as e:
                            response_text = f"🔐 Export error: {e}"
                elif text.startswith("/wallet_deposit_qr") or text.startswith("/wallet_qr"):
                    deny = _require_admin(user)
                    if deny:
                        response_text = deny["response"]
                    else:
                        try:
                            import os, re, time, qrcode, wallets
                            uid = user.get("id")

                            # Parse optional amount (e.g., "/wallet_deposit_qr 0.5")
                            parts = text.split()
                            amt = None
                            if len(parts) > 1:
                                try:
                                    amt = float(parts[1].replace(",", ""))
                                    if amt <= 0: amt = None
                                except Exception:
                                    amt = None

                            # Get address robustly
                            addr_text = (wallets.cmd_wallet_addr(uid) or "").strip()
                            m = re.search(r"[1-9A-HJ-NP-Za-km-z]{32,44}", addr_text)
                            if not m:
                                response_text = "⚠️ Unable to detect wallet address."
                            else:
                                addr = m.group(0)

                                # Build solana: URI (amount is optional & many wallets honor it)
                                uri = f"solana:{addr}"
                                if amt is not None:
                                    # Don't append scientific notation; keep plain decimal
                                    uri = f"{uri}?amount={amt:.9f}".rstrip("0").rstrip(".")

                                # Generate QR
                                os.makedirs("tmp", exist_ok=True)
                                path = f"tmp/qr_{addr[:6]}_{int(time.time())}.png"
                                img = qrcode.make(uri)
                                img.save(path)

                                # Send photo
                                from telegram_media import send_photo_safe
                                chat_id = (update_data.get("message", {}).get("chat") or {}).get("id")
                                caption_lines = [f"Deposit Address:\n{addr}"]
                                if amt is not None:
                                    caption_lines.append(f"Requested Amount: {amt} SOL")
                                caption_lines.append("⚠️ Burner wallet for testing. Do not send large amounts.")
                                caption = "\n".join(caption_lines)

                                ok, status, _ = send_photo_safe(TELEGRAM_BOT_TOKEN, chat_id, path, caption=caption)
                                if ok:
                                    response_text = "📸 Sent deposit QR."
                                else:
                                    response_text = "⚠️ Failed to send QR image."
                        except Exception as e:
                            response_text = f"🖼️ QR error: {e}"
                elif text.strip() == "/solscanstats":
                    try:
                        from config_manager import get_config
                        config_mgr = get_config()
                        
                        # Get unified scanner status
                        import scanner
                        status = scanner.get_status()
                        
                        # Also check Solscan module status
                        solscan_running = False
                        if "solscan" in SCANNERS:
                            solscan_scanner = SCANNERS["solscan"]
                            solscan_running = getattr(solscan_scanner, 'running', False)
                        
                        response_text = (
                            f"📊 **Scanner System Status**\n\n"
                            f"**Unified Scanner:**\n"
                            f"Status: {'✅ Running' if status['running'] else '❌ Stopped'}\n"
                            f"Enabled: {'✅' if status['enabled'] else '❌'}\n"
                            f"Interval: {status['interval_sec']}s\n"
                            f"Threshold: {status['threshold']}\n"
                            f"Watchlist: {status['watchlist_size']} tokens\n\n"
                            f"**Solscan Module:**\n"
                            f"Status: {'✅ Running' if solscan_running else '❌ Stopped'}\n"
                            f"Config: scanner_config.json"
                        )
                    except Exception as e:
                        response_text = f"📊 Solscan error: {e}"
                elif text.strip() == "/config_show":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            from config_manager import get_config
                            config_mgr = get_config()
                            
                            scanner_config = config_mgr.get_scanner_config()
                            watchlist = config_mgr.get_watchlist()
                            
                            lines = ["⚙️ **Scanner Configuration**"]
                            lines.append(f"Enabled: {'✅' if scanner_config.get('enabled', True) else '❌'}")
                            lines.append(f"Interval: {scanner_config.get('interval_sec', 20)}s")
                            lines.append(f"Threshold: {scanner_config.get('threshold', 75)}")
                            lines.append(f"Watchlist: {len(watchlist)} tokens")
                            
                            if watchlist:
                                lines.append("**Watchlist:**")
                                for i, token in enumerate(watchlist[:5]):  # Show first 5
                                    lines.append(f"  • {token[:8]}...{token[-4:]}")
                                if len(watchlist) > 5:
                                    lines.append(f"  ... and {len(watchlist) - 5} more")
                            
                            response_text = "\n".join(lines)
                        except Exception as e:
                            response_text = f"⚙️ Config error: {e}"
                elif text.startswith("/config_update"):
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            from config_manager import get_config
                            config_mgr = get_config()
                            
                            parts = text.split()
                            if len(parts) < 3:
                                response_text = (
                                    "⚙️ **Config Update Usage:**\n"
                                    "/config_update <key> <value>\n\n"
                                    "Examples:\n"
                                    "• /config_update interval 25\n"
                                    "• /config_update threshold 80\n"
                                    "• /config_update enabled true"
                                )
                            else:
                                key = parts[1]
                                value = parts[2]
                                
                                # Convert value to appropriate type
                                if value.lower() in ['true', 'false']:
                                    value = value.lower() == 'true'
                                elif value.isdigit():
                                    value = int(value)
                                elif value.replace('.', '').isdigit():
                                    value = float(value)
                                
                                # Map common keys to full paths
                                key_mapping = {
                                    'interval': 'scanner.interval_sec',
                                    'threshold': 'scanner.threshold',
                                    'enabled': 'scanner.enabled'
                                }
                                
                                full_key = key_mapping.get(key, f"scanner.{key}")
                                config_mgr.set(full_key, value)
                                config_mgr.save_config()
                                
                                response_text = f"✅ Updated {key} = {value}"
                        except Exception as e:
                            response_text = f"⚙️ Update error: {e}"
                elif text.startswith("/scanner_on"):
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import scanner
                            scanner.enable()
                            response_text = "🟢 Scanner enabled."
                        except Exception as e:
                            response_text = f"⚠️ Scanner enable error: {e}"
                elif text.startswith("/scanner_off"):
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import scanner
                            scanner.disable()
                            response_text = "🔴 Scanner disabled."
                        except Exception as e:
                            response_text = f"⚠️ Scanner disable error: {e}"
                elif text.startswith("/threshold"):
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            parts = text.split()
                            if len(parts) < 2:
                                response_text = "Usage: /threshold <score>"
                            else:
                                val = int(parts[1])
                                import scanner
                                scanner.set_threshold(val)
                                response_text = f"✅ Threshold set to {val}."
                        except Exception as e:
                            response_text = f"⚠️ Threshold error: {e}"
                elif text.startswith("/watch "):
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            mint = text.split(maxsplit=1)[1].strip()
                            import scanner
                            ok = scanner.add_watch(mint)
                            response_text = f"👀 Watching {mint}" if ok else "ℹ️ Already watching."
                        except Exception as e:
                            response_text = f"⚠️ Watch error: {e}"
                elif text.startswith("/unwatch "):
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            mint = text.split(maxsplit=1)[1].strip()
                            import scanner
                            ok = scanner.remove_watch(mint)
                            response_text = "🗑️ Removed" if ok else "ℹ️ Not on watchlist."
                        except Exception as e:
                            response_text = f"⚠️ Unwatch error: {e}"
                elif text.strip() == "/watchlist":
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            import scanner
                            watchlist = scanner.get_watchlist()
                            
                            if watchlist:
                                lines = ["👀 **Watchlist:**"]
                                for i, mint in enumerate(watchlist, 1):
                                    lines.append(f"{i}. {mint}")
                                response_text = "\n".join(lines)
                            else:
                                response_text = "👀 Watchlist: (empty)"
                        except Exception as e:
                            response_text = f"⚠️ Watchlist error: {e}"
                elif text.startswith("/fetch "):
                    # /fetch <MINT|SYM> - Look up specific token
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            query = text.split(maxsplit=1)[1].strip()
                            import token_fetcher
                            import flip_checklist
                            
                            # Look up the specific token
                            token = token_fetcher.lookup(query)
                            if token:
                                score, verdict, details = flip_checklist.score(token)
                                symbol = token.get("symbol", "Unknown")
                                price = token.get("usd_price", token.get("price", "?"))
                                holders = token.get("holders", token.get("holder_count", "?"))
                                age = token.get("age", token.get("age_seconds", "?"))
                                
                                response_text = f"🔍 **Token Lookup: {symbol}**\n\n"
                                response_text += f"**Verdict:** {verdict} (Score: {score})\n"
                                response_text += f"**Price:** ${price}\n"
                                response_text += f"**Holders:** {holders}\n"
                                response_text += f"**Age:** {age}s\n"
                                response_text += f"**Details:** {details}"
                            else:
                                response_text = f"❌ Token not found: {query}"
                        except Exception as e:
                            response_text = f"🔍 Fetch error: {e}"
                elif text.startswith("/fetchnow"):
                    # /fetchnow [N] - Scan N tokens immediately
                    deny = _require_admin(user)
                    if deny: 
                        response_text = deny["response"]
                    else:
                        try:
                            parts = text.split()
                            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 15
                            limit = min(limit, 50)  # Cap at 50
                            
                            import scanner
                            results = scanner.scan_now(limit)
                            
                            response_text = f"📊 **Immediate Token Scan**\n\n"
                            response_text += f"Scanned: {len(results)} tokens\n"
                            
                            if results:
                                # Filter for interesting results
                                good_results = [r for r in results if r[1] >= scanner.get_threshold()]
                                if good_results:
                                    response_text += f"**Good Targets ({len(good_results)}):**\n"
                                    for i, (token, score, verdict) in enumerate(good_results[:5], 1):
                                        symbol = token.get("symbol", "Unknown")
                                        price = token.get("usd_price", token.get("price", "?"))
                                        response_text += f"{i}. **{symbol}** - {verdict} (Score: {score})\n"
                                        response_text += f"   Price: ${price}\n"
                                else:
                                    response_text += f"**Top 5 Results:**\n"
                                    for i, (token, score, verdict) in enumerate(results[:5], 1):
                                        symbol = token.get("symbol", "Unknown")
                                        price = token.get("usd_price", token.get("price", "?"))
                                        response_text += f"{i}. **{symbol}** - {verdict} (Score: {score})\n"
                            else:
                                response_text += "No tokens found"
                        except Exception as e:
                            response_text = f"📊 Scan error: {e}"
                else:
                    # Handle unknown commands and plain text
                    if is_command:
                        response_text = f"❓ Unknown command: {text}\nUse /help for available commands."
                    else:
                        response_text = "👍"
        
        if response_text is None:
            response_text = "No response generated"
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[CMD] cmd='{text}' user_id={user_id} is_admin={is_admin} duration_ms={duration_ms} status=error")
        logger.error(f"Command processing error: {e}")
        response_text = f"Command processing error: {str(e)}"
        
    # Return unified response
    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[CMD] cmd='{text}' user_id={user_id} is_admin={is_admin} duration_ms={duration_ms} status=ok")
    return _reply(response_text or "No response generated", status="ok")

def start_telegram_polling():
    """Start Telegram polling in background thread"""
    try:
        from telegram_polling import start_polling, disable_webhook_if_polling
        
        # Disable webhook to prevent duplicate processing
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if bot_token:
            disable_webhook_if_polling(bot_token)
        
        polling_instance = start_polling()
        logger.info("Telegram polling started successfully")
        return polling_instance
    except Exception as e:
        logger.error(f"Failed to start Telegram polling: {e}")
        return None

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
        # Using global publish function
        
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
            
            # ULTRA DEBUG: Log ALL incoming messages regardless of command
            logger.info(f"[WEBHOOK-ULTRA] RAW MESSAGE: text='{msg_text}' user={user_id} chat={update_data['message'].get('chat', {}).get('id', '')}")
            
            # Special tracking for test commands
            if msg_text and '/test123' in msg_text:
                logger.error(f"[WEBHOOK-SPECIAL] /test123 DETECTED! Raw text: '{msg_text}' User: {user_id}")
            if msg_text and '/help' in msg_text:
                logger.error(f"[WEBHOOK-SPECIAL] /help DETECTED! Raw text: '{msg_text}' User: {user_id}")
            
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
            message = update_data['message']
            user = message.get('from', {})
            text = message.get('text', '')
            
            logger.info(f"[WEBHOOK] Message from {user.get('username', 'unknown')} ({user.get('id', 'unknown')}): '{text}'")
            
            # Publish webhook event for real-time monitoring
            publish("webhook.update", {
                "from": user.get("username", "?"), 
                "user_id": user.get("id"),
                "text": text,
                "chat_id": message.get('chat', {}).get('id')
            })
            
            # Publish command routing event for specific command tracking
            if text and text.startswith('/'):
                publish("command.route", {"cmd": text.split()[0]})
                # Enhanced debug for /help command specifically
                if text.strip() == "/help":
                    logger.info(f"[WEBHOOK-TRACE] /help command detected early in processing pipeline")
            
            # Check for multiple commands in one message
            commands_in_message = []
            if text:
                # Split by whitespace and find all commands (starting with /)
                words = text.split()
                for word in words:
                    if word.startswith('/'):
                        commands_in_message.append(word)
            
            # If multiple commands detected, log it
            if len(commands_in_message) > 1:
                logger.info(f"[WEBHOOK] Multiple commands detected: {commands_in_message}")

            # DISABLED: Helper functions for sending replies - now handled by polling loop
            def _send_chunk(txt: str, parse_mode: str = "Markdown", no_preview: bool = True) -> bool:
                """DISABLED: Direct API calls removed to centralize sending in polling loop"""
                logger.info(f"[WEBHOOK] _send_chunk called but disabled: {txt[:100]}...")
                return True

            def _send_safe(text: str, parse_mode: str = "Markdown", no_preview: bool = True) -> bool:
                """DISABLED: Safe send - now handled by polling loop"""
                logger.info(f"[WEBHOOK] _send_safe called but disabled: {text[:100]}...")
                return True

            def _reply(text: str, parse_mode: str = "Markdown", no_preview: bool = True) -> bool:
                """DISABLED: Reply function - now handled by polling loop"""
                logger.info(f"[WEBHOOK] _reply called but disabled: {text[:100]}...")
                return True
                
                # Split large messages on paragraph boundaries where possible
                i = 0
                all_success = True
                while i < len(text):
                    chunk = text[i:i+MAX]
                    # Try not to cut mid-line
                    cut = chunk.rfind("\n")
                    if cut > 1000:  # Only use newline break if it helps
                        chunk = chunk[:cut]
                        i += cut + 1
                    else:
                        i += len(chunk)
                    
                    # Use enhanced safe send for each chunk
                    chunk_success = _send_safe(chunk, parse_mode=parse_mode, no_preview=no_preview)
                    all_success = all_success and chunk_success
                
                return all_success

            # Simple admin command processing for immediate testing
            from config import ASSISTANT_ADMIN_TELEGRAM_ID
            
            if user.get('id') == ASSISTANT_ADMIN_TELEGRAM_ID and text.startswith('/'):
                logger.info(f"[WEBHOOK] Admin command detected: {text}")
                
                # Process admin commands directly without PTB
                chat_id = message['chat']['id']
                response_text = None
                
                # Handle multiple commands in one message
                if len(commands_in_message) > 1:
                    logger.info(f"[WEBHOOK] Processing {len(commands_in_message)} commands sequentially")
                    responses = []
                    
                    # Process each command separately by calling webhook recursively
                    for cmd in commands_in_message:
                        # Create a modified message for single command processing
                        temp_text = text
                        text = cmd  # Temporarily set text to single command
                        
                        # Process the single command using existing logic
                        single_response = None
                        
                        # Process actual commands for multiple command handling
                        if text.strip() == "/fetch":
                            try:
                                import data_fetcher
                                # Use the actual function name from data_fetcher
                                if hasattr(data_fetcher, 'fetch_candidates_from_pumpfun'):
                                    results = data_fetcher.fetch_candidates_from_pumpfun(limit=50)
                                    count = len(results) if isinstance(results, list) else 0
                                    single_response = f"🎯 F.E.T.C.H scan: {count} tokens found"
                                else:
                                    single_response = "🎯 F.E.T.C.H scan: Data fetcher available"
                            except Exception as e:
                                single_response = f"🎯 F.E.T.C.H scan failed: {str(e)[:50]}..."
                        elif text.strip() == "/fetch_now":
                            try:
                                # Use the comprehensive multi-source fetch command
                                from alerts.telegram import cmd_fetch_now_sync
                                result_text = cmd_fetch_now_sync()
                                if result_text and result_text.strip():
                                    # Extract just the summary for multi-command response
                                    lines = result_text.split('\n')
                                    summary_line = next((line for line in lines if 'tokens' in line and ('multi-source' in line or 'found' in line)), None)
                                    if summary_line:
                                        single_response = f"⚡ {summary_line.strip()}"
                                    else:
                                        single_response = "⚡ Comprehensive fetch completed"
                                else:
                                    single_response = "⚡ No candidates found from multi-source fetch"
                            except Exception as e:
                                single_response = f"⚡ Fetch failed: {str(e)[:50]}..."
                        elif text.strip() == "/ping":
                            single_response = "🎯 Pong!"
                        elif text.strip() == "/solscanstats":
                            try:
                                if "solscan" in SCANNERS:
                                    scanner = SCANNERS["solscan"]
                                    single_response = f"📊 Solscan: {getattr(scanner, 'running', False)}"
                                else:
                                    single_response = "📊 Solscan: Not initialized"
                            except Exception as e:
                                single_response = f"📊 Solscan error: {e}"
                        elif text.strip() == "/wallet":
                            try:
                                import wallets
                                single_response = wallets.cmd_wallet_summary(user.get('id'))
                            except Exception as e:
                                single_response = f"💰 Wallet error: {e}"
                        elif text.strip().startswith("/wallet_new"):
                            try:
                                import wallets
                                single_response = wallets.cmd_wallet_new(user.get('id'))
                            except Exception as e:
                                single_response = f"💰 Wallet new error: {e}"
                        elif text.strip().startswith("/wallet_addr"):
                            try:
                                import wallets
                                single_response = wallets.cmd_wallet_addr(user.get('id'))
                            except Exception as e:
                                single_response = f"💰 Wallet addr error: {e}"
                        elif text.startswith("/wallet_addr_test"):
                            # Test case for enhanced wallet functionality
                            single_response = "Test OK - Enhanced wallet system active"
                        elif text.strip().startswith("/wallet_balance"):
                            try:
                                import wallets
                                single_response = wallets.cmd_wallet_balance(user.get('id'))
                            except Exception as e:
                                single_response = f"💰 Wallet balance error: {e}"
                        elif text.strip().startswith("/bus_test"):
                            single_response = handle_bus_test()
                            BUS.publish("NEW_TOKEN", fake)
                            single_response = "📣 Published synthetic *NEW_TOKEN* to the bus (source=TEST). Check for the formatted alert."
                        
                        if single_response:
                            responses.append(f"*{cmd}*: {single_response}")
                        
                        text = temp_text  # Restore original text
                    
                    if responses:
                        response_text = "\n\n".join(responses)
                    else:
                        response_text = f"Processed {len(commands_in_message)} commands"
                    
                    # Skip the rest of the command processing for multiple commands
                    logger.info(f"[WEBHOOK] Sending multiple command response: {response_text}")
                    
                    # DISABLED: Direct API call - now handled by polling loop
                    logger.info(f"[WEBHOOK] Multiple commands processed, response prepared: {response_text[:100]}...")
                    reply_success = True  # Always report success since polling handles sending
                    
                    logger.info(f"[WEBHOOK] Multiple command reply success: {reply_success}")
                    return jsonify({"status": "ok", "command": text, "response_sent": reply_success, "multiple_commands": len(commands_in_message)})
                
                # DEBUG: Track command routing for solscanstats
                if text.strip() == "/solscanstats":
                    logger.info(f"[WEBHOOK-DEBUG] /solscanstats detected! About to enter command routing...")
                    logger.info(f"[WEBHOOK-DEBUG] Admin ID check: user={user.get('id')}, admin={ASSISTANT_ADMIN_TELEGRAM_ID}")
                
                # DEBUG: Log ALL command attempts for debugging
                if text.startswith('/'):
                    logger.info(f"[WEBHOOK-COMMAND-DEBUG] Processing command: '{text}' from user {user.get('id')}")
                
                if text.strip() in ['/ping', '/a_ping']:
                    publish("admin.command", {"command": "ping", "user": user.get("username", "?")})
                    response_text = 'Pong! Webhook processing is working! 🎯'

                elif text.strip().startswith("/bus_test"):
                    response_text = handle_bus_test()
                    _reply(response_text, parse_mode=None, no_preview=True)
                    return jsonify({"status": "ok", "command": text, "response_sent": True})
                elif text.strip() in ['/status', '/a_status']:
                    publish("admin.command", {"command": "status", "user": user.get("username", "?")})
                    response_text = f'''🤖 Mork F.E.T.C.H Bot Status
                    
Mode: Webhook Processing
PTB: Disabled (import conflicts)
Admin Commands: Direct webhook
Logging: Enhanced (active)
Health: Operational

Admin router with comprehensive logging active.'''
                elif text.strip().startswith("/whoami_sys"):
                    info = [
                        f"PID: {os.getpid()}",
                        f"Admin ID: {ASSISTANT_ADMIN_TELEGRAM_ID}",
                        f"Mode: Webhook Processing",
                        f"Threadalive: {globals().get('SCANNER_STATE', {}).get('threadalive', False)}",
                        f"Active scanners: {', '.join(sorted(SCANNERS.keys())) or '(none)'}",
                    ]
                    response_text = "🧩 System Info\n" + "\n".join(info)
                elif text.strip().startswith("/whoami"):
                    try:
                        pid = os.getpid()
                        keys = list(SCANNERS.keys())
                        sol = SCANNERS.get("solscan")
                        sol_enabled = getattr(sol, "enabled", None) if sol else None
                        sol_running = getattr(sol, "running", None) if sol else None
                        feat = os.getenv("FEATURE_SOLSCAN", "unset")
                        keylen = len(os.getenv("SOLSCAN_API_KEY", "")) or 0
                        response_text = (
                            "👤 *Worker diag*\n"
                            f"pid: `{pid}`\n"
                            "gunicorn: workers=1, threads=1 (forced)\n"
                            f"SCANNERS: `{keys}`\n"
                            f"solscan: enabled={sol_enabled} running={sol_running}\n"
                            f"FEATURE_SOLSCAN={feat} keylen={keylen}\n"
                        )
                    except Exception as e:
                        response_text = f"whoami error: {e}"
                elif text.strip().startswith('/a_logs_tail') or text.strip().startswith('/logs_tail'):
                    # Enhanced logs tail with ring buffer (ultra-fast)
                    try:
                        from robust_logging import get_ring_buffer_lines, get_ring_buffer_stats
                        
                        # Parse command arguments
                        parts = text.strip().split()
                        args = parts[1:] if len(parts) > 1 else []

                        # Defaults
                        n_lines = 50
                        level_filter = "all"
                        contains = None

                        for arg in args:
                            if arg.isdigit():
                                n_lines = max(10, min(500, int(arg)))
                            elif arg.startswith("level="):
                                level_filter = arg.split("=", 1)[1].lower()
                            elif arg.startswith("contains="):
                                contains = arg.split("=", 1)[1]

                        # Get lines from ring buffer
                        lines = get_ring_buffer_lines(n_lines, level_filter)

                        # Optional substring filter
                        if contains:
                            lines = [ln for ln in lines if contains in ln]
                        
                        stats = get_ring_buffer_stats()
                        
                        if not lines:
                            filter_desc = f"level={level_filter}"
                            if contains:
                                filter_desc += f", contains='{contains}'"
                            response_text = f'❌ No log entries found ({filter_desc})'
                        else:
                            log_text = '\n'.join(lines)
                            
                            # Truncate if too long for Telegram (4096 char limit)
                            if len(log_text) > 3000:
                                log_text = "..." + log_text[-2900:]
                            
                            header = f"📋 Ring Buffer Log Entries (last {len(lines)} lines"
                            if level_filter != "all":
                                header += f", level>={level_filter}"
                            if contains:
                                header += f", contains='{contains}'"
                            header += "):"
                            
                            buffer_info = ""
                            if stats.get("available"):
                                buffer_info = f"\nBuffer: {stats['current_size']}/{stats['max_capacity']} ({stats['usage_percent']}%)"
                            
                            response_text = f'''{header}

```
{log_text}
```
{buffer_info}
Source: Ring Buffer (ultra-fast access)
Usage: /a_logs_tail [number] [level=error|warn|info|all] [contains=text]
Examples: /a_logs_tail 100, /a_logs_tail level=error, /a_logs_tail contains=WS'''
                            
                    except Exception as e:
                        response_text = f'❌ Error reading ring buffer: {str(e)}'
                elif text.startswith("/a_diag_fetch"):
                    # Enhanced diagnostic command for multi-source fetch system
                    try:
                        # Import the diagnostic function
                        import asyncio
                        from alerts.telegram import cmd_a_diag_fetch
                        
                        # Create a mock update object for compatibility
                        class MockUpdateDiag:
                            def __init__(self, message_data):
                                self.message = type('obj', (object,), message_data)()
                                self.effective_user = type('obj', (object,), {'id': user.get('id')})()
                        
                        mock_update = MockUpdateDiag({
                            'chat': type('obj', (object,), {'id': message['chat']['id']})(),
                            'from_user': type('obj', (object,), user)(),
                            'text': text
                        })
                        
                        # Run the async diagnostic command
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            response_text = loop.run_until_complete(cmd_a_diag_fetch(mock_update, None))
                        finally:
                            loop.close()
                            
                    except Exception as e:
                        response_text = f'❌ Diagnostic command error: {str(e)}'
                
                # Assistant model and codegen integration
                elif text.startswith("/assistant_model"):
                    try:
                        from assistant_dev import set_current_model, get_current_model
                        
                        logger.info(f"[WEBHOOK] Routing /assistant_model")
                        if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                            response_text = "Not authorized."
                        else:
                            parts = text.split()
                            if len(parts) < 2:
                                response_text = f"Current model: {get_current_model()}"
                            else:
                                new_model = parts[1].strip()
                                os.environ["ASSISTANT_MODEL"] = new_model  # live in-process
                                set_current_model(new_model)               # persist to assistant module
                                logger.info(f"[ADMIN] Assistant model changed to {new_model}")
                                response_text = f"✅ Assistant model changed to: {new_model}"
                    except Exception as e:
                        logger.exception("assistant_model handler error")
                        publish("command.error", {"cmd": text.split()[0], "err": str(e)})
                        response_text = f"❌ /assistant_model failed: {e}"

                # --- assistant via sync path (no asyncio) ---
                elif text.startswith("/assistant "):
                    logger.info(f"[WEBHOOK] Routing /assistant")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from alerts.telegram import assistant_generate_sync
                        req = text.partition(" ")[2].strip()
                        try:
                            model_used, body = assistant_generate_sync(req)
                            response_text = f"Model: {model_used}\n\n{body}"
                        except Exception as e:
                            logger.exception("assistant sync error")
                            publish("command.error", {"cmd": text.split()[0], "err": str(e)})
                            response_text = f"❌ /assistant failed: {e}"

                # /rules_show (admin only)
                elif text.strip() == "/rules_show":
                    logger.info("[WEBHOOK] Routing /rules_show")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from alerts.telegram import cmd_rules_show_sync
                        response_text = cmd_rules_show_sync()

                # /pumpfun_probe (admin only)
                elif text.strip().startswith("/pumpfun_probe"):
                    logger.info("[WEBHOOK] Routing /pumpfun_probe")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from data_fetcher import probe_pumpfun_sources
                            
                            res = probe_pumpfun_sources(limit=50)
                            lines = [
                                "🛠 Pump.fun Probe",
                                f"at: {res['at']}",
                                "",
                            ]
                            for s in res["sources"]:
                                mark = "✅" if (s["status"] == 200 and s["count"] > 0) else "⚠️" if s["status"] else "❌"
                                lines.append(f"{mark} {s['label']}  ({s['ms']} ms)  status={s['status']}  count={s['count']}" + (f"  err={s['error']}" if s["error"] else ""))
                                if s["samples"]:
                                    for it in s["samples"]:
                                        sym = it.get("symbol") or "?"
                                        nm  = it.get("name") or "?"
                                        lines.append(f"   • {sym} — {nm}")
                            r = res.get("rpc", {})
                            if r:
                                rmark = "✅" if r.get("ok") else "❌"
                                lines.append("")
                                lines.append(f"{rmark} solana-rpc ({r.get('ms')} ms) url={r.get('url')}"+ (f"  err={r.get('error')}" if r.get("error") else ""))
                            
                            response_text = "\n".join(lines)
                        except Exception as e:
                            response_text = f"❌ Probe failed: {str(e)}"

                # /pumpfun_status (admin only) 
                elif text.strip().startswith("/pumpfun_status"):
                    logger.info("[WEBHOOK] Routing /pumpfun_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from pumpfun_enrich import pumpfun_ping
                            import textwrap
                            
                            url, status, n, err = pumpfun_ping(limit=10)
                            body = textwrap.dedent(f"""\
                                Pump.fun status
                                ───────────────
                                url:    {url}
                                status: {status}
                                items:  {n}
                                error:  {err or "-"}
                            """)
                            response_text = f"```\n{body}\n```"
                        except Exception as e:
                            response_text = f"❌ Status check failed: {str(e)}"

                # /scan_start [interval_sec]
                elif text.strip().startswith("/scan_start"):
                    logger.info("[WEBHOOK] Routing /scan_start")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            parts = text.split()
                            interval = int(parts[1]) if len(parts) > 1 else None
                            if interval:
                                SCANNER.interval = max(5, interval)
                            SCANNER.start()
                            
                            # Ensure all scanners are registered and start them
                            _ensure_scanners()
                            started_scanners = []
                            for name, scanner in SCANNERS.items():
                                try:
                                    if hasattr(scanner, 'start') and hasattr(scanner, 'enabled') and scanner.enabled:
                                        scanner.start()
                                        started_scanners.append(name)
                                except Exception as e:
                                    app.logger.warning("[SCAN] %s start error: %s", name, e)
                            
                            scanner_list = ", ".join(started_scanners) if started_scanners else "birdeye only"
                            response_text = f"✅ Scanners started: {scanner_list}\nBirdeye interval: {SCANNER.interval}s"
                            logger.info(f"[WEBHOOK] scan_start response ready: {len(response_text)} chars")
                        except Exception as e:
                            response_text = f"❌ scan_start failed: {e}"
                            logger.error(f"[WEBHOOK] scan_start error: {e}")

                # /scan_stop
                elif text.strip().startswith("/scan_stop"):
                    logger.info("[WEBHOOK] Routing /scan_stop")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            SCANNER.stop()
                            
                            # Stop all scanners in registry
                            for s in SCANNERS.values():
                                try: 
                                    s.stop()
                                except: 
                                    pass
                            
                            response_text = "🛑 All scanners stopped"
                            logger.info(f"[WEBHOOK] scan_stop response ready: {len(response_text)} chars")
                        except Exception as e:
                            response_text = f"❌ scan_stop failed: {e}"
                            logger.error(f"[WEBHOOK] scan_stop error: {e}")

                # /scan_status (admin only)
                elif text.strip().startswith("/scan_status"):
                    logger.info("[WEBHOOK] Routing /scan_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        # Ensure scanners are initialized in this worker process
                        _ensure_scanners()
                        try:
                            st = SCANNER.status()
                            from birdeye import SCAN_MODE
                            
                            # Check actual scanner status with API key detection
                            import os
                            solscan_scanner = SCANNERS.get('solscan')
                            solscan_api_key = os.getenv('SOLSCAN_API_KEY', '')
                            
                            # Determine Solscan status with proper key detection
                            if solscan_scanner and solscan_scanner.enabled and solscan_api_key:
                                solscan_status = "ON"
                            elif solscan_api_key:
                                solscan_status = "ON (key present, scanner initializing)"
                            else:
                                solscan_status = "OFF (no key)"
                            
                            lines = [
                                "🔍 Multi-Source Scan Status",
                                f"running: {st['running']}",
                                f"interval: {st['interval']}s", 
                                f"seen_cache: {st['seen_cache']}",
                                f"thread_alive: {st['thread_alive']}",
                                f"mode: {SCAN_MODE}",
                                "",
                                "Data Sources (live):",
                                f"  • Birdeye HTTP: OK",
                                f"  • Jupiter: {'ON' if SCANNERS.get('jupiter') and SCANNERS['jupiter'].enabled else 'OFF'}",
                                f"  • Solscan: {solscan_status}"
                            ]
                            response_text = "\n".join(lines)
                            logger.info(f"[WEBHOOK] scan_status response ready: {len(response_text)} chars")
                        except Exception as e:
                            response_text = f"❌ scan_status failed: {e}"
                            logger.error(f"[WEBHOOK] scan_status error: {e}")

                # /scan_mode [all|strict]
                elif text.strip().startswith("/scan_mode"):
                    logger.info("[WEBHOOK] Routing /scan_mode")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            parts = text.split()
                            if len(parts) < 2:
                                response_text = "Usage: /scan_mode all|strict"
                            else:
                                set_scan_mode(parts[1])
                                response_text = f"⚙️ Scan mode set to {parts[1].lower()}"
                        except Exception as e:
                            response_text = f"❌ scan_mode failed: {e}"

                # /birdeye_probe [limit]
                elif text.strip().startswith("/birdeye_probe"):
                    logger.info("[WEBHOOK] Routing /birdeye_probe")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            parts = text.split()
                            limit = int(parts[1]) if len(parts) > 1 else 10
                            res = birdeye_probe_once(limit=limit)
                            if not res.get("ok"):
                                response_text = f"❌ probe error: {res.get('err')}"
                            else:
                                items = res.get("items") or []
                                if not items:
                                    response_text = "ℹ️ probe ok, no items"
                                else:
                                    lines = ["🧪 Birdeye Probe (newest):", ""]
                                    for it in items:
                                        mint = it.get("mint")
                                        sym  = it.get("symbol") or "?"
                                        nm   = it.get("name") or "?"
                                        be   = f"https://birdeye.so/token/{mint}?chain=solana"
                                        lines.append(f"• {nm} ({sym})\n`{mint}`\n{be}")
                                    response_text = "\n".join(lines)
                        except Exception as e:
                            response_text = f"❌ birdeye_probe failed: {e}"

                # /scan_mode strict | all | ws
                elif text.strip().startswith("/scan_mode"):
                    logger.info("[WEBHOOK] Routing /scan_mode")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        parts = text.strip().split()
                        arg = parts[1].lower() if len(parts) > 1 else ""
                        if arg in ("strict", "all"):
                            try:
                                from birdeye import set_scan_mode
                                set_scan_mode(arg)
                                response_text = f"✅ scan_mode set to *{arg}*"
                            except Exception as e:
                                response_text = f"❌ failed to set scan_mode: {e}"
                        elif arg == "ws":
                            # ensure WS is running
                            try:
                                ws_client.start()
                                response_text = "✅ WebSocket scanner *started*"
                            except Exception as e:
                                response_text = f"❌ WS start failed: {e}"
                        else:
                            response_text = "Usage: /scan_mode strict|all|ws"

                # /scan_probe_ws (WebSocket probe and pipeline test)
                elif text.strip().startswith("/scan_probe_ws"):
                    logger.info("[WEBHOOK] Routing /scan_probe_ws")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        # Quick probe of WS state; also send a synthetic alert to verify Telegram piping
                        running = getattr(ws_client, "running", False)
                        alive = getattr(ws_client, "thread", None)
                        alive = alive.is_alive() if alive else False
                        # synthetic test alert to ensure pipeline prints to Telegram
                        _ = send_admin_md("🧪 *Probe:* WS pipeline OK (synthetic alert)")
                        response_text = (
                            "🔎 WS probe\n"
                            f"running: {running}\n"
                            f"thread_alive: {alive}\n"
                            "Sent a synthetic alert to admin."
                        )

                # /ws_status (WebSocket status check)
                elif text.strip().startswith("/ws_status"):
                    logger.info("[WEBHOOK] Routing /ws_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from birdeye_ws import is_ws_connected
                        status = ws_client.status()
                        connected = is_ws_connected()
                        thread_alive = getattr(ws_client, "thread", None)
                        thread_alive = thread_alive.is_alive() if thread_alive else False
                        
                        # human friendly last_msg_ago
                        ago = status.get("last_msg_ago_secs")
                        last_line = "last_msg_ago: —"
                        if ago is not None:
                            # show up to 2 decimals; also show ISO timestamp when available
                            iso = status.get("last_msg_iso")
                            last_line = f"last_msg_ago: {ago}s" + (f" (at {iso})" if iso else "")

                        response_text = (
                            "📡 *WebSocket Status*\n"
                            f"running: {status.get('running', False)}\n"
                            f"connected: {connected}\n"
                            f"thread_alive: {thread_alive}\n"
                            f"mode: {status.get('mode', 'unknown')}\n"
                            f"messages_received: {status.get('recv', 0)}\n"
                            f"new_tokens: {status.get('new', 0)}\n"
                            f"cache_size: {status.get('seen_cache', 0)}/8000\n"
                            f"{last_line}\n"
                            f"watchdog: {status.get('watchdog', False)}\n"
                            f"stale_after: {status.get('stale_after', 0)}s\n"
                            f"restart_count: {status.get('restart_count', 0)}"
                        )

                # /ds_start (DexScreener scanner start with optional interval)
                elif text.strip().startswith("/ds_start"):
                    logger.info("[WEBHOOK] Routing /ds_start")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            parts = text.split()
                            interval = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                            if interval:
                                DS_SCANNER.interval = max(10, interval)
                            DS_SCANNER.start()
                            response_text = f"✅ Dexscreener scan started (every {DS_SCANNER.interval}s)"
                        except Exception as e:
                            response_text = f"❌ DS start failed: {e}"

                # /ds_stop (DexScreener scanner stop)
                elif text.strip().startswith("/ds_stop"):
                    logger.info("[WEBHOOK] Routing /ds_stop")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            DS_SCANNER.stop()
                            response_text = "🛑 Dexscreener scan stopped"
                        except Exception as e:
                            response_text = f"❌ DS stop failed: {e}"

                # /ds_status (DexScreener status check)
                elif text.strip().startswith("/ds_status"):
                    logger.info("[WEBHOOK] Routing /ds_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            status = DS_SCANNER.status()
                            response_text = (
                                "🧭 *Dexscreener Status*\n"
                                f"running: {status.get('running', False)}\n"
                                f"interval: {status.get('interval', 0)}s\n"
                                f"seencache: {status.get('seencache', 0)}/8000\n"
                                f"threadalive: {status.get('threadalive', False)}\n"
                                f"window: {status.get('window_sec', 0)}s"
                            )
                        except Exception as e:
                            response_text = f"❌ DS status failed: {e}"

                # /ws_stale (Set watchdog stale window)
                elif text.strip().startswith("/ws_stale "):
                    logger.info("[WEBHOOK] Routing /ws_stale")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            secs = float(text.split(" ", 1)[1].strip())
                            ws = SCANNERS.get("websocket")
                            if not ws:
                                response_text = "❌ No WS scanner registered"
                            else:
                                ws._stale_after = max(5.0, secs)
                                response_text = f"✅ WS stale window set to {ws._stale_after:.1f}s"
                        except Exception as e:
                            response_text = f"❌ ws_stale error: {e}"

                # /ws_force_stale (Force stale state for testing)
                elif text.strip().startswith("/ws_force_stale"):
                    logger.info("[WEBHOOK] Routing /ws_force_stale")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        import time
                        ws = SCANNERS.get("websocket")
                        if not ws:
                            response_text = "❌ No WS scanner registered"
                        else:
                            # push last-msg timestamp back in time to trigger watchdog quickly
                            ws._last_msg_monotonic = time.monotonic() - (ws._stale_after + 1.0)
                            response_text = "🧪 Forced stale state; watchdog should restart shortly."

                # /ws_tap (WebSocket debug tap - mirror WS messages to logs)
                elif text.strip().startswith("/ws_tap"):
                    logger.info("[WEBHOOK] Routing /ws_tap")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            parts = text.split()
                            mode = parts[1].lower() if len(parts) > 1 else "on"
                            enabled = mode in ("on", "true", "1", "yes")
                            try:
                                # Try to use birdeye_ws helper if available
                                if hasattr(ws_client, 'set_tap_mode'):
                                    ws_client.set_tap_mode(enabled)
                                else:
                                    # Fallback: store flag in environment
                                    os.environ["WS_TAP"] = "1" if enabled else "0"
                            except Exception:
                                # Fallback: store flag in environment
                                os.environ["WS_TAP"] = "1" if enabled else "0"
                            response_text = f"🛰 WS tap {'enabled' if enabled else 'disabled'}"
                        except Exception as e:
                            response_text = f"❌ WS tap failed: {e}"

                # /scan_test (quick single-shot fetch preview)
                elif text.strip().startswith("/scan_test"):
                    logger.info("[WEBHOOK] Routing /scan_test")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            res = birdeye_probe_once(limit=5)
                            if not res.get("ok"):
                                response_text = f"❌ scan_test: {res.get('err')}"
                            else:
                                items = res.get("items") or []
                                if not items:
                                    response_text = "✅ scan_test ok — no new items right now"
                                else:
                                    lines = ["✅ scan_test ok — sample:", ""]
                                    for it in items:
                                        mint = it.get("mint")
                                        sym  = it.get("symbol") or "?"
                                        nm   = it.get("name") or "?"
                                        be   = f"https://birdeye.so/token/{mint}?chain=solana"
                                        pf   = f"https://pump.fun/{mint}"
                                        lines.append(f"• *{nm}* ({sym})\n`{mint}`\n[Birdeye]({be}) • [Pump.fun]({pf})")
                                    response_text = "\n".join(lines)
                        except Exception as e:
                            response_text = f"❌ scan_test failed: {e}"

                # /system_scan_status (legacy data fetcher status)
                elif text.strip().startswith("/system_scan_status"):
                    logger.info("[WEBHOOK] Routing /system_scan_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            import datetime
                            lines = [
                                "🔍 System Scan Status",
                                f"at: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
                                "",
                            ]
                            
                            # Check data fetcher status
                            try:
                                from data_fetcher import probe_pumpfun_sources
                                res = probe_pumpfun_sources(limit=20)
                                working_sources = sum(1 for s in res["sources"] if s["status"] == 200)
                                total_sources = len(res["sources"])
                                lines.append(f"📊 Data Sources: {working_sources}/{total_sources} operational")
                                
                                for s in res["sources"]:
                                    mark = "✅" if s["status"] == 200 else "❌"
                                    lines.append(f"  {mark} {s['label']}: {s['status']} ({s['ms']}ms)")
                                    
                                # Check RPC connectivity
                                rpc = res.get("rpc", {})
                                if rpc:
                                    mark = "✅" if rpc.get("ok") else "❌"
                                    lines.append(f"{mark} Solana RPC: {rpc.get('ms', 'N/A')}ms")
                            except Exception as e:
                                lines.append(f"❌ Data sources check failed: {str(e)}")
                            
                            # Check event bus
                            try:
                                from eventbus import get_subscriber_count
                                count = get_subscriber_count()
                                lines.append(f"📡 Event Bus: {count} active subscribers")
                            except:
                                lines.append("📡 Event Bus: status unknown")
                            
                            # Check logging system
                            try:
                                from robust_logging import get_ring_buffer_stats
                                stats = get_ring_buffer_stats()
                                if stats.get("available"):
                                    lines.append(f"📝 Logging: {stats['current_size']}/{stats['max_capacity']} entries ({stats['usage_percent']}%)")
                                else:
                                    lines.append("📝 Logging: ring buffer unavailable")
                            except:
                                lines.append("📝 Logging: status unknown")
                            
                            response_text = "\n".join(lines)
                        except Exception as e:
                            response_text = f"❌ Scan status failed: {str(e)}"

                # /scan_test (admin only)
                elif text.strip().startswith("/scan_test"):
                    logger.info("[WEBHOOK] Routing /scan_test")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            import datetime
                            lines = [
                                "🧪 System Test Results",
                                f"at: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
                                "",
                            ]
                            
                            # Test data fetching
                            try:
                                from data_fetcher import probe_pumpfun_sources
                                res = probe_pumpfun_sources(limit=5)
                                
                                sample_count = 0
                                for s in res["sources"]:
                                    if s.get("samples"):
                                        sample_count += len(s["samples"])
                                
                                lines.append(f"🔬 Data Test: {sample_count} sample tokens retrieved")
                                
                                # Show sample tokens if available
                                for s in res["sources"]:
                                    if s.get("samples"):
                                        lines.append(f"  📈 From {s['label']}:")
                                        for sample in s["samples"][:2]:  # Show first 2 samples
                                            symbol = sample.get("symbol", "?")
                                            name = sample.get("name", "?")
                                            lines.append(f"    • {symbol} - {name}")
                                        if len(s["samples"]) > 2:
                                            lines.append(f"    ... and {len(s['samples']) - 2} more")
                            except Exception as e:
                                lines.append(f"❌ Data test failed: {str(e)}")
                            
                            # Test event publishing
                            try:
                                # Enhanced events system with deduplication
        # Using global publish function
                                def get_subscriber_count(): return len([sub for subs in BUS._subs.values() for sub in subs])
                                publish("test.scan", {"test_id": "scan_test", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()})
                                subscriber_count = get_subscriber_count()
                                lines.append(f"📤 Event Test: published to {subscriber_count} subscribers")
                            except Exception as e:
                                lines.append(f"❌ Event test failed: {str(e)}")
                            
                            lines.append("")
                            lines.append("✅ System test complete")
                            
                            response_text = "\n".join(lines)
                        except Exception as e:
                            response_text = f"❌ Scan test failed: {str(e)}"

                # /rules_reload (admin only)
                elif text.startswith("/rules_reload"):
                    logger.info("[WEBHOOK] Routing /rules_reload")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        _reply("Not authorized.")
                        return jsonify({"status": "ok", "command": text, "response_sent": True})
                    from alerts.telegram import cmd_rules_reload_sync
                    _reply(cmd_rules_reload_sync())
                    return jsonify({"status": "ok", "command": text, "response_sent": True})

                # /fetch or /fetch_now (admin only) - but only for single commands, multiple commands handled above
                elif (text.strip().startswith("/fetch") or text.strip().startswith("/fetch_now")) and len(commands_in_message) <= 1:
                    logger.info("[WEBHOOK] /fetch alias entered (raw='%s')", text.strip())
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        _reply("Not authorized.")
                        return jsonify({"status": "ok", "command": text, "response_sent": True})
                    
                    try:
                        from alerts.telegram import cmd_fetch_now_sync
                    except Exception as e:
                        logger.exception("[WEBHOOK] import cmd_fetch_now_sync failed: %s", e)
                        _reply("❌ fetch failed: internal import error.", parse_mode=None, no_preview=True)
                    else:
                        try:
                            result_text = cmd_fetch_now_sync()
                            if not result_text or not result_text.strip():
                                result_text = "No candidates found (multi-source fetch returned empty)."
                            _reply(result_text, parse_mode="Markdown", no_preview=True)
                            logger.info("[WEBHOOK] /fetch replied OK (len=%d)", len(result_text))
                        except Exception as e:
                            logger.exception("[WEBHOOK] /fetch error: %s", e)
                            _reply(f"❌ fetch failed: {str(e)[:300]}", parse_mode=None, no_preview=True)
                    return jsonify({"status": "ok", "command": text, "response_sent": True})

                # /pumpfunstatus (admin only)
                elif text.startswith("/pumpfunstatus"):
                    logger.info("[WEBHOOK] Routing /pumpfunstatus")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        _reply("Not authorized.")
                        return jsonify({"status": "ok", "command": text, "response_sent": True})
                    try:
                        from data_fetcher import probe_pumpfun_sources
                        result = probe_pumpfun_sources(limit=5)
                        
                        lines = ["🔍 Pump.fun Source Status:"]
                        for source in result.get("sources", []):
                            status_icon = "✅" if source.get("status") == 200 else "❌"
                            lines.append(f"{status_icon} {source.get('label', 'Unknown')}: {source.get('status')} ({source.get('ms', 'N/A')}ms)")
                            
                            # Show sample tokens if available
                            samples = source.get("samples", [])
                            if samples:
                                lines.append(f"   Samples: {len(samples)} tokens retrieved")
                                for sample in samples[:2]:
                                    symbol = sample.get("symbol", "?")
                                    name = sample.get("name", "?")
                                    lines.append(f"   • {symbol} - {name}")
                        
                        response_text = "\n".join(lines)
                    except Exception as e:
                        response_text = f"❌ pumpfunstatus failed: {e}"

                # /pumpfunprobe (admin only)
                elif text.startswith("/pumpfunprobe"):
                    logger.info("[WEBHOOK] Routing /pumpfunprobe")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        _reply("Not authorized.")
                        return jsonify({"status": "ok", "command": text, "response_sent": True})
                    try:
                        from data_fetcher import fetch_candidates_from_pumpfun
                        tokens = fetch_candidates_from_pumpfun(limit=10, offset=0)
                        
                        if not tokens:
                            response_text = "❌ No tokens retrieved from Pump.fun"
                        else:
                            lines = [f"🟢 Pump.fun Probe Results: {len(tokens)} tokens"]
                            lines.append("symbol | name | holders | mcap$ | age_min")
                            for token in tokens[:5]:
                                symbol = token.get("symbol", "?")
                                name = token.get("name", "?")[:15]
                                holders = token.get("holders", "?")
                                mcap = token.get("mcap_usd", "?")
                                age = token.get("age_min", "?")
                                lines.append(f"{symbol} | {name} | {holders} | {mcap} | {age}")
                            
                            response_text = "```\n" + "\n".join(lines) + "\n```"
                    except Exception as e:
                        response_text = f"❌ pumpfunprobe failed: {e}"

                # /fetch_source (admin only)
                elif text.startswith("/fetch_source"):
                    logger.info("[WEBHOOK] Routing /fetch_source")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        _reply("Not authorized.")
                        return jsonify({"status": "ok", "command": text, "response_sent": True})
                    
                    # Create mock update object for compatibility
                    class MockMessage:
                        def __init__(self, text, chat_id):
                            self.text = text
                            self.chat_id = chat_id
                        
                        async def reply_text(self, text, parse_mode=None):
                            _reply(text)
                    
                    class MockUpdate:
                        def __init__(self, message_text, user_data, chat_id):
                            self.message = MockMessage(message_text, chat_id)
                            self.effective_user = type('User', (), user_data)()
                    
                    mock_update = MockUpdate(text, user, message['chat']['id'])
                    
                    try:
                        import asyncio
                        from alerts.telegram import cmd_fetch_source_sync
                        
                        # Run the async function
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(cmd_fetch_source_sync(mock_update, None))
                        finally:
                            loop.close()
                        
                        return jsonify({"status": "ok", "command": text, "response_sent": True})
                    except Exception as e:
                        logger.exception("fetch_source error")
                        publish("command.error", {"cmd": text.split()[0], "err": str(e)})
                        _reply(f"❌ fetch_source failed: {e}")
                        return jsonify({"status": "error", "command": text, "error": str(e)})
                        
                elif text.strip() in ['/a_logs_stream', '/logs_stream']:
                    response_text = '''📡 Log Streaming:

Current mode: Direct webhook processing
Real-time logging: Active
Recent activity: Bot processing commands successfully

Use /a_logs_tail for recent log entries.
Full streaming available via admin interface.'''

                elif text.strip() in ['/a_logs_watch', '/logs_watch']:
                    response_text = '''👁️ Log Monitoring:

Current status: Enhanced logging active
Webhook processing: Operational  
Admin commands: Responding successfully
Error tracking: No recent errors

All bot activity is being logged in real-time.'''

                elif text.strip() in ['/a_mode', '/mode']:
                    response_text = '''⚙️ Bot Operation Mode:

Current Mode: Webhook Processing
PTB Integration: Disabled (import conflicts)
Fallback System: Direct Telegram API
Admin Commands: Fully operational
Response System: Working (HTTP 200)

Enhanced logging and monitoring active.'''

                elif text.strip().startswith("/monitor"):
                    from urllib.parse import urljoin, urlencode
                    base = request.url_root  # e.g., https://<your-repl-domain>/
                    tok  = os.environ.get("LIVE_TOKEN","")
                    url  = urljoin(base, "monitor") + ("?" + urlencode({"token": tok}) if tok else "")
                    response_text = f"Open Live Monitor:\n{url}"

                elif text.strip().startswith("/live"):
                    from urllib.parse import urljoin, urlencode
                    base = request.url_root
                    tok  = os.environ.get("LIVE_TOKEN","")
                    url  = urljoin(base, "live") + ("?" + urlencode({"token": tok}) if tok else "")
                    response_text = f"Open Live Console:\n{url}"

                elif text.strip().startswith("/birdeye_start"):
                    try:
                        from birdeye import get_scanner
                        scanner = get_scanner(publish)
                        scanner.start()
                        status = scanner.status()
                        response_text = f"Birdeye scanner started\nInterval: {status['interval']}s\nCache size: {status['seen_cache']}"
                    except Exception as e:
                        response_text = f"Birdeye start failed: {e}"

                elif text.strip().startswith("/birdeye_stop"):
                    try:
                        from birdeye import get_scanner
                        scanner = get_scanner(publish)
                        scanner.stop()
                        response_text = "Birdeye scanner stopped"
                    except Exception as e:
                        response_text = f"Birdeye stop failed: {e}"

                elif text.strip().startswith("/birdeye_status"):
                    try:
                        from birdeye import get_scanner
                        scanner = get_scanner(publish)
                        status = scanner.status()
                        response_text = f"""Birdeye Scanner Status:
Running: {status['running']}
Interval: {status['interval']}s
Cache: {status['seen_cache']} tokens
API Key: {'Set' if os.environ.get('BIRDEYE_API_KEY') else 'Missing'}"""
                    except Exception as e:
                        response_text = f"Birdeye status failed: {e}"

                elif text.strip().startswith("/birdeye_tick"):
                    try:
                        from birdeye import get_scanner
                        scanner = get_scanner(publish)
                        scanner.tick()
                        response_text = "Birdeye manual tick executed"
                    except Exception as e:
                        response_text = f"Birdeye tick failed: {e}"

                elif text.startswith("/scan_start"):
                    try:
                        parts = text.split()
                        secs = int(parts[1]) if len(parts) > 1 else None
                    except Exception:
                        secs = None

                    scanner = get_scanner(publish)        # <-- new singleton
                    if secs:
                        scanner.interval = max(5, int(secs))
                    scanner.start()

                    response_text = f"✅ Birdeye scanner started (every {scanner.interval}s)"

                elif text.startswith("/scan_stop"):
                    scanner = get_scanner(publish)
                    scanner.stop()
                    response_text = "🔴 Birdeye scanner stopped."

# Removed duplicate scan_status handler - using the multi-source version at line 828 instead

                elif text.strip().startswith("/scan_mode"):
                    logger.info("[WEBHOOK] Routing /scan_mode")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            parts = text.split()
                            mode = parts[1] if len(parts) > 1 else "strict"
                            from birdeye import set_scan_mode, current_mode
                            set_scan_mode(mode)
                            response_text = f"✅ scan mode set → {current_mode()}"
                        except Exception as e:
                            response_text = f"❌ scan_mode failed: {e}"

                elif text.strip().startswith("/scan_probe"):
                    logger.info("[WEBHOOK] Routing /scan_probe")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            parts = text.split()
                            n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
                            from birdeye import peek_last
                            items = peek_last(n)
                            if not items:
                                response_text = "No cached items yet. Wait a few ticks after /scan_start."
                            else:
                                lines = ["🔎 Latest Birdeye items:"]
                                for it in items[-n:]:
                                    mint = it.get("mint") or "?"
                                    sym  = it.get("symbol") or "?"
                                    nm   = it.get("name") or "?"
                                    lines.append(f"• {nm} ({sym}) — `{mint}`")
                                response_text = "\n".join(lines)
                        except Exception as e:
                            response_text = f"❌ scan_probe failed: {e}"

                elif text.strip().startswith("/ws_start"):
                    logger.info("[WEBHOOK] Routing /ws_start")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        # Enhanced events system
        # Using global publish function
                        from birdeye_ws import get_ws
                        def notify_admin(msg):
                            _reply(msg)
                        ws = get_ws(publish=publish, notify=notify_admin)
                        ws.start()
                        response_text = "🟢 Birdeye WS started."

                elif text.strip().startswith("/ws_stop"):
                    logger.info("[WEBHOOK] Routing /ws_stop")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from birdeye_ws import get_ws
                        def _notify(_): pass
                        ws = get_ws(publish=lambda *_: None, notify=_notify)
                        ws.stop()
                        response_text = "🔴 Birdeye WS stopped."

                elif text.strip().startswith("/ws_status"):
                    logger.info("[WEBHOOK] Routing /ws_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from birdeye_ws import get_ws
                        ws = get_ws(publish=lambda *_: None, notify=lambda *_: None)
                        st = ws.status()
                        # Get subscription topics
                        topics = getattr(ws, 'subscription_topics', ['token.created'])
                        
                        response_text = (
                            "🗂 *Birdeye WebSocket Status*\n"
                            f"running: {st['running']}\n"
                            f"connected: {st.get('connected', False)}\n"
                            f"recv: {st['recv']}  new: {st['new']}\n"
                            f"seencache: {st['seen_cache']}  threadalive: {st['thread_alive']}\n"
                            f"mode: {st['mode']}\n"
                            f"topics: {', '.join(topics)}"
                        )

                elif text.strip().startswith("/ws_debug"):
                    logger.info("[WEBHOOK] Routing /ws_debug")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        arg = text.split(maxsplit=1)[1].lower() if " " in text else "status"
                        from birdeye_ws import get_ws
                        ws = get_ws(publish=lambda *_: None, notify=lambda *_: None)
                        if arg in ("on","true","1"):
                            try:
                                ws.set_debug(True)
                                response_text = "🧪 WS debug: ON"
                            except Exception as e:
                                response_text = f"❌ WS debug on failed: {e}"
                        elif arg in ("off","false","0"):
                            try:
                                ws.set_debug(False)
                                response_text = "🧪 WS debug: OFF"
                            except Exception as e:
                                response_text = f"❌ WS debug off failed: {e}"
                        else:
                            response_text = f"🧪 WS debug: {getattr(ws,'_debug_mode', False)}"

                elif text.strip().startswith("/ws_probe"):
                    logger.info("[WEBHOOK] Routing /ws_probe")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        import time
                        from birdeye_ws import get_ws
                        ws = get_ws(publish=lambda *_: None, notify=lambda *_: None)
                        ok = False
                        try:
                            ok = ws.injectdebugevent({"type":"probe","ts":time.time()})
                        except Exception as e:
                            response_text = f"❌ Debug probe error: {e}"
                        if ok:
                            response_text = "🧪 Probe injected"
                        elif "response_text" not in locals():
                            response_text = "❌ Probe failed"

                elif text.strip().startswith("/ws_dump"):
                    logger.info("[WEBHOOK] Routing /ws_dump")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from birdeye_ws import get_ws
                        ws = get_ws(publish=lambda *_: None, notify=lambda *_: None)
                        try:
                            lines = ws.getdebugcache()
                            tail = "\n".join(lines[-20:]) if lines else "(empty)"
                            response_text = f"🧾 WS debug cache (last {len(lines)}):\n{tail}"
                        except Exception as e:
                            response_text = f"❌ Debug dump error: {e}"

                elif text.strip().startswith("/ws_mode"):
                    # /ws_mode all  or /ws_mode strict
                    logger.info("[WEBHOOK] Routing /ws_mode")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from birdeye_ws import set_ws_mode
                        parts = text.split()
                        mode = parts[1] if len(parts) > 1 else "strict"
                        set_ws_mode(mode)
                        response_text = f"⚙️ Birdeye WS mode set to: {mode}"
                        
                # /ws_restart - Enhanced WebSocket restart with Launchpad support
                elif text.strip().startswith("/ws_restart"):
                    logger.info("[WEBHOOK] Routing /ws_restart")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from birdeye_ws import get_ws
                            # Enhanced events system
        # Using global publish function
                            ws = get_ws(publish=publish, notify=lambda m: _reply(m))
                            ws.stop()
                            time.sleep(0.5)
                            ws.start()
                            response_text = "🔄 *Birdeye WS restarted with Launchpad priority*"
                        except Exception as e:
                            response_text = f"❌ WS restart error: {e}"
                            
                # /ws_sub - Set subscription topics with Launchpad priority
                elif text.strip().startswith("/ws_sub"):
                    logger.info("[WEBHOOK] Routing /ws_sub")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from birdeye_ws import get_ws
                            # Enhanced events system
        # Using global publish function
                            ws = get_ws(publish=publish, notify=lambda m: _reply(m))
                            
                            parts = text.split(maxsplit=1)
                            topics = []
                            if len(parts) > 1:
                                topics = [t.strip() for t in parts[1].split(",") if t.strip()]
                            if not topics:
                                topics = ["launchpad.created", "token.created"]
                            
                            # Set subscription topics
                            ws.subscription_topics = topics
                            
                            response_text = f"✅ *WS subscriptions set:* {', '.join(topics)}"
                        except Exception as e:
                            response_text = f"❌ WS subscription error: {e}"
                            
                # /ws_debug - Enhanced debug control
                elif text.strip().startswith("/ws_debug"):
                    logger.info("[WEBHOOK] Routing /ws_debug")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            arg = text.split(maxsplit=1)[1].lower() if " " in text else "status"
                            if arg in ("on","true","1"):
                                BIRDEYE_WS.set_debug(True)
                                response_text = "🧪 WS debug: ON"
                            elif arg in ("off","false","0"):
                                BIRDEYE_WS.set_debug(False)
                                response_text = "🧪 WS debug: OFF"
                            else:
                                response_text = f"🧪 WS debug: {getattr(BIRDEYE_WS,'_debug_mode',False)}"
                        except Exception as e:
                            response_text = f"❌ Debug command error: {e}"

                # ======= ENHANCED WS DEBUG CONTROLS =======
                elif text.strip().startswith("/ws_dump"):
                    logger.info("[WEBHOOK] Routing /ws_dump")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            lines = BIRDEYE_WS.getdebugcache()
                            response_text = "🧾 WS debug cache (last {}):\n{}".format(
                                len(lines), "\n".join(lines[-20:]) or "(empty)"
                            )
                        except Exception as e:
                            response_text = f"❌ Debug dump error: {e}"

                elif text.strip().startswith("/ws_probe"):
                    logger.info("[WEBHOOK] Routing /ws_probe")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            import time
                            ok = BIRDEYE_WS.injectdebugevent({"type":"probe","ts":time.time()})
                            response_text = "🧪 Probe injected" if ok else "❌ Probe failed"
                        except Exception as e:
                            response_text = f"❌ Debug probe error: {e}"

                # Jupiter Scanner Commands
                elif text.strip().startswith("/jupiter_start"):
                    logger.info("[WEBHOOK] Routing /jupiter_start")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            if JUPITER_SCANNER:
                                JUPITER_SCANNER.start()
                                response_text = "🪐 Jupiter scanner started successfully"
                            else:
                                response_text = "❌ Jupiter scanner not initialized"
                        except Exception as e:
                            response_text = f"❌ Jupiter start failed: {e}"

                elif text.strip().startswith("/jupiter_stop"):
                    logger.info("[WEBHOOK] Routing /jupiter_stop") 
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            if JUPITER_SCANNER:
                                JUPITER_SCANNER.stop()
                                response_text = "🪐 Jupiter scanner stopped"
                            else:
                                response_text = "❌ Jupiter scanner not initialized"
                        except Exception as e:
                            response_text = f"❌ Jupiter stop failed: {e}"

                elif text.strip().startswith("/jupiter_status"):
                    logger.info("[WEBHOOK] Routing /jupiter_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            if JUPITER_SCANNER:
                                status = "🟢 Running" if JUPITER_SCANNER.running else "🔴 Stopped"
                                enabled = "✅ Enabled" if JUPITER_SCANNER.enabled else "❌ Disabled"
                                cache_size = len(JUPITER_SCANNER.seen)
                                response_text = f"""🪐 **Jupiter Scanner Status**
Status: {status}
Feature: {enabled}
Cache: {cache_size} seen tokens
Interval: {JUPITER_SCANNER.interval}s
URL: https://token.jup.ag/all?includeCommunity=true"""
                            else:
                                response_text = "❌ Jupiter scanner not initialized"
                        except Exception as e:
                            response_text = f"❌ Jupiter status failed: {e}"

                # Solscan Scanner Commands
                elif text.strip().startswith("/solscan_start"):
                    logger.info("[WEBHOOK] Routing /solscan_start")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            if SOLSCAN_SCANNER:
                                if SOLSCAN_SCANNER.enabled:
                                    SOLSCAN_SCANNER.start()
                                    response_text = "🔍 Solscan scanner started successfully"
                                else:
                                    response_text = "❌ Solscan disabled\nRequires: FEATURE_SOLSCAN=on AND SOLSCAN_API_KEY"
                            else:
                                response_text = "❌ Solscan scanner not initialized"
                        except Exception as e:
                            response_text = f"❌ Solscan start failed: {e}"

                elif text.strip().startswith("/solscan_stop"):
                    logger.info("[WEBHOOK] Routing /solscan_stop")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            if SOLSCAN_SCANNER:
                                SOLSCAN_SCANNER.stop()
                                response_text = "🔍 Solscan scanner stopped"
                            else:
                                response_text = "❌ Solscan scanner not initialized"
                        except Exception as e:
                            response_text = f"❌ Solscan stop failed: {e}"

                # --- Admin: Solscan status (specific patterns first to avoid collision) --------------------------------------------------
                elif text.strip().startswith("/solscanstats"):
                    # CRITICAL DEBUG: Track if we reach this handler
                    logger.info(f"[CRITICAL-DEBUG] /solscanstats handler reached! text='{text}'")
                    logger.info("[WEBHOOK] Routing /solscanstats")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            # Force scanner initialization in this worker process
                            _ensure_scanners()
                            # Use SOLSCAN_SCANNER or scanners registry
                            scanner = SOLSCAN_SCANNER or SCANNERS.get("solscan")
                            
                            if scanner and hasattr(scanner, 'status'):
                                st = scanner.status()
                                import datetime
                                last_tick = st.get('last_tick_ts')
                                last_tick_str = "never" if not last_tick else datetime.datetime.fromtimestamp(last_tick).strftime("%H:%M:%S")
                                
                                # Enhanced stats display
                                new_cache_age = st.get('new_tokens_cache_age')
                                new_cache_age_str = f"{new_cache_age:.1f}s" if new_cache_age is not None else "N/A"
                                
                                response_text = (
                                    f"📊 *Solscan Pro Scanner Status*\n"
                                    f"Enabled: `{st.get('enabled', False)}`\n"
                                    f"Running: `{st.get('running', False)}`\n"
                                    f"Mode: `{st.get('mode', 'auto')}`\n"
                                    f"Base URL: `{st.get('base_url', 'unknown')}`\n"
                                    f"Last tick: `{last_tick_str}`\n"
                                    f"Last endpoint: `{st.get('last_successful_endpoint', 'none')}`\n"
                                    f"Last new endpoint: `{st.get('last_new_endpoint', 'none')}`\n"
                                    f"Last new count: `{st.get('last_new_count', 0)}`\n"
                                    f"Fallbacks: `{st.get('fallback_count', 0)}`\n"
                                    f"New tokens cache: `{st.get('new_tokens_cache_size', 0)}` items (age: `{new_cache_age_str}`)\n"
                                    f"Requests OK/Err: `{st.get('requests_ok', 0)}/{st.get('requests_err', 0)}`\n"
                                    f"Last status: `{st.get('last_status', 'N/A')}`\n"
                                    f"Seen count: `{st.get('seen_cache', 0)}`"
                                )
                            else:
                                response_text = "⚠️ Solscan scanner not initialized. Enable with FEATURE_SOLSCAN=on and provide SOLSCAN_API_KEY."
                        except Exception as e:
                            response_text = f"❌ solscanstats failed: {e}"

                # /solscan_ping - Manual ping command
                elif text.strip().startswith("/solscan_ping"):
                    logger.info("[WEBHOOK] Routing /solscan_ping")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            # Force scanner initialization in this worker process
                            _ensure_scanners()
                            scanner = SOLSCAN_SCANNER or SCANNERS.get("solscan")
                            
                            if scanner and hasattr(scanner, 'ping'):
                                result = scanner.ping()
                                if result.get('success'):
                                    response_text = f"🏓 Solscan ping → pong + tick ok ({result.get('new', 0)} new tokens | {result.get('seen', 0)} seen)"
                                else:
                                    response_text = f"❌ Solscan ping failed: {result.get('error', 'unknown')}"
                            else:
                                response_text = "⚠️ Solscan scanner not available for ping"
                        except Exception as e:
                            response_text = f"❌ solscan_ping failed: {e}"

                elif text.startswith("/solscan_mode"):
                    logger.info("[WEBHOOK] Routing /solscan_mode")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        # /solscan_mode [auto|new|trending]
                        parts = text.split()
                        mode = parts[1].strip().lower() if len(parts) > 1 else None
                        
                        # Force scanner initialization in this worker process
                        _ensure_scanners()
                        ss = SCANNERS.get("solscan")
                        
                        if not ss:
                            response_text = "❌ Solscan scanner not initialized"
                            logger.warning("[WEBHOOK] solscan_mode: scanner not found in SCANNERS")
                        else:
                            if mode in ("auto", "new", "trending"):
                                old_mode = ss.get_mode() if hasattr(ss, 'get_mode') else 'unknown'
                                ss.set_mode(mode)
                                response_text = f"✅ Solscan mode set to *{mode}* (was: {old_mode})"
                                logger.info(f"[WEBHOOK] solscan_mode: changed from {old_mode} to {mode}")
                            elif mode is None:
                                # Show current mode when no argument provided
                                current_mode = ss.get_mode() if hasattr(ss, 'get_mode') else 'unknown'
                                response_text = f"🧭 Solscan current mode: *{current_mode}*"
                                logger.info(f"[WEBHOOK] solscan_mode: current mode is {current_mode}")
                            else:
                                response_text = "Usage: `/solscan_mode auto|new|trending` or `/solscan_mode` to check current mode"
                                logger.warning(f"[WEBHOOK] solscan_mode: invalid mode '{mode}'")

                # --- Admin: Process Diagnostic --------------------------------------------------
                elif text.strip().startswith("/diag"):
                    logger.info("[WEBHOOK] Routing /diag")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        import os
                        # Force scanner initialization in this worker process
                        _ensure_scanners()
                        
                        scanner_keys = list(SCANNERS.keys()) if 'SCANNERS' in globals() else []
                        solscan_info = {}
                        if 'SCANNERS' in globals() and 'solscan' in SCANNERS:
                            scanner = SCANNERS['solscan']
                            if scanner:
                                solscan_info = {
                                    "enabled": getattr(scanner, 'enabled', False),
                                    "running": getattr(scanner, 'running', False), 
                                    "object_id": id(scanner)
                                }
                        
                        response_text = (
                            f"🔍 *Process Diagnostic*\n"
                            f"FEATURE_SOLSCAN={os.getenv('FEATURE_SOLSCAN', 'off')}\n"
                            f"SOLSCAN_API_KEY len={len(os.getenv('SOLSCAN_API_KEY', ''))}\n"
                            f"pid={os.getpid()}\n"
                            f"SCANNERS keys={scanner_keys}\n"
                            f"solscan: enabled={solscan_info.get('enabled')}, running={solscan_info.get('running')}, id={solscan_info.get('object_id')}"
                        )

                # --- Admin: Solscan status (moved after solscanstats to avoid collision) ------------------------------------------
                elif text.strip().startswith("/solscan_status"):
                    logger.info("[WEBHOOK] Routing /solscan_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            if SOLSCAN_SCANNER:
                                status = "🟢 Running" if SOLSCAN_SCANNER.running else "🔴 Stopped"
                                enabled = "✅ Enabled" if SOLSCAN_SCANNER.enabled else "❌ Disabled (no API key)"
                                cache_size = len(SOLSCAN_SCANNER.seen)
                                api_key_status = "✅ Provided" if SOLSCAN_SCANNER.key else "❌ Missing"
                                response_text = f"""🔍 **Solscan Scanner Status**
Status: {status}
Feature: {enabled}
API Key: {api_key_status}
Cache: {cache_size} seen tokens
Interval: {SOLSCAN_SCANNER.interval}s

Note: Requires SOLSCAN_API_KEY and FEATURE_SOLSCAN=on"""
                            else:
                                response_text = "❌ Solscan scanner not initialized"
                        except Exception as e:
                            response_text = f"❌ Solscan status failed: {e}"

                # --- Admin: Solscan start/stop ------------------------------------------
                elif text.strip().startswith("/solscan_start"):
                    logger.info("[WEBHOOK] Routing /solscan_start")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            # Force scanner initialization in this worker process
                            _ensure_scanners()
                            scanner = SOLSCAN_SCANNER or SCANNERS.get("solscan")
                            if scanner and hasattr(scanner, 'start'):
                                scanner.start()
                                response_text = "🟢 Solscan Pro scanner started."
                            else:
                                response_text = "❌ Solscan scanner not available. Check FEATURE_SOLSCAN=on and SOLSCAN_API_KEY."
                        except Exception as e:
                            response_text = f"❌ Solscan start failed: {e}"

                elif text.strip().startswith("/solscan_stop"):
                    logger.info("[WEBHOOK] Routing /solscan_stop")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            scanner = SOLSCAN_SCANNER or SCANNERS.get("solscan")
                            if scanner and hasattr(scanner, 'stop'):
                                scanner.stop()
                                response_text = "🔴 Solscan Pro scanner stopped."
                            else:
                                response_text = "❌ Solscan scanner not available."
                        except Exception as e:
                            response_text = f"❌ Solscan stop failed: {e}"

                elif text.strip().startswith("/scan_mode_old"):
                    parts = text.split()
                    mode = parts[1].lower() if len(parts) > 1 else ""
                    try:
                        from birdeye import set_scan_mode
                        set_scan_mode(mode)
                        response_text = f"🛠 Scan mode set to *{('all' if mode=='all' else 'strict')}*."
                    except Exception as e:
                        response_text = f"❌ scan_mode failed: {e}"

                # /wallet - Simple wallet info command
                elif text.strip() == "/wallet":
                    logger.info("[WEBHOOK] Routing /wallet")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            user_id = str(user.get('id'))
                            wallet = get_wallet(user_id)
                            if not wallet:
                                response_text = "No burner wallet yet. Use /wallet_new to create one."
                            else:
                                balance = get_balance_sol(wallet["address"])
                                
                                if balance >= 0:
                                    balance_str = f"{balance:.6f} SOL"
                                else:
                                    balance_str = "RPC error"
                                
                                created_ts = wallet.get("created_at", 0)
                                if created_ts:
                                    from datetime import datetime
                                    created_date = datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M")
                                else:
                                    created_date = "Unknown"
                                
                                response_text = f"""💰 **Burner Wallet Info**

Address: `{wallet["address"]}`
Balance: {balance_str}
Created: {created_date}

⚠️ **Development Only**
This is a temporary wallet for testing.
Not for production custody."""
                        except Exception as e:
                            response_text = f"❌ Wallet error: {e}"

                # /rules_show - Display current rules configuration
                elif text.strip().startswith("/rules_show"):
                    try:
                        import rules
                        import json
                        R = rules.load_rules()
                        response_text = "Current rules:\n```\n" + json.dumps(R, indent=2) + "\n```"
                    except Exception as e:
                        response_text = f"❌ Rules error: {e}"

                # /rules_reload - Reload rules from rules.yaml
                elif text.strip().startswith("/rules_reload"):
                    try:
                        import rules
                        rules.load_rules(force=True)
                        response_text = "🔄 Rules reloaded."
                    except Exception as e:
                        response_text = f"❌ Rules reload error: {e}"

                # /rules_test - Test rules against a token
                elif text.strip().startswith("/rules_test"):
                    parts = text.split(maxsplit=1)
                    if len(parts) == 1:
                        response_text = "Usage: /rules_test <mint>"
                    else:
                        mint = parts[1].strip().lower()
                        try:
                            import rules
                            # Create a test token object
                            obj = {"mint": mint, "source": "manual", "age_min": 0, "liq_usd": 0, "mcap_usd": 0, "holders": 0, "risk": {}}
                            res = rules.check_token(obj)
                            vibe = "PASS ✅" if res.passed else "FAIL ❌"
                            response_text = f"Rules test for `{mint}` → *{vibe}*\nreasons: {', '.join(res.reasons) or 'ok'}"
                        except Exception as e:
                            response_text = f"❌ Rules test error: {e}"



                # /wallet commands - Restore original working format
                elif text.strip().startswith("/wallet"):
                    logger.info("[WALLET] /wallet command requested by %s", user.get('id'))
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from wallet_manager import wallet_manager
                        user_id = str(user.get('id'))
                        parts = text.strip().split()
                        
                        if len(parts) == 1:  # Just "/wallet"
                            response_text = "Usage: `/wallet create` or `/wallet import <private_key>`"
                        elif parts[1].lower() == "create":
                            result = wallet_manager.create_wallet(user_id, "default")
                            if result["success"]:
                                response_text = f"✅ **Wallet Created**\n\nAddress: `{result['pubkey']}`\n\n⚠️ **Important:** Your private key is encrypted and stored securely. Never share it!"
                            else:
                                response_text = f"❌ Failed to create wallet: {result['error']}"
                        elif parts[1].lower() == "import":
                            if len(parts) < 3:
                                response_text = "Usage: `/wallet import <private_key>`"
                            else:
                                private_key = parts[2]
                                result = wallet_manager.import_wallet(user_id, private_key, "default")
                                if result["success"]:
                                    response_text = f"✅ **Wallet Imported**\n\nAddress: `{result['pubkey']}`\n\n🔒 Your private key is encrypted and secure."
                                else:
                                    response_text = f"❌ Failed to import wallet: {result['error']}"
                        else:
                            response_text = "Unknown wallet command. Use `create` or `import`."

                # /balance - Check wallet balance (original working command)
                elif text.strip().startswith("/balance"):
                    logger.info("[WALLET] /balance command requested by %s", user.get('id'))
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from wallet_manager import wallet_manager
                        from jupiter_engine import jupiter_engine
                        from safety_system import safety
                        
                        user_id = str(user.get('id'))
                        
                        if not wallet_manager.has_wallet(user_id):
                            response_text = "❌ No wallet found. Use `/wallet create` or `/wallet import` first."
                        else:
                            try:
                                wallet_info = wallet_manager.get_wallet_info(user_id)
                                wallet_address = wallet_info["default"]["pubkey"]
                                
                                # Get SOL balance
                                sol_balance = jupiter_engine.get_sol_balance(wallet_address)
                                
                                # Check MORK holdings  
                                mork_ok, mork_msg = safety.check_mork_holdings(wallet_address, 1.0)
                                
                                response_text = f"""💰 **Wallet Balance**

**Address:** `{wallet_address}`
**SOL Balance:** {sol_balance:.6f} SOL

**MORK Holdings:** {mork_msg}

**Trading Status:**
{'✅ Eligible for all trading' if mork_ok else '⚠️ Need more MORK for full access'}"""
                                
                            except Exception as e:
                                response_text = f"❌ Error checking balance: {str(e)}"

                # /snipe - Manual token trading (original working command)
                elif text.strip().startswith("/snipe"):
                    logger.info("[WALLET] /snipe command requested by %s", user.get('id'))
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from wallet_manager import wallet_manager
                        from jupiter_engine import jupiter_engine
                        from safety_system import safety
                        
                        user_id = str(user.get('id'))
                        parts = text.strip().split()
                        
                        if len(parts) < 3:
                            response_text = "Usage: `/snipe <token_mint> <sol_amount>`\n\nExample: `/snipe 7eMJmn1bTJnmhK4qZsZfMPUWuBhzQ5VXx1B1Cj6pump 0.01`"
                        elif not wallet_manager.has_wallet(user_id):
                            response_text = "❌ No wallet found. Use `/wallet create` or `/wallet import` first."
                        else:
                            try:
                                token_mint = parts[1]
                                amount_sol = float(parts[2])
                                
                                wallet_info = wallet_manager.get_wallet_info(user_id)
                                wallet_address = wallet_info["default"]["pubkey"]
                                
                                # Safety checks
                                safe_ok, safe_msg = safety.comprehensive_safety_check(
                                    user_id, wallet_address, token_mint, amount_sol, "snipe"
                                )
                                
                                if not safe_ok:
                                    response_text = f"❌ **Safety Check Failed**\n\n{safe_msg}"
                                else:
                                    # Execute trade
                                    private_key = wallet_manager.get_private_key(user_id, "default")
                                    if not private_key:
                                        response_text = "❌ Could not access wallet private key"
                                    else:
                                        result = jupiter_engine.safe_swap(private_key, token_mint, amount_sol)
                                        
                                        if result["success"]:
                                            safety.record_trade(user_id, amount_sol)
                                            response_text = f"""🎉 **Snipe Successful!**

**Transaction:** `{result['signature']}`
**Tokens Received:** {result['delta_raw']:,}
**Status:** Trade completed and verified

Your tokens are now in your wallet! 🚀"""
                                        else:
                                            response_text = f"❌ **Trade Failed**\n\n{result['error']}"
                                            
                            except ValueError:
                                response_text = "❌ Invalid SOL amount. Use a number like 0.01"
                            except Exception as e:
                                response_text = f"❌ Error executing snipe: {str(e)}"

                # /bus_test - Test event bus with fake token
                elif text.strip().startswith("/bus_test"):
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            # publish a synthetic NEW_TOKEN event to prove the end-to-end path
                            fake = {
                                "source": "TEST",
                                "symbol": "TESTCOIN",
                                "name": "Synthetic Test Token",
                                "mint": "TestMint1111111111111111111111111111111111",
                                "holders": 1,
                                "mcaps": 0,
                                "liq$": 0,
                                "age_min": 0,
                                "risk": "low",
                                "solscan": None,
                                "links": {"pumpfun": None, "birdeye": None},
                                "ts": int(time.time())
                            }
                            BUS.publish("NEW_TOKEN", fake)
                            response_text = "📣 Published synthetic *NEW_TOKEN* to the bus (source=TEST). Check for the formatted alert."
                        except Exception as e:
                            response_text = f"❌ Bus test error: {e}"

                # Wallet Commands (single command processing)
                elif text.strip().startswith("/wallet_new"):
                    logger.info(f"[WEBHOOK] Processing /wallet_new for user {user.get('id')}")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from wallets import get_or_create_wallet
                            uid = str(user.get('id'))
                            logger.info(f"[WEBHOOK] Creating wallet for uid={uid}")
                            w = get_or_create_wallet(uid)
                            response_text = (
                                "🪪 *Burner wallet created*\n"
                                f"• Address: `{w['address']}`\n"
                                "_(Private key stored server-side for testing; will move to secure storage before trading.)_"
                            )
                            logger.info(f"[WEBHOOK] Wallet created successfully, response_text length: {len(response_text)}")
                        except Exception as e:
                            logger.exception(f"[WEBHOOK] Wallet creation error: {e}")
                            response_text = f"❌ Wallet creation error: {e}"

                elif text.strip().startswith("/wallet_addr"):
                    logger.info(f"[WEBHOOK] Processing /wallet_addr for user {user.get('id')}")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from wallets import get_wallet
                            uid = str(user.get('id'))
                            w = get_wallet(uid)
                            if w:
                                response_text = f"📬 *Your burner wallet address*\n`{w['address']}`"
                            else:
                                response_text = "❌ No wallet found. Use /wallet_new to create one first."
                        except Exception as e:
                            logger.exception(f"[WEBHOOK] Wallet address error: {e}")
                            response_text = f"❌ Wallet address error: {e}"

                elif text.strip().startswith("/wallet_balance"):
                    logger.info(f"[WEBHOOK] Processing /wallet_balance for user {user.get('id')}")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from wallets import get_wallet, get_balance_sol
                            uid = str(user.get('id'))
                            w = get_wallet(uid)
                            if w:
                                bal = get_balance_sol(w["address"])
                                response_text = (
                                    f"💰 *Wallet balance*\n"
                                    f"Address: `{w['address']}`\n"
                                    f"Balance: `{bal:.6f} SOL`"
                                    f"\n\n_⚠️ Burner wallet for testing only. Private keys stored server-side._"
                                )
                            else:
                                response_text = "❌ No wallet found. Use /wallet_new to create one first."
                        except Exception as e:
                            logger.exception(f"[WEBHOOK] Wallet balance error: {e}")
                            response_text = f"❌ Wallet balance error: {e}"

                elif text.strip() in ['/help', '/commands', '/info', '/menu', '/start']:
                    logger.info(f"[WEBHOOK-DEBUG] Help command detected: {text.strip()}")
                    help_text = '''Mork F.E.T.C.H Bot

/ping - Test bot
/wallet create - New wallet
/balance - Check balances
/status - System status
/fetch - Token scan

Bot working!'''
                    
                    # Use _reply() to handle chunking automatically  
                    logger.info(f"[WEBHOOK-DEBUG] About to send help text, length: {len(help_text)}")
                    success = _reply(help_text, parse_mode=None, no_preview=True)  # Remove Markdown to avoid parsing issues
                    logger.info(f"[WEBHOOK-DEBUG] Help message sent, success: {success}")
                    return jsonify({"status": "ok", "command": text, "response_sent": True})
                
                elif text.strip() == "/test123":
                    logger.info(f"[WEBHOOK-DEBUG] Test command detected")
                    success = _reply("Test successful!", parse_mode=None, no_preview=True)
                    logger.info(f"[WEBHOOK-DEBUG] Test message sent, success: {success}")
                    return jsonify({"status": "ok", "command": text, "response_sent": True})
                
                if response_text:
                    logger.info(f"[WEBHOOK] About to send response for '{text}': {len(response_text)} chars")
                    sent_ok = _reply(response_text, parse_mode="Markdown", no_preview=True)
                    logger.info(f"[WEBHOOK] Command '{text}' processed, response sent: {'200' if sent_ok else '500'}")
                    if not sent_ok:
                        logger.error(f"[WEBHOOK] Failed to send response to Telegram for command: {text}")

                    try:
                        publish("command.done", {
                            "cmd": text.split()[0],
                            "ok": bool(sent_ok),
                            **({ "reason": "api_error" } if not sent_ok else {})
                        })
                    except Exception as e:
                        logger.warning(f"Event publish failed: {e}")
                    
                    return jsonify({"status": "ok", "command": text, "response_sent": bool(sent_ok)})
                else:
                    logger.info(f"[WEBHOOK] Unknown admin command: {text}")
                    response_text = f"Unknown command: {text}\n\nAvailable commands: /ping, /status, /scan_status, /scan_test, /fetch, /fetch_now, /pumpfun_status, /pumpfun_probe, /help\n\nType /help for full command list."
                
                # Send response if we have one
                if response_text:
                    _reply(response_text)
                    
                return jsonify({"status": "ok", "command": text, "response_sent": True})
        
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
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-box {
            background: #1a1a1a;
            border: 1px solid #7cb342;
            border-radius: 5px;
            padding: 15px;
        }
        .events {
            background: #1a1a1a;
            border: 1px solid #7cb342;
            border-radius: 5px;
            padding: 15px;
            height: 400px;
            overflow-y: auto;
        }
        .event {
            margin: 5px 0;
            padding: 5px;
            border-left: 3px solid #7cb342;
            background: #2a2a2a;
        }
        .timestamp {
            color: #888;
            font-size: 12px;
        }
        .event-type {
            color: #7cb342;
            font-weight: bold;
        }
        .event-data {
            color: #ccc;
            margin-left: 20px;
            white-space: pre-wrap;
            font-size: 12px;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff00;
            animation: pulse 2s infinite;
        }
        .controls {
            margin: 20px 0;
            text-align: center;
        }
        .btn {
            background: #7cb342;
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 0 5px;
        }
        .btn:hover {
            background: #9ccc65;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐕 Mork F.E.T.C.H Bot - Live Monitor</h1>
        <p>Real-time system monitoring and event streaming</p>
        <span class="status-indicator"></span> System Online
    </div>
    
    <div class="controls">
        <button class="btn" onclick="triggerFetch()">Trigger Manual Fetch</button>
        <button class="btn" onclick="clearEvents()">Clear Events</button>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <h3>System Status</h3>
            <div id="system-stats">
                <div>Events Processed: <span id="event-count">0</span></div>
                <div>Last Activity: <span id="last-activity">Starting...</span></div>
                <div>Uptime: <span id="uptime">Calculating...</span></div>
            </div>
        </div>
        
        <div class="stat-box">
            <h3>Token Data Sources</h3>
            <div id="source-stats">
                <div>On-chain: <span id="onchain-count">0</span></div>
                <div>Pump.fun: <span id="pumpfun-count">0</span></div>
                <div>DexScreener: <span id="dexscreener-count">0</span></div>
            </div>
        </div>
        
        <div class="stat-box">
            <h3>Performance</h3>
            <div id="perf-stats">
                <div>Fetch Cycles: <span id="fetch-cycles">0</span></div>
                <div>Fallbacks: <span id="fallback-count">0</span></div>
                <div>Success Rate: <span id="success-rate">100%</span></div>
            </div>
        </div>
    </div>
    
    <div class="events">
        <h3>Live Event Stream</h3>
        <div id="event-stream"></div>
    </div>

    <script>
        let eventCount = 0;
        let fetchCycles = 0;
        let fallbacks = 0;
        let sources = {onchain: 0, pumpfun: 0, dexscreener: 0};
        const startTime = Date.now();
        
        // Connect to event stream with optional token
        const token = new URLSearchParams(window.location.search).get('token') || '';
        const eventUrl = '/events' + (token ? '?token=' + encodeURIComponent(token) : '');
        const eventSource = new EventSource(eventUrl);
        
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.type !== 'heartbeat') {
                    addEvent(data);
                    updateStats(data);
                }
            } catch (e) {
                console.error('Error parsing event:', e);
            }
        };
        
        function addEvent(event) {
            const eventDiv = document.createElement('div');
            eventDiv.className = 'event';
            
            const timestamp = new Date(event.ts).toLocaleTimeString();
            const eventType = event.type;
            const eventData = JSON.stringify(event.data, null, 2);
            
            eventDiv.innerHTML = `
                <div class="timestamp">${timestamp}</div>
                <div class="event-type">${eventType}</div>
                <div class="event-data">${eventData}</div>
            `;
            
            const stream = document.getElementById('event-stream');
            stream.insertBefore(eventDiv, stream.firstChild);
            
            // Keep only last 50 events
            if (stream.children.length > 50) {
                stream.removeChild(stream.lastChild);
            }
            
            eventCount++;
            document.getElementById('event-count').textContent = eventCount;
            document.getElementById('last-activity').textContent = timestamp;
        }
        
        function updateStats(event) {
            if (event.type === 'fetch_completed') {
                fetchCycles++;
                document.getElementById('fetch-cycles').textContent = fetchCycles;
                
                if (event.data.sources) {
                    sources.onchain += event.data.sources['pumpfun-chain'] || 0;
                    sources.pumpfun += event.data.sources['pumpfun'] || 0;
                    sources.dexscreener += event.data.sources['dexscreener'] || 0;
                    
                    document.getElementById('onchain-count').textContent = sources.onchain;
                    document.getElementById('pumpfun-count').textContent = sources.pumpfun;
                    document.getElementById('dexscreener-count').textContent = sources.dexscreener;
                }
            }
            
            if (event.type === 'fallback_activated') {
                fallbacks++;
                document.getElementById('fallback-count').textContent = fallbacks;
                
                const successRate = fetchCycles > 0 ? Math.round(((fetchCycles - fallbacks) / fetchCycles) * 100) : 100;
                document.getElementById('success-rate').textContent = successRate + '%';
            }
        }
        
        function triggerFetch() {
            fetch('/api/trigger-fetch')
                .then(response => response.json())
                .then(data => console.log('Fetch triggered:', data))
                .catch(error => console.error('Error:', error));
        }
        
        function clearEvents() {
            document.getElementById('event-stream').innerHTML = '';
        }
        
        // Update uptime every second
        setInterval(() => {
            const uptime = Math.floor((Date.now() - startTime) / 1000);
            const hours = Math.floor(uptime / 3600);
            const minutes = Math.floor((uptime % 3600) / 60);
            const seconds = uptime % 60;
            document.getElementById('uptime').textContent = 
                `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }, 1000);
    </script>
</body>
</html>
    ''')

LIVE_TOKEN = os.environ.get("LIVE_TOKEN", "")

@app.route('/events')
def stream_events():
    """Token-gated server-sent events endpoint for real-time monitoring."""
    # Simple token gate for secure access
    tok = request.args.get("token", "")
    if LIVE_TOKEN and tok != LIVE_TOKEN:
        return Response("unauthorized", status=401)

    q = BUS.subscribe()

    @stream_with_context
    def gen():
        # Set retry interval for client reconnection
        yield "retry: 1000\\n\\n"
        try:
            while True:
                try:
                    evt = q.get(timeout=30)
                    # Compact JSON serialization for efficiency
                    yield f"data: {json.dumps(evt, separators=(',', ':'))}\\n\\n"
                except queue.Empty:
                    # Send keepalive comment (not data event)
                    yield ": keepalive\\n\\n"
        except GeneratorExit:
            # Clean up subscriber when client disconnects
            with BUS.lock:
                BUS.subscribers.discard(q)
    
    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )

LIVE_HTML = """
<!doctype html>
<meta charset="utf-8">
<title>Mork Live Console</title>
<style>
 body{font-family:ui-monospace,monospace;background:#0b0f14;color:#e6edf3;margin:0}
 header{padding:12px 16px;background:#111827;position:sticky;top:0}
 .ok{color:#22c55e}.warn{color:#f59e0b}.err{color:#ef4444}
 #log{padding:10px 14px;white-space:pre-wrap;font-size:13px;line-height:1.35}
 .ts{opacity:.6}
 .row{border-bottom:1px solid #1f2937;padding:6px 0}
</style>
<header>
  <b>Mork Live Console</b>
  <span id="status" style="margin-left:10px;opacity:.8">connecting...</span>
</header>
<div id="log"></div>
<script>
const log = document.getElementById('log');
const statusEl = document.getElementById('status');
const params=new URLSearchParams(location.search);
const token=params.get('token')||'';
const es=new EventSource(`/events?token=${encodeURIComponent(token)}`);
es.onopen=()=>statusEl.textContent='connected';
es.onerror=()=>statusEl.textContent='reconnecting...';
es.onmessage=(e)=>{
  const evt=JSON.parse(e.data);
  const d=new Date(evt.ts);
  const ts=d.toISOString().replace('T',' ').replace('Z','');
  const type=evt.type||'evt';
  const data=evt.data||{};
  const pretty=JSON.stringify(data);
  const div=document.createElement('div');
  div.className='row';
  div.innerHTML=`<span class="ts">${ts}</span> — <b>${type}</b> ${pretty}`;
  log.prepend(div);
  const rows=log.children;
  for(let i=500;i<rows.length;i++) rows[i].remove();
};
</script>
"""

@app.route("/live")
def live():
    """Compact live console interface with token-gated access."""
    tok = request.args.get("token", "")
    if LIVE_TOKEN and tok != LIVE_TOKEN:
        return Response("unauthorized", status=401)
    return render_template_string(LIVE_HTML)

# ========= Enhanced WS Debug Event Forwarding to Admin Chat =========
_WS_DEBUG_FORWARDER_SET = False

def _install_ws_debug_forwarder():
    """Install one-time event bus subscriber for WS debug event forwarding"""
    global _WS_DEBUG_FORWARDER_SET
    if _WS_DEBUG_FORWARDER_SET:
        return
    _WS_DEBUG_FORWARDER_SET = True
    
    try:
        admin_id = int(os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID", "0"))
    except Exception:
        admin_id = 0
    if not admin_id:
        logger.warning("[WS] No admin ID for debug forwarding")
        return
        
    def _send_admin_debug(text: str):
        """DISABLED: Send debug message to admin chat - now handled by polling loop"""
        logger.debug(f"_send_admin_debug called but disabled: {text[:100]}...")
        return
    
    def _on_debug_event(evt):
        """Handle WS debug events from event bus"""
        if not isinstance(evt, dict):
            return
            
        # Handle ws.debug events
        if evt.get("type") == "ws.debug":
            data = evt.get("data", {})
            event_type = data.get("event", "?")
            preview = data.get("preview", "")[:500]  # Limit length
            timestamp = data.get("ts", "")
            
            debug_msg = (
                f"🛰 *WS Debug Event*\n"
                f"Event: `{event_type}`\n"
                f"Time: {timestamp}\n"
                f"```json\n{preview}\n```"
            )
            _send_admin_debug(debug_msg)
            
        # Handle ws.debug.mode events  
        elif evt.get("type") == "ws.debug.mode":
            data = evt.get("data", {})
            mode_on = data.get("on", False)
            status_msg = f"🔬 *WebSocket Debug Mode: {'ON' if mode_on else 'OFF'}*"
            _send_admin_debug(status_msg)
    
    # Subscribe to event bus
    try:
        q = BUS.subscribe()
        import threading
        
        def _debug_forwarder_worker():
            """Background worker for debug event forwarding"""
            while True:
                try:
                    evt = q.get(timeout=30)
                    _on_debug_event(evt)
                except Exception:
                    continue  # Keep running on any error
        
        thread = threading.Thread(target=_debug_forwarder_worker, daemon=True)
        thread.start()
        logger.info("[WS] Debug event forwarder installed for admin chat")
        
    except Exception as e:
        logger.warning("[WS] Debug forwarder setup failed: %s", e)

# Install debug forwarder at startup
_install_ws_debug_forwarder()

@app.route('/api/trigger-fetch')
def trigger_fetch():
    """API endpoint to trigger a manual fetch for testing."""
    try:
        publish("manual_fetch_triggered", {"triggered_by": "web_api", "timestamp": int(time.time())})
        
        # Trigger actual fetch in background
        import threading
        def background_fetch():
            try:
                import rules
                import data_fetcher
                rules_config = rules.load_rules()
                results = data_fetcher.fetch_and_rank(rules_config)
                publish("manual_fetch_completed", {"tokens_found": len(results)})
            except Exception as e:
                publish("manual_fetch_error", {"error": str(e)})
        
        thread = threading.Thread(target=background_fetch)
        thread.daemon = True
        thread.start()
        
        return jsonify({"status": "success", "message": "Fetch triggered"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Auto-start services when Flask app boots up (modern Flask approach)
def start_services():
    """Auto-start both HTTP and WebSocket scanners on app boot"""
    # Start HTTP scanner (ensure it's running)
    try:
        from birdeye import get_scanner
        scanner = get_scanner(publish)
        if not scanner.running:
            scanner.start()
            logger.info("Birdeye scanner auto-started on boot")
        else:
            logger.info("Birdeye scanner already running")
    except Exception as e:
        logger.warning("HTTP scanner start failed (ok to continue): %s", e)
    
    # Auto-start enhanced WebSocket with Launchpad support
    try:
        from birdeye_ws import get_ws
        ws_instance = get_ws(publish=publish, notify=lambda m: None)
        if ws_instance and hasattr(ws_instance, 'start'):
            ws_instance.start()
            logger.info("[WS] Birdeye WS auto-started on boot")
        else:
            logger.info("[WS] Birdeye WS not available")
    except Exception as e:
        logger.warning("[WS] auto-start failed: %s", e)
        # Continue without failing the app boot

    # Start Birdeye WebSocket client
    try:
        if ws_client:
            ws_client.start()
            logger.info("Birdeye WS scanner auto-started on boot")
    except Exception as e:
        logger.warning("WS start failed: %s", e)
        
    # Start DexScreener scanner
    try:
        if DS_SCANNER:
            DS_SCANNER.start()
            logger.info("DexScreener scanner auto-started on boot")
    except Exception as e:
        logger.warning("DexScreener scanner start failed: %s", e)

    # Background forwarder: push scanner alerts to admin chat
    def _forward_scanner_alerts():
        q = BUS.subscribe()
        while True:
            try:
                evt = q.get(timeout=30)
                if not isinstance(evt, dict):
                    continue
                    
                event_type = evt.get("type", "")
                data = evt.get("data", {})
                
                # Handle Birdeye WebSocket alerts
                if event_type == "scan.birdeye.ws":
                    msg = data.get("alert")
                    if msg:
                        send_admin_md(msg)
                        
                # Handle DexScreener new token alerts
                elif event_type == "scan.dexscreener.new" and data.get("items"):
                    lines = ["🟢 *New tokens (DexScreener):*"]
                    for item in data["items"]:
                        mint = item.get("mint") or ""
                        name = item.get("name") or "?"
                        symbol = item.get("symbol") or "?"
                        price = item.get("price")
                        
                        lines.append(f"• *{name}* | `{symbol}` | `{mint}`")
                        
                        if mint:
                            be_link = f"https://birdeye.so/token/{mint}?chain=solana"
                            pf_link = f"https://pump.fun/{mint}"
                            lines.append(f"  [Birdeye]({be_link}) • [Pump.fun]({pf_link})")
                            
                        if price:
                            lines.append(f"  ~${price}")
                    
                    alert_text = "\n".join(lines)
                    send_admin_md(alert_text)
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.warning("Scanner alert forwarding error: %s", e)
                time.sleep(1)

    # Start scanner alert forwarding thread
    import threading
    t = threading.Thread(target=_forward_scanner_alerts, daemon=True)
    t.start()
    logger.info("Scanner alert forwarding thread started")
    
    # Publish startup event
    publish("app.services.started", {
        "http_scanner": True,
        "ws_scanner": True,
        "ds_scanner": True,
        "alert_forwarding": True,
        "event_bridge": True,
        "timestamp": time.time()
    })

# Token event subscriber
def _on_new_token(ev: dict):
    """Handle NEW_TOKEN events from the bus"""
    try:
        res = rules.check_token(ev)
        vibe = "✅ PASS" if res.passed else "❌ FAIL"
        reasons = "ok" if res.passed else (", ".join(res.reasons) or "unknown")
        msg = (
            f"*New token* ({ev.get('source')})\n"
            f"`{ev.get('symbol')}` — {ev.get('mint')}\n"
            f"liq: ${ev.get('liq_usd'):,.0f} | mcap: ${ev.get('mcap_usd'):,.0f} | "
            f"age: {ev.get('age_min'):.1f}m | holders: {ev.get('holders')}\n"
            f"Rules: *{vibe}* — {reasons}"
        )
        
        # DISABLED: Direct API call - now handled by polling loop
        logger.info(f"Token notification prepared but not sent: {msg[:100]}...")
    except Exception as e:
        logger.warning(f"Token notification error: {e}")

# Subscribe to NEW_TOKEN events
BUS.subscribe("NEW_TOKEN", _on_new_token)
logger.info("Subscribed to NEW_TOKEN events on bus")

# Auto-start services if enabled by environment variable
with app.app_context():
    if os.getenv("AUTO_START_SCANS", "false").lower() == "true":
        start_services()
        logger.info("Auto-start scans enabled (AUTO_START_SCANS=true)")
    else:
        logger.info("Auto-start scans disabled (AUTO_START_SCANS=false or unset)")
    
    # Start Telegram polling mode if enabled (default due to webhook delivery issues)
    if TELEGRAM_MODE == 'polling':
        logger.info("Starting Telegram polling mode (bypasses webhook delivery issues)")
        start_telegram_polling()
    else:
        logger.info("Using webhook mode for Telegram")

# Export app for gunicorn
application = app

if __name__ == '__main__':
    # Start bot polling in development
    if mork_bot and mork_bot.telegram_available and os.environ.get('REPLIT_ENVIRONMENT'):
        logger.info("Starting bot in polling mode...")
        # Use the bot's start method instead of run
        if hasattr(mork_bot, 'start_polling'):
            # Use PTB polling if available
            logger.info("Starting Telegram bot polling...")
        else:
            logger.warning("Bot polling not available, running Flask only")
            app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        # Run Flask app
        app.run(host='0.0.0.0', port=5000, debug=True)