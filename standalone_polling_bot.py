#!/usr/bin/env python3
"""
Standalone Mork F.E.T.C.H Polling Bot
No Flask dependencies - pure Telegram API polling
"""

import os
import logging
import requests
import json
import fcntl
import time
import traceback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StandaloneMorkBot:
    def __init__(self):
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        
        self.admin_id = os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.offset = 0
        self.running = False
        
    def get_updates(self):
        """Get updates from Telegram API"""
        try:
            url = f"{self.base_url}/getUpdates"
            response = requests.get(
                url,
                params={"timeout": 25, "offset": self.offset},
                timeout=30
            )
            
            if response.status_code == 409:
                logger.error("[poll] 409 Conflict from Telegram: webhook set or another poller is consuming updates.")
                logger.error("[poll] run: curl -s -X POST \"https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook\"")
                self.running = False
                return {"ok": False}
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get updates: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return None
    
    def send_message(self, chat_id, text):
        """Send message to Telegram"""
        try:
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Message sent successfully to chat {chat_id}")
                return True
            else:
                logger.error(f"Failed to send message: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Exception sending message: {e}")
            return False
    
    def process_command(self, text, user_id, chat_id):
        """Process commands without Flask dependencies"""
        # Basic admin check
        if self.admin_id and str(user_id) != str(self.admin_id):
            return "⛔ Admin only"
        
        cmd = text.lower().strip()
        
        if cmd in ['/ping', '/help']:
            return "🤖 Mork F.E.T.C.H Bot is online!\n\nPolling mode active ✅"
        elif cmd == '/status':
            return f"📊 **Bot Status**\n\n• Mode: Polling\n• Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n• Admin ID: {self.admin_id}"
        elif cmd == '/health':
            return f"💚 **Health Check**\n\n• Polling: Healthy\n• PID: {os.getpid()}\n• Uptime: Active"
        else:
            return f"❓ Unknown command: `{cmd}`\n\nTry /ping or /help"
    
    def process_update(self, update):
        """Process a single update"""
        try:
            logger.info(f"[poll] Processing update: {update.get('update_id')}")
            
            if 'message' not in update:
                return
                
            message = update['message']
            text = message.get('text', '')
            user_id = message.get('from', {}).get('id', '')
            chat_id = message.get('chat', {}).get('id', '')
            
            if not text.startswith('/'):
                return
                
            logger.info(f"Processing command '{text}' from user {user_id}")
            
            response_text = self.process_command(text, user_id, chat_id)
            
            # Send response
            if response_text and chat_id:
                success = self.send_message(chat_id, response_text)
                logger.info(f"Response sent: {success}")
                
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            traceback.print_exc()
    
    def run(self):
        """Start polling loop"""
        try:
            # Single-instance lock
            self._lock_fd = open("/tmp/mork_polling.lock", "w")
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._lock_fd.write(str(os.getpid()))
                self._lock_fd.flush()
                logger.info("[poll] lock acquired /tmp/mork_polling.lock")
            except BlockingIOError:
                logger.error("[poll] another polling instance is already running; exiting")
                return

            self.running = True
            logger.info("🤖 Mork F.E.T.C.H Bot starting in polling mode...")
            
            # Get bot info
            try:
                response = requests.get(f"{self.base_url}/getMe", timeout=10)
                if response.status_code == 200:
                    bot_info = response.json()
                    username = bot_info.get('result', {}).get('username', 'Unknown')
                    logger.info(f"Bot ready: @{username}")
                else:
                    logger.error("Failed to get bot info")
                    return
            except Exception as e:
                logger.error(f"Bot info check failed: {e}")
                return
            
            logger.info(f"[poll] startup OK offset={self.offset}")
            
            # Main polling loop
            while self.running:
                try:
                    result = self.get_updates()
                    
                    if result is None:
                        time.sleep(1)
                        continue
                    
                    if not result.get("ok"):
                        logger.error("Failed to get updates, stopping")
                        break
                    
                    updates = result.get("result", [])
                    
                    if updates:
                        logger.info(f"[poll] received {len(updates)} updates")
                        
                        for update in updates:
                            self.process_update(update)
                            self.offset = update["update_id"] + 1
                    else:
                        logger.debug("[poll] no new updates")
                        
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    break
                except Exception as e:
                    logger.error(f"Polling loop error: {e}")
                    time.sleep(5)  # Brief pause before retrying
                    
        except Exception as e:
            logger.error(f"Critical error in polling bot: {e}")
            
        finally:
            self.running = False
            if hasattr(self, '_lock_fd'):
                try:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                    self._lock_fd.close()
                    os.unlink("/tmp/mork_polling.lock")
                except:
                    pass
            logger.info("Bot stopped")

if __name__ == "__main__":
    bot = StandaloneMorkBot()
    bot.run()