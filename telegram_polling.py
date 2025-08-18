"""
Telegram Polling Service - Integrated with Flask App
Runs as a background thread within the Flask process
"""
import os
import sys
import time
import json
import requests
import threading
import logging
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)

# Import unified sender from app
try:
    from app import tg_send
except ImportError:
    tg_send = None

class TelegramPollingService:
    def __init__(self, bot_token: str, message_handler=None):
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.message_handler = message_handler
        self.running = False
        self.polling_thread = None
        self.offset = 0
        
    def send_message(self, chat_id: int, text: str, parse_mode: Optional[str] = None) -> bool:
        """Send message using unified tg_send with enhanced logging"""
        ln = len(text or "")
        preview = (text or "")[:120].replace("\n"," ")
        logger.info("[SEND] chat=%s len=%s preview=%r", chat_id, ln, preview)
        
        if tg_send:
            res = tg_send(chat_id, text, preview=True)
            ok = bool(res.get("ok"))
            logger.info("[SEND] result=%s json=%s", ok, json.dumps(res)[:300])
            return ok
        else:
            # Fallback to direct API call
            try:
                url = f"{self.api_url}/sendMessage"
                data = {"chat_id": chat_id, "text": text}
                if parse_mode:
                    data["parse_mode"] = parse_mode
                response = requests.post(url, json=data, timeout=10)
                ok = response.ok
                logger.info("[SEND] result=%s fallback", ok)
                return ok
            except Exception as e:
                logger.error(f"❌ Send error: {e}")
                return False
    
    def process_update(self, update: dict):
        """Process a single Telegram update"""
        try:
            message = update.get('message') or update.get('edited_message')
            if not message:
                return
                
            text = message.get('text', '').strip()
            chat_id = message.get('chat', {}).get('id')
            user_info = message.get('from', {})
            user_id = user_info.get('id')
            username = user_info.get('username', 'Unknown')
            
            if not text or not chat_id:
                return
            
            logger.info(f"📨 Processing message from @{username} ({user_id}): '{text}'")
            
            # Admin check
            ADMIN_ID = int(os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID', '1653046781'))
            is_admin = user_id == ADMIN_ID
            
            # Basic command processing
            if text.startswith('/ping'):
                response = "🤖 **Mork F.E.T.C.H Bot**\n✅ Integrated polling active\n🔥 Bot responding from Flask app!"
                self.send_message(chat_id, response, "Markdown")
                
            elif text.startswith('/status'):
                uptime = time.strftime('%H:%M:%S UTC', time.gmtime())
                response = f"✅ **Bot Status: OPERATIONAL**\n⚡ Mode: Integrated Polling\n🕐 Time: {uptime}\n\n{'🔐 Admin access' if is_admin else '👤 User access'}"
                self.send_message(chat_id, response, "Markdown")
                
            elif text.startswith('/help'):
                response = "🐕 **Mork F.E.T.C.H Bot Help**\n\n📋 **Available Commands:**\n• `/ping` - Test connection\n• `/status` - System status\n• `/help` - Show help\n\n🔥 Ready for trading!"
                self.send_message(chat_id, response, "Markdown")
                
            elif text.startswith('/test') and is_admin:
                response = "🧪 **Test Mode**\nIntegrated polling working!\nFlask app managing Telegram polling."
                self.send_message(chat_id, response)
                
            elif text.startswith('/'):
                # Use custom handler if available
                if self.message_handler:
                    try:
                        result = self.message_handler(update)
                        if result and isinstance(result, str):
                            self.send_message(chat_id, result)
                    except Exception as e:
                        logger.error(f"Message handler error: {e}")
                        cmd = text.split()[0]
                        self.send_message(chat_id, f"Command `{cmd}` encountered an error.")
                else:
                    cmd = text.split()[0]
                    self.send_message(chat_id, f"Command `{cmd}` not recognized. Use /help for available commands.")
                    
        except Exception as e:
            logger.error(f"Error processing update: {e}")
    
    def clear_pending_updates(self):
        """Clear any pending Telegram updates"""
        try:
            logger.info("Clearing pending updates...")
            response = requests.get(f"{self.api_url}/getUpdates", timeout=10)
            if response.ok:
                updates = response.json().get('result', [])
                if updates:
                    last_update_id = max(update.get('update_id', 0) for update in updates)
                    requests.get(f"{self.api_url}/getUpdates", 
                               params={'offset': last_update_id + 1}, timeout=10)
                    logger.info(f"Cleared {len(updates)} pending updates")
                else:
                    logger.info("No pending updates")
            else:
                logger.error(f"Failed to get updates: {response.status_code}")
        except Exception as e:
            logger.error(f"Error clearing updates: {e}")
    
    def polling_loop(self):
        """Main polling loop running in background thread"""
        logger.info("🚀 Starting integrated Telegram polling")
        
        # Delete webhook first
        try:
            requests.post(f"{self.api_url}/deleteWebhook", timeout=10)
            logger.info("Webhook deleted - polling mode active")
        except Exception as e:
            logger.error(f"Webhook delete error: {e}")
        
        # Clear pending updates
        self.clear_pending_updates()
        
        consecutive_errors = 0
        
        while self.running:
            try:
                params = {
                    'offset': self.offset,
                    'limit': 10,
                    'timeout': 25
                }
                
                response = requests.get(f"{self.api_url}/getUpdates", params=params, timeout=30)
                
                if not response.ok:
                    consecutive_errors += 1
                    logger.error(f"❌ Poll failed: {response.status_code} (error #{consecutive_errors})")
                    if consecutive_errors > 5:
                        time.sleep(30)
                    else:
                        time.sleep(5)
                    continue
                
                consecutive_errors = 0
                data = response.json()
                
                if not data.get('ok'):
                    logger.error(f"API error response: {data}")
                    time.sleep(5)
                    continue
                
                updates = data.get('result', [])
                
                if updates:
                    logger.info(f"📥 Processing {len(updates)} updates")
                    
                    for update in updates:
                        update_id = update.get('update_id', 0)
                        self.offset = max(self.offset, update_id + 1)
                        self.process_update(update)
                        
                logger.debug(f"Polling cycle complete, offset: {self.offset}")
                
            except requests.exceptions.Timeout:
                logger.debug("Poll timeout - continuing...")
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"❌ Unexpected polling error: {e} (error #{consecutive_errors})")
                time.sleep(10 if consecutive_errors < 3 else 30)
        
        logger.info("Polling loop stopped")
    
    def start_polling(self):
        """Start polling in background thread"""
        if self.running:
            logger.warning("Polling already running")
            return False
            
        self.running = True
        self.polling_thread = threading.Thread(target=self.polling_loop, daemon=True)
        self.polling_thread.start()
        logger.info("Polling service started")
        return True
    
    def stop_polling(self):
        """Stop polling"""
        if not self.running:
            return
            
        self.running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        logger.info("Polling service stopped")

# Global service instance
_polling_service: Optional[TelegramPollingService] = None

def start_polling_service(message_handler=None) -> bool:
    """Start the global polling service"""
    global _polling_service
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found")
        return False
    
    if _polling_service and _polling_service.running:
        logger.warning("Polling service already running")
        return True
    
    _polling_service = TelegramPollingService(bot_token, message_handler)
    return _polling_service.start_polling()

def stop_polling_service():
    """Stop the global polling service"""
    global _polling_service
    if _polling_service:
        _polling_service.stop_polling()
        _polling_service = None

def get_polling_service() -> Optional[TelegramPollingService]:
    """Get the global polling service instance"""
    return _polling_service