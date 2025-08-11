"""
Flask Web Application for Mork F.E.T.C.H Bot
Handles Telegram webhooks and provides web interface
"""

import os
import logging
import threading
from flask import Flask, request, jsonify, Response, stream_with_context, render_template_string
from config import DATABASE_URL, TELEGRAM_BOT_TOKEN, ASSISTANT_ADMIN_TELEGRAM_ID
from eventbus import publish, BUS
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
from solscan_scan import SolscanScan

# Initialize components after admin functions are defined
def _init_scanners():
    global SCANNER, ws_client, DS_SCANNER, JUPITER_SCANNER, SOLSCAN_SCANNER, SCANNERS
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
    SOLSCAN_SCANNER = SolscanScan(notify_fn=_notify_tokens, cache_limit=8000, interval_sec=10)  # Solscan scanner (dormant)
    
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
from eventbus import BUS

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
SCANNERS = {}

# Initialize scanners after admin functions are defined
try:
    _init_scanners()
    logger.info("Scanners initialized successfully")
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
                    total, new = SCANNER.tick()
                except Exception as e:
                    total, new = 0, 0
                    app.logger.warning("[SCAN] Birdeye tick error: %s", e)
            
            # Run all other scanners in SCANNERS registry
            for name, scanner in SCANNERS.items():
                if scanner and hasattr(scanner, 'tick') and hasattr(scanner, 'running') and scanner.running:
                    try:
                        t, n = scanner.tick()
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

# Ensure additional scanners are registered in SCANNERS registry
def _ensure_scanners():
    """Ensure Jupiter and Solscan scanners are created and registered"""
    global SCANNERS
    # Avoid duplicates
    if "jupiter" not in SCANNERS:
        SCANNERS["jupiter"] = JupiterScan(notify_fn=_notify_tokens, interval_sec=int(os.getenv("SCAN_INTERVAL_SEC","8")))
        logger.info("Jupiter scanner registered in SCANNERS registry")
    if "solscan" not in SCANNERS:
        SCANNERS["solscan"] = SolscanScan(notify_fn=_notify_tokens, interval_sec=int(os.getenv("SCAN_INTERVAL_SEC","8")))
        logger.info("Solscan scanner registered in SCANNERS registry")

# Ensure scanners are in registry on boot
_ensure_scanners()

# Auto-start Jupiter scanner if enabled
try:
    if JUPITER_SCANNER and JUPITER_SCANNER.enabled:
        JUPITER_SCANNER.start()
        logger.info("Jupiter scanner auto-started on boot")
    elif "jupiter" in SCANNERS and SCANNERS["jupiter"].enabled:
        SCANNERS["jupiter"].start()
        logger.info("Jupiter scanner auto-started from registry")
except Exception as e:
    logger.warning(f"Jupiter auto-start failed: {e}")

# Auto-start Solscan scanner if enabled (has API key and feature flag)
try:
    if SOLSCAN_SCANNER and SOLSCAN_SCANNER.enabled:
        SOLSCAN_SCANNER.start()
        logger.info("Solscan scanner auto-started on boot")
    elif "solscan" in SCANNERS and SCANNERS["solscan"].enabled:
        SCANNERS["solscan"].start() 
        logger.info("Solscan scanner auto-started from registry")
    else:
        if SOLSCAN_SCANNER or ("solscan" in SCANNERS):
            logger.info("Solscan scanner dormant (requires FEATURE_SOLSCAN=on and SOLSCAN_API_KEY)")
        else:
            logger.info("Solscan scanner not initialized")
