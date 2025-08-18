#!/usr/bin/env python3
"""
PRODUCTION POLLING BOT - Standalone deployment version
Clean, conflict-free polling bot for Replit deployment
"""
import os
import sys
import time
import json
import logging
import requests
import threading
from datetime import datetime

# Ensure we're in the right directory
sys.path.insert(0, '/home/runner/workspace')

# Setup logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [PRODUCTION-BOT] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('live_bot.log')
    ]
)
logger = logging.getLogger(__name__)

class ProductionPollingBot:
    def __init__(self):
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not found")
            sys.exit(1)
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.running = True
        self.offset = 0
        
        # Import command processor
        try:
            from app import process_telegram_command, _require_admin
            self.process_command = process_telegram_command
            self.require_admin = _require_admin
            logger.info("✅ Command processor imported successfully")
        except Exception as e:
            logger.error(f"Failed to import command processor: {e}")
            self.process_command = None
            self.require_admin = None
        
        logger.info("🤖 Production Polling Bot initialized")
    
    def send_telegram_message(self, chat_id, text):
        """Send message via Telegram API with production error handling"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": chat_id, "text": text}
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.ok:
                result = response.json().get('result', {})
                msg_id = result.get('message_id')
                logger.info(f"✅ Sent message {msg_id} to chat {chat_id}")
                return True
            else:
                logger.error(f"❌ Send failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Send error: {e}")
            return False
    
    def process_update(self, update):
        """Process incoming update with production-grade error handling"""
        try:
            message = update.get('message')
            if not message:
                return
            
            # Extract message details
            text = message.get('text', '').strip()
            user = message.get('from', {})
            chat = message.get('chat', {})
            
            user_id = user.get('id')
            chat_id = chat.get('id')
            username = user.get('username', 'Unknown')
            
            if not text.startswith('/'):
                return
            
            logger.info(f"📨 Processing: '{text}' from {username} ({user_id})")
            
            # Use imported command processor if available
            if self.process_command:
                try:
                    result = self.process_command(text, user, {})
                    if result and isinstance(result, dict):
                        response_text = result.get('text', 'Command processed')
                        self.send_telegram_message(chat_id, response_text)
                        logger.info(f"✅ Processed via app.py: {text}")
                        return
                except Exception as e:
                    logger.warning(f"App processor failed: {e}, using fallback")
            
            # Fallback command handling
            if text.startswith('/ping'):
                self.send_telegram_message(chat_id, "🤖 Mork F.E.T.C.H Bot\n✅ ONLINE via production polling\n🔥 Ready to fetch!")
                logger.info("✅ Responded to /ping")
            elif text.startswith('/status'):
                self.send_telegram_message(chat_id, f"✅ Bot Status: OPERATIONAL\n⚡ Mode: Production Polling\n🕐 Time: {datetime.now().strftime('%H:%M:%S')}")
                logger.info("✅ Responded to /status")
            elif text.startswith('/help'):
                self.send_telegram_message(chat_id, "🐕 Mork F.E.T.C.H Bot - The Degens' Best Friend\n\n/ping - Test connectivity\n/status - System status\n/help - Show commands\n/wallet - Wallet management\n\n🚀 Production deployment active!")
                logger.info("✅ Responded to /help")
            elif text.startswith('/'):
                self.send_telegram_message(chat_id, f"Command '{text}' not recognized. Use /help for available commands.")
                logger.info(f"❓ Unknown command: {text}")
                
        except Exception as e:
            logger.error(f"❌ Update processing error: {e}")
    
    def poll_updates(self):
        """Poll for new updates with production-grade error handling"""
        try:
            url = f"{self.api_url}/getUpdates"
            params = {
                "offset": self.offset,
                "limit": 10,
                "timeout": 25
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if not response.ok:
                if response.status_code == 409:
                    logger.warning("⚠️ Conflict detected - another bot instance may be running")
                    time.sleep(10)
                else:
                    logger.error(f"❌ Poll failed: {response.status_code}")
                return
            
            data = response.json()
            if not data.get('ok'):
                logger.error(f"❌ API error: {data}")
                return
            
            updates = data.get('result', [])
            
            if updates:
                logger.info(f"📥 Received {len(updates)} updates")
                
                for update in updates:
                    self.offset = max(self.offset, update.get('update_id', 0) + 1)
                    self.process_update(update)
            else:
                logger.debug("⏱️ No new updates")
            
        except requests.exceptions.Timeout:
            logger.debug("⏱️ Poll timeout (normal)")
        except Exception as e:
            logger.error(f"❌ Poll error: {e}")
            time.sleep(5)
    
    def clear_webhook(self):
        """Clear any existing webhook to prevent conflicts"""
        try:
            response = requests.post(f"{self.api_url}/deleteWebhook", timeout=10)
            if response.ok:
                logger.info("🧹 Webhook cleared - polling mode active")
            else:
                logger.warning("⚠️ Failed to clear webhook")
        except Exception as e:
            logger.warning(f"⚠️ Webhook clear error: {e}")
    
    def run(self):
        """Main bot loop with auto-restart capability"""
        logger.info("🚀 Starting Production Polling Bot")
        
        # Clear webhook first
        self.clear_webhook()
        
        # Main polling loop with auto-restart
        restart_count = 0
        while True:
            try:
                self.running = True
                logger.info(f"🔄 Bot loop started (restart #{restart_count})")
                
                while self.running:
                    self.poll_updates()
                    
            except KeyboardInterrupt:
                logger.info("🛑 Bot stopped by user")
                break
            except Exception as e:
                restart_count += 1
                logger.error(f"💥 Unexpected error #{restart_count}: {e}")
                logger.info("🔄 Auto-restarting in 5 seconds...")
                time.sleep(5)

def main():
    """Main entry point with production error handling"""
    try:
        bot = ProductionPollingBot()
        bot.run()
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()