#!/usr/bin/env python3
"""
Minimal webhook-only Flask app for Telegram bot
"""
import os
import sys
import logging
from flask import Flask, request, jsonify
import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Get bot token
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found")
    sys.exit(1)

def send_telegram_message(chat_id, text):
    """Send message via Telegram API"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.ok:
            result = response.json().get('result', {})
            msg_id = result.get('message_id')
            logger.info(f"✅ Sent message_id={msg_id} to chat_id={chat_id}")
            return True
        else:
            logger.error(f"Failed to send message: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def process_command(text, user_id, chat_id):
    """Process Telegram commands"""
    text = text.strip().lower()
    
    if text.startswith('/ping'):
        return "🤖 Pong! Webhook mode active and working perfectly!"
    
    elif text.startswith('/status'):
        return "✅ Mork F.E.T.C.H Bot\n📡 Webhook Mode: ON\n🔧 Status: Operational"
    
    elif text.startswith('/help'):
        return """🐕 **Mork F.E.T.C.H Bot Help**

Available commands:
• `/ping` - Test bot connectivity
• `/status` - Check bot status
• `/help` - Show this help

Bot is running in webhook mode for maximum reliability."""

    elif text.startswith('/'):
        return f"Command `{text}` is not recognized. Use /help for available commands."
    
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook"""
    try:
        update = request.get_json()
        if not update:
            return jsonify({"status": "no_data"}), 400
        
        logger.info(f"[WEBHOOK] Received update: {update.get('update_id')}")
        
        # Extract message info
        message = update.get('message', {})
        text = message.get('text', '')
        user = message.get('from', {})
        chat = message.get('chat', {})
        
        user_id = user.get('id')
        chat_id = chat.get('id')
        
        if not text or not chat_id:
            return jsonify({"status": "no_text_or_chat"}), 200
        
        logger.info(f"[WEBHOOK] Processing '{text}' from user {user_id}")
        
        # Process command
        response = process_command(text, user_id, chat_id)
        
        if response:
            success = send_telegram_message(chat_id, response)
            return jsonify({"status": "sent" if success else "send_failed"}), 200
        
        return jsonify({"status": "no_response"}), 200
        
    except Exception as e:
        logger.error(f"[WEBHOOK] Error: {e}")
        return jsonify({"status": "error"}), 200

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "online",
        "bot": "Mork F.E.T.C.H Bot",
        "mode": "webhook",
        "version": "1.0"
    })

@app.route('/health')
def health():
    """Health check for monitoring"""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    logger.info("🚀 Starting Mork F.E.T.C.H Bot webhook server...")
    app.run(host='0.0.0.0', port=5000, debug=False)