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
                        self._handle_update(update)
                            
                time.sleep(1)  # Brief pause between polls
                
            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(5)
                
    def _handle_update(self, update: dict):
        """Unified update handler with idempotency and single send guarantee"""
        try:
            upd_id = update.get("update_id")
            msg = update.get("message") or update.get("edited_message") or {}
            msg_id = msg.get("message_id")
            chat_id = (msg.get("chat") or {}).get("id")

            dedupe_key = f"{upd_id}:{msg_id}:{chat_id}"
            if _seen(dedupe_key):
                logger.debug(f"Duplicate update ignored: {dedupe_key}")
                # Prevent double send
                return

            # Skip updates without message content
            if not msg or not chat_id:
                return

            # Import at runtime to avoid circular import
            from app import process_telegram_command
            result = process_telegram_command(update)

            # Unified send logic
            text = None
            if isinstance(result, dict) and "response" in result:
                text = result["response"]
            elif isinstance(result, str):
                text = result
            else:
                text = "⚠️ No response generated."

            if text:
                self._send_response(chat_id, text)

        except Exception as e:
            logger.error(f"Update handling error: {e}")
            # Final fallback if we have chat_id
            if "chat_id" in locals() and chat_id:
                self._send_fallback_response(chat_id, "❌ Processing error occurred")
    
    def _send_response(self, chat_id: str, text: str):
        """Send response via Telegram API with proper formatting"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Enhanced Markdown detection to prevent parsing errors
        def should_use_markdown(text: str) -> bool:
            """Intelligent Markdown detection with validation"""
            markdown_indicators = ['*', '_', '`', '[', ']', '**', '__']
            
            # Check for Markdown characters
            if not any(indicator in text for indicator in markdown_indicators):
                return False
            
            # Additional validation for common patterns that cause issues
            # Ensure balanced formatting (basic check)
            star_count = text.count('*')
            underscore_count = text.count('_')
            bracket_open = text.count('[')
            bracket_close = text.count(']')
            
            # If unbalanced formatting detected, use plain text for safety
            if (star_count % 2 != 0) or (underscore_count % 2 != 0) or (bracket_open != bracket_close):
                logger.debug("Unbalanced Markdown detected, using plain text")
                return False
                
            return True
        
        has_markdown = should_use_markdown(text)
        
        data = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        }
        
        # Only use Markdown if text appears to have formatting
        if has_markdown:
            data["parse_mode"] = "Markdown"
        
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"Response sent successfully to chat {chat_id}")
            else:
                logger.error(f"Response failed: {response.status_code} - {response.text}")
                # Retry without Markdown formatting on error
                if "parse_mode" in data:
                    del data["parse_mode"]
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