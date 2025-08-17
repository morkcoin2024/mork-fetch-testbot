#!/usr/bin/env python3
"""
WORKING POLLING BOT - Uses existing app infrastructure
"""
import os
import sys
import time
import json
import logging
import requests
import threading
from datetime import datetime

# Import the working command processor from app.py
sys.path.insert(0, '/home/runner/workspace')
from app import process_telegram_command

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [POLLING] %(message)s'
)
logger = logging.getLogger(__name__)

class WorkingPollingBot:
    def __init__(self):
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not found")
            sys.exit(1)
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.running = True
        self.offset = 0
        self.processed_msgs = set()
        
        logger.info("Working Polling Bot initialized")
    
    def send_telegram_message(self, chat_id, text):
        """Send message via Telegram API"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": chat_id, "text": text}
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.ok:
                result = response.json().get('result', {})
                msg_id = result.get('message_id')
                logger.info(f"✅ Message sent: id={msg_id} to chat={chat_id}")
                return True
            else:
                logger.error(f"Send failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False
    
    def process_update(self, update):
        """Process incoming update using existing app logic"""
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
            
            if not text or not chat_id:
                return
            
            # Deduplication
            msg_key = f"{user_id}_{text[:30]}_{message.get('date', 0)}"
            if msg_key in self.processed_msgs:
                return
            
            self.processed_msgs.add(msg_key)
            
            # Keep memory manageable
            if len(self.processed_msgs) > 500:
                self.processed_msgs = set(list(self.processed_msgs)[-250:])
            
            logger.info(f"📨 Processing: '{text}' from {username} ({user_id})")
            
            # Use the existing command processor from app.py
            try:
                result = process_telegram_command(update)
                
                if result:
                    if isinstance(result, dict):
                        response_text = result.get('result', str(result))
                    else:
                        response_text = str(result)
                    
                    self.send_telegram_message(chat_id, response_text)
                    logger.info(f"✅ Processed command: {text}")
                else:
                    # Fallback simple responses
                    if text.startswith('/ping'):
                        self.send_telegram_message(chat_id, "🤖 Mork F.E.T.C.H Bot\n✅ ONLINE via polling\n🔥 Ready to fetch!")
                    elif text.startswith('/status'):
                        self.send_telegram_message(chat_id, f"✅ Bot Status: OPERATIONAL\n⚡ Mode: Working Polling\n🕐 Time: {datetime.now().strftime('%H:%M:%S')}")
                    elif text.startswith('/help'):
                        self.send_telegram_message(chat_id, "🐕 Mork F.E.T.C.H Bot\n\n/ping - Test bot\n/status - System status\n/help - Show commands\n\nBot is fully operational!")
                    elif text.startswith('/'):
                        self.send_telegram_message(chat_id, f"Command '{text}' not recognized. Use /help for available commands.")
                
            except Exception as e:
                logger.error(f"Command processing error: {e}")
                self.send_telegram_message(chat_id, "⚠️ Command processing error. Bot is still operational.")
                
        except Exception as e:
            logger.error(f"Update processing error: {e}")
    
    def poll_updates(self):
        """Poll for new updates"""
        try:
            url = f"{self.api_url}/getUpdates"
            params = {
                "offset": self.offset,
                "limit": 10,
                "timeout": 25
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if not response.ok:
                logger.error(f"Poll failed: {response.status_code}")
                return
            
            data = response.json()
            if not data.get('ok'):
                logger.error(f"API error: {data}")
                return
            
            updates = data.get('result', [])
            
            if updates:
                logger.info(f"📥 Received {len(updates)} updates")
                
                for update in updates:
                    self.offset = max(self.offset, update.get('update_id', 0) + 1)
                    self.process_update(update)
            
        except requests.exceptions.Timeout:
            logger.debug("Poll timeout (normal)")
        except Exception as e:
            logger.error(f"Poll error: {e}")
            time.sleep(5)
    
    def run(self):
        """Main bot loop"""
        logger.info("🚀 Starting Working Polling Bot")
        
        # Delete webhook first
        try:
            requests.post(f"{self.api_url}/deleteWebhook", timeout=10)
            logger.info("Webhook deleted - polling mode active")
        except:
            pass
        
        # Main polling loop
        while self.running:
            try:
                self.poll_updates()
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(10)

def main():
    bot = WorkingPollingBot()
    bot.run()

if __name__ == "__main__":
    main()