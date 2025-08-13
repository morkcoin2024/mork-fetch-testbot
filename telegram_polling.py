#!/usr/bin/env python3
"""
Production Telegram polling service integrated with main app
"""
import os
import time
import requests
import logging
import threading
import json
from typing import Optional, Dict, Any
from collections import deque

# Import webhook processing function - delay import to avoid circular imports

logger = logging.getLogger(__name__)

# Idempotency: de-dupe by update_id / message_id (pre-send)
_PROCESSED = deque(maxlen=1000)   # recent keys
_PROCESSED_SET = set()

def _seen(key: str, ttl_sec=120) -> bool:
    """Simple rolling memory; swap to time-based if needed"""
    if key in _PROCESSED_SET:
        return True
    _PROCESSED.append((time.time(), key))
    _PROCESSED_SET.add(key)
    # Periodic cleanup (optional)
    if len(_PROCESSED) >= 990:
        cutoff = time.time() - ttl_sec
        while _PROCESSED and _PROCESSED[0][0] < cutoff:
            _, old = _PROCESSED.popleft()
            _PROCESSED_SET.discard(old)
    return False

def disable_webhook_if_polling(bot_token: str):
    """Kill webhook when starting polling to prevent duplicate processing"""
    try:
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/deleteWebhook", timeout=5)
        if response.json().get('ok'):
            logger.info("[startup] Deleted Telegram webhook (polling mode).")
        else:
            logger.warning(f"[startup] Webhook delete failed: {response.json()}")
    except Exception as e:
        logger.warning(f"[startup] Warning: failed to delete webhook: {e}")

class TelegramPolling:
    def __init__(self):
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.admin_id = os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID')
        self.running = False
        self.offset = None
        self.thread = None
        
    def start(self):
        """Start polling in background thread"""
        if self.running:
            logger.warning("Polling already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info("Telegram polling started")
        
    def stop(self):
        """Stop polling"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Telegram polling stopped")
        
    def get_updates(self) -> Optional[Dict[str, Any]]:
        """Get updates from Telegram"""
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {"timeout": 10}
        if self.offset:
            params["offset"] = self.offset
            
        try:
            response = requests.get(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return None
            
    def _poll_loop(self):
        """Main polling loop"""
        logger.info("Starting polling loop")
        
        while self.running:
            try:
                result = self.get_updates()
                if not result or not result.get("ok"):
                    if result:
                        logger.warning(f"Bad response: {result}")
                    time.sleep(5)
                    continue
                    
                updates = result.get("result", [])
                if updates:
                    logger.info(f"Processing {len(updates)} updates")
                    
                    for update in updates:
                        self.offset = update["update_id"] + 1
                        
                        if "message" in update:
                            # Idempotency check using update_id + message_id
                            update_id = update.get("update_id", 0)
                            message_id = update["message"].get("message_id", 0)
                            dedup_key = f"{update_id}:{message_id}"
                            
                            if _seen(dedup_key):
                                logger.debug(f"Duplicate update ignored: {dedup_key}")
                                continue
                                
                            self._process_message(update["message"])
                            
                time.sleep(1)  # Brief pause between polls
                
            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(5)
                
    def _process_message(self, message: Dict[str, Any]):
        """Process incoming message using main app logic"""
        try:
            text = message.get("text", "")
            user_id = message.get("from", {}).get("id", "")
            chat_id = message.get("chat", {}).get("id", "")
            
            logger.info(f"Processing message: '{text}' from user {user_id}")
            
            # Create update structure matching webhook format
            update_data = {
                "update_id": int(time.time()),
                "message": message
            }
            
            # Import at runtime to avoid circular import
            try:
                from app import process_telegram_command
                response = process_telegram_command(update_data)
                logger.info(f"Command processed: {response}")
                
                # Handle new dict-based response format
                if isinstance(response, dict) and "response" in response:
                    self._send_response(chat_id, response["response"])
                elif isinstance(response, str):
                    # Legacy string response support
                    self._send_response(chat_id, response)
                else:
                    # Avoid silence - send fallback message
                    self._send_response(chat_id, "⚠️ No response generated.")
                    
            except Exception as import_error:
                logger.error(f"Import or processing error: {import_error}")
                # Fallback: direct Telegram API call
                self._send_fallback_response(chat_id, f"🤖 Received: {text}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _send_response(self, chat_id: str, text: str):
        """Send response via Telegram API with proper formatting"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"Response sent successfully to chat {chat_id}")
            else:
                logger.error(f"Response failed: {response.status_code} - {response.text}")
                # Retry without Markdown formatting on error
                data["parse_mode"] = None
                fallback_response = requests.post(url, json=data, timeout=10)
                logger.info(f"Fallback response: {fallback_response.status_code}")
        except Exception as e:
            logger.error(f"Response send failed: {e}")
    
    def _send_fallback_response(self, chat_id: str, text: str):
        """Send direct response via Telegram API as fallback"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text
        }
        try:
            response = requests.post(url, json=data, timeout=10)
            logger.info(f"Fallback response sent: {response.status_code}")
        except Exception as e:
            logger.error(f"Fallback response failed: {e}")

# Global polling instance
_polling_instance = None

def start_polling():
    """Start polling service"""
    global _polling_instance
    if not _polling_instance:
        _polling_instance = TelegramPolling()
    _polling_instance.start()
    return _polling_instance
    
def stop_polling():
    """Stop polling service"""
    global _polling_instance
    if _polling_instance:
        _polling_instance.stop()

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start polling
    polling = TelegramPolling()
    polling.start()
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        polling.stop()