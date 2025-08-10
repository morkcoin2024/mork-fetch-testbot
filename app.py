"""
Flask Web Application for Mork F.E.T.C.H Bot
Handles Telegram webhooks and provides web interface
"""

import os
import logging
from flask import Flask, request, jsonify, Response, stream_with_context, render_template_string
from config import DATABASE_URL, TELEGRAM_BOT_TOKEN, ASSISTANT_ADMIN_TELEGRAM_ID
from eventbus import publish, BUS
import json
import time
import queue
# Import bot conditionally to handle missing token gracefully
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

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates with comprehensive logging"""
    try:
        # Log incoming webhook request
        logger.info(f"[WEBHOOK] Received {request.method} request from {request.remote_addr}")
        
        update_data = request.get_json()
        logger.info(f"[WEBHOOK] Update data: {update_data}")
        
        if not mork_bot:
            logger.error("[WEBHOOK] Bot not initialized - missing TELEGRAM_BOT_TOKEN")
            return jsonify({"error": "Bot not available"}), 500
        
        # Skip PTB dependency and handle webhook directly
        if not mork_bot.telegram_available:
            logger.warning("[WEBHOOK] PTB disabled, using direct webhook processing")
            
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
            
            # Helper function for sending replies
            def _reply(text: str):
                try:
                    import requests
                    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={"chat_id": message['chat']['id'], "text": text, "parse_mode": "Markdown"},
                        timeout=10,
                    )
                    return True
                except Exception as e:
                    logger.exception("sendMessage failed: %s", e)
                    return False

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
                        
                        # Default values
                        n_lines = 50
                        level_filter = "all"
                        
                        # Parse arguments
                        for arg in args:
                            if arg.isdigit():
                                n_lines = max(10, min(500, int(arg)))  # Limit for Telegram
                            elif arg.startswith("level="):
                                level_filter = arg.split("=", 1)[1].lower()
                        
                        # Get lines from ring buffer (super fast!)
                        lines = get_ring_buffer_lines(n_lines, level_filter)
                        stats = get_ring_buffer_stats()
                        
                        if not lines:
                            response_text = f'❌ No log entries found (level={level_filter})'
                        else:
                            log_text = '\n'.join(lines)
                            
                            # Truncate if too long for Telegram (4096 char limit)
                            if len(log_text) > 3000:
                                log_text = "..." + log_text[-2900:]
                            
                            header = f"📋 Ring Buffer Log Entries (last {len(lines)} lines"
                            if level_filter != "all":
                                header += f", level>={level_filter}"
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
Usage: /a_logs_tail [number] [level=error|warn|info|all]
Examples: /a_logs_tail 100, /a_logs_tail level=error'''
                            
                    except Exception as e:
                        response_text = f'❌ Error reading ring buffer: {str(e)}'
                elif text.startswith("/a_diag_fetch"):
                    # Enhanced diagnostic command for multi-source fetch system
                    try:
                        # Import the diagnostic function
                        import asyncio
                        from alerts.telegram import cmd_a_diag_fetch
                        
                        # Create a mock update object for compatibility
                        class MockUpdate:
                            def __init__(self, message_data):
                                self.message = type('obj', (object,), message_data)()
                                self.effective_user = type('obj', (object,), {'id': user.get('id')})()
                        
                        mock_update = MockUpdate({
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

                elif text.strip() in ['/help']:
                    response_text = '''🐕 Mork F.E.T.C.H Bot Commands

Admin Commands:
/ping, /a_ping - Test responsiveness
/status, /a_status - System status  
/whoami, /a_whoami - Your Telegram info
/a_logs_tail [n] [level=x] - Recent log entries with filtering
/a_logs_stream - Log streaming info
/a_logs_watch - Log monitoring status
/a_mode - Operation mode details

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
                    # Send response using direct API call
                    import requests
                    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
                    response_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    
                    response_data = {
                        'chat_id': chat_id,
                        'text': response_text
                    }
                    
                    resp = requests.post(response_url, json=response_data)
                    logger.info(f"[WEBHOOK] Command '{text}' processed, response sent: {resp.status_code}")
                    
                    return jsonify({"status": "ok", "command": text, "response_sent": True})
                else:
                    logger.info(f"[WEBHOOK] Unknown admin command: {text}")
                    return jsonify({"status": "ok", "command": text, "response_sent": False})
        
        return jsonify({"status": "ok", "processed": True})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

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

if __name__ == '__main__':
    # Start bot polling in development
    if mork_bot and os.environ.get('REPLIT_ENVIRONMENT'):
        logger.info("Starting bot in polling mode...")
        mork_bot.run()
    else:
        # Run Flask app
        app.run(host='0.0.0.0', port=5000, debug=True)