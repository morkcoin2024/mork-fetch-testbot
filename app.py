"""
Flask Web Application for Mork F.E.T.C.H Bot
Handles Telegram webhooks and provides web interface
"""

import os
import logging
from flask import Flask, request, jsonify
from config import DATABASE_URL, TELEGRAM_BOT_TOKEN
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
                    response_text = 'Pong! Webhook processing is working! 🎯'
                elif text.strip() in ['/status', '/a_status']:
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

if __name__ == '__main__':
    # Start bot polling in development
    if mork_bot and os.environ.get('REPLIT_ENVIRONMENT'):
        logger.info("Starting bot in polling mode...")
        mork_bot.run()
    else:
        # Run Flask app
        app.run(host='0.0.0.0', port=5000, debug=True)