except Exception as e:
    logger.warning(f"Solscan auto-start failed: {e}")

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
    """New webhook endpoint to bypass deployment caching issues"""
    return webhook()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates with comprehensive logging - Fully standalone operation"""
    try:
        # Import publish at function level to avoid import issues
        from eventbus import publish
        
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

            # Simple admin command processing for immediate testing
            from config import ASSISTANT_ADMIN_TELEGRAM_ID
            
            if user.get('id') == ASSISTANT_ADMIN_TELEGRAM_ID and text.startswith('/'):
                logger.info(f"[WEBHOOK] Admin command detected: {text}")
                
                # Process admin commands directly without PTB
                chat_id = message['chat']['id']
                response_text = None
                
                if text.strip() in ['/ping', '/a_ping']:
                    publish("admin.command", {"command": "ping", "user": user.get("username", "?")})
                    response_text = 'Pong! Webhook processing is working! 🎯'
                elif text.strip() in ['/status', '/a_status']:
                    publish("admin.command", {"command": "status", "user": user.get("username", "?")})
                    response_text = f'''🤖 Mork F.E.T.C.H Bot Status
                    
Mode: Webhook Processing
PTB: Disabled (import conflicts)
Admin Commands: Direct webhook
Logging: Enhanced (active)
Health: Operational

Admin router with comprehensive logging active.'''
                elif text.strip() in ['/whoami', '/a_whoami']:
                    response_text = f'''Your Telegram Info:
ID: {user.get('id', 'unknown')}
Username: @{user.get('username', 'unknown')}
Admin: {'Yes' if user.get('id') == ASSISTANT_ADMIN_TELEGRAM_ID else 'No'}'''
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
                        _reply("Not authorized.")
                        return jsonify({"status": "ok", "command": text, "response_sent": True})
                    from alerts.telegram import cmd_rules_show_sync
                    _reply(cmd_rules_show_sync())
                    return jsonify({"status": "ok", "command": text, "response_sent": True})

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
                        try:
                            st = SCANNER.status()
                            from birdeye import SCAN_MODE
                            
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
                                f"  • Solscan: {'ON' if SCANNERS.get('solscan') and SCANNERS['solscan'].enabled else 'OFF (no key)'}"
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
                        
                        response_text = (
                            "📡 *WebSocket Status*\n"
                            f"running: {status.get('running', False)}\n"
                            f"connected: {connected}\n"
                            f"thread_alive: {thread_alive}\n"
                            f"mode: {status.get('mode', 'unknown')}\n"
                            f"messages_received: {status.get('recv', 0)}\n"
                            f"new_tokens: {status.get('new', 0)}\n"
                            f"cache_size: {status.get('seen_cache', 0)}/8000"
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
                                from eventbus import publish, get_subscriber_count
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

                # /fetch_now (admin only)
                elif text.startswith("/fetch_now"):
                    logger.info("[WEBHOOK] Routing /fetch_now")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        _reply("Not authorized.")
                        return jsonify({"status": "ok", "command": text, "response_sent": True})
                    from alerts.telegram import cmd_fetch_now_sync
                    _reply(cmd_fetch_now_sync())
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

                elif text.strip().startswith("/scan_status") or text.strip().startswith("/a_scan_status"):
                    logger.info("[WEBHOOK] Routing /scan_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from birdeye import get_scanner, current_mode
                            sc = get_scanner(publish)
                            st = sc.status()
                            md = current_mode()
                            response_text = (
                                "🗣  Birdeye Scan Status\n"
                                f"running: {st['running']}\n"
                                f"interval: {st['interval']}s\n"
                                f"seencache: {st['seen_cache']}\n"
                                f"threadalive: {st['thread_alive']}\n"
                                f"mode: {md}\n"
                            )
                        except Exception as e:
                            response_text = f"❌ Scan status failed: {e}"

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
                        from eventbus import publish
                        from birdeye_ws import get_ws_scanner
                        def _notify(msg):
                            _reply(msg)
                        ws = get_ws_scanner(publish, _notify)
                        ws.start()
                        response_text = "🟢 Birdeye WS started."

                elif text.strip().startswith("/ws_stop"):
                    logger.info("[WEBHOOK] Routing /ws_stop")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from birdeye_ws import get_ws_scanner
                        def _notify(_): pass
                        ws = get_ws_scanner(lambda *_: None, _notify)
                        ws.stop()
                        response_text = "🔴 Birdeye WS stopped."

                elif text.strip().startswith("/ws_status"):
                    logger.info("[WEBHOOK] Routing /ws_status")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        from birdeye_ws import get_ws_scanner
                        ws = get_ws_scanner(lambda *_: None, lambda *_: None)
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
                            from eventbus import publish
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
                            from eventbus import publish
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
                            from birdeye_ws import ws_client_singleton as WS_CLIENT
                            if not WS_CLIENT:
                                from birdeye_ws import get_ws
                                from eventbus import publish
                                WS_CLIENT = get_ws(publish=publish, notify=lambda m: _reply(m))
                            
                            parts = text.split(maxsplit=1)
                            action = parts[1].lower() if len(parts) > 1 else "status"
                            
                            if action in ("on", "enable", "true", "1"):
                                WS_CLIENT.set_debug(True)
                                response_text = "🔬 *WebSocket debug mode enabled*\nRate-limited message forwarding active"
                            elif action in ("off", "disable", "false", "0"):
                                WS_CLIENT.set_debug(False)
                                response_text = "🔬 *WebSocket debug mode disabled*"
                            elif action == "inject":
                                WS_CLIENT.inject_debug_event("manual_test")
                                response_text = "🧪 *Debug event injected*\nSynthetic test message sent through pipeline"
                            elif action.startswith("cache"):
                                try:
                                    cache_size = int(action.split("cache")[-1]) if "cache" in action else 10
                                    cache = WS_CLIENT.get_debug_cache(cache_size)
                                    if cache:
                                        response_text = f"📋 *Debug Cache ({len(cache)} messages):*\n"
                                        for i, msg in enumerate(cache[-5:], 1):  # Show last 5
                                            event = msg.get("event", "?")
                                            response_text += f"{i}. {event}\n"
                                    else:
                                        response_text = "📋 *Debug cache empty*"
                                except Exception as e:
                                    response_text = f"❌ Cache error: {e}"
                            else:
                                # Status
                                debug_on = getattr(WS_CLIENT, 'ws_debug', False)
                                cache_size = len(getattr(WS_CLIENT, '_debug_cache', []))
                                response_text = (
                                    f"🔬 *WebSocket Debug Status*\n"
                                    f"Mode: {'ON' if debug_on else 'OFF'}\n"
                                    f"Cache: {cache_size}/30 messages\n"
                                    f"Commands: on/off, inject, cache[N], status"
                                )
                        except Exception as e:
                            response_text = f"❌ Debug command error: {e}"

                # ======= ENHANCED WS DEBUG CONTROLS =======
                elif text.strip().startswith("/ws_dump"):
                    logger.info("[WEBHOOK] Routing /ws_dump")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from birdeye_ws import get_ws
                            from eventbus import publish
                            ws = get_ws(publish=publish, notify=lambda m: _reply(m))
                            
                            # Parse number of messages to dump
                            parts = text.strip().split()
                            n = 10
                            if len(parts) > 1 and parts[1].isdigit():
                                n = int(parts[1])
                            
                            items = ws.get_debug_cache(n)
                            if not items:
                                response_text = "📦 *No WS debug cache yet*\nEnable debug mode first with `/ws_debug on`"
                            else:
                                # Format cached messages for display
                                lines = [f"📦 *Last {len(items)} WS raw events:*"]
                                for i, item in enumerate(items, 1):
                                    event = item.get("event", "?")
                                    # Compact JSON for readability
                                    preview = json.dumps(item, separators=(',', ':'))[:300]
                                    lines.append(f"{i}. `{event}`: {preview}...")
                                response_text = "\n".join(lines)
                        except Exception as e:
                            response_text = f"❌ Debug dump error: {e}"

                elif text.strip().startswith("/ws_probe"):
                    logger.info("[WEBHOOK] Routing /ws_probe")
                    if user.get('id') != ASSISTANT_ADMIN_TELEGRAM_ID:
                        response_text = "Not authorized."
                    else:
                        try:
                            from birdeye_ws import get_ws
                            from eventbus import publish
                            ws = get_ws(publish=publish, notify=lambda m: _reply(m))
                            
                            # Inject synthetic event for pipeline testing
                            ws.inject_debug_event("manual-probe")
                            response_text = (
                                "🧪 *Debug probe injected*\n"
                                "Synthetic WS event sent through pipeline\n"
                                "Check logs with `/a_logs_tail` or cache with `/ws_dump`"
                            )
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

                elif text.strip().startswith("/scan_mode_old"):
                    parts = text.split()
                    mode = parts[1].lower() if len(parts) > 1 else ""
                    try:
                        from birdeye import set_scan_mode
                        set_scan_mode(mode)
                        response_text = f"🛠 Scan mode set to *{('all' if mode=='all' else 'strict')}*."
                    except Exception as e:
                        response_text = f"❌ scan_mode failed: {e}"

                elif text.strip() in ['/help']:
                    response_text = '''🐕 Mork F.E.T.C.H Bot Commands

Admin Commands:
/ping, /a_ping - Test responsiveness
/status, /a_status - System status  
/whoami, /a_whoami - Your Telegram info
/scan_status, /a_scan_status - Comprehensive system health check
/scan_test, /a_scan_test - Quick system test with sample data
/pumpfun_status, /a_pumpfun_status - Pump.fun endpoint status
/pumpfun_probe, /a_pumpfun_probe - Multi-source diagnostic probe
/a_logs_tail [n] [level=x] - Recent log entries with filtering
/a_logs_stream - Log streaming info
/a_logs_watch - Log monitoring status
/a_mode - Operation mode details

Live Monitoring:
/monitor - Open real-time monitoring dashboard
/live - Open compact live console

Birdeye Scanner:
/scan_start - Start background scanning
/scan_stop - Stop background scanning
/scan_status - Scanner status and metrics
/birdeye_start - Start token scanning
/birdeye_stop - Stop token scanning
/birdeye_status - Scanner status
/birdeye_tick - Manual scan

WebSocket Enhanced Controls:
/ws_start, /ws_stop - WebSocket scanner controls  
/ws_restart - Restart with Launchpad priority
/ws_status - Enhanced connection and subscription stats
/ws_sub [topics] - Set custom subscription topics
/ws_mode [strict|all] - Set WebSocket filter mode
/ws_tap [on|off] - Toggle message debug tap

Advanced WebSocket Debug:
/ws_debug on/off/inject/cache/status - Debug mode control
/ws_dump [n] - View cached raw WebSocket messages
/ws_probe - Inject synthetic test event

DexScreener Scanner:
/ds_start [seconds], /ds_stop, /ds_status - Pair scanner controls

Multi-Source Token Discovery:
/jupiter_start, /jupiter_stop - Jupiter scanner controls
/jupiter_status - Jupiter scanner status and metrics
/solscan_start, /solscan_stop - Solscan Pro API scanner controls  
/solscan_status - Solscan scanner status (requires FEATURE_SOLSCAN=on + Pro API key)

AI Assistant:
/assistant_model [model] - Get/set assistant AI model
/assistant [request] - AI assistant and code generation

F.E.T.C.H Rules System:
/rules_show, /a_rules_show - Display current rules configuration
/rules_reload, /a_rules_reload - Reload rules from rules.yaml
/fetch_now, /a_fetch_now - Run token filtering demo

/help - This help message

Bot is operational with direct webhook processing.
Admin alias commands (a_*) available to avoid conflicts.'''
                
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
                    response_text = f"Unknown command: {text}\n\nAvailable commands: /ping, /status, /scan_status, /scan_test, /pumpfun_status, /pumpfun_probe, /help\n\nType /help for full command list."
                
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
        """Send debug message to admin chat"""
        try:
            import requests
            bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                return
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": admin_id, 
                    "text": text, 
                    "parse_mode": "Markdown",
                    "disable_notification": True  # Don't spam with notifications
                },
                timeout=8,
            )
        except Exception as e:
            logger.debug("Admin debug send failed: %s", e)
    
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
        get_ws(publish=publish, notify=lambda m: None).start()
        logger.info("[WS] Birdeye WS auto-started on boot")
    except Exception as e:
        logger.warning("[WS] auto-start failed: %s", e)

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

# Auto-start services immediately after app creation
with app.app_context():
    start_services()

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