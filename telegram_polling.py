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
from telegram_safety import send_telegram_safe

# Import webhook processing function - delay import to avoid circular imports

logger = logging.getLogger(__name__)

# Bridge function to redirect legacy send_message calls to centralized system
def send_message(chat_id: int, text: str):
    """Bridge function: redirects to centralized send_telegram_safe()"""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    ok, status, _ = send_telegram_safe(bot_token, chat_id, text)
    if not ok:
        logger.warning("send_message_failed", extra={"status": status})
    return ok

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
        """Enhanced update handler with single-send guarantee"""
        chat_id = (update.get("message", {}).get("chat") or {}).get("id")
        if chat_id is None:
            return

        # Idempotency check
        upd_id = update.get("update_id")
        msg_id = update.get("message", {}).get("message_id")
        dedupe_key = f"{upd_id}:{msg_id}:{chat_id}"
        if _seen(dedupe_key):
            logger.debug(f"Duplicate update ignored: {dedupe_key}")
            return

        # Process command through main router
        from app import process_telegram_command
        result = process_telegram_command(update)

        # Single-send guarantee
        text_out = None
        if isinstance(result, dict) and result.get("handled"):
            text_out = result.get("response")
        elif isinstance(result, str):
            text_out = result
        else:
            text_out = "⚠️ Processing error occurred."

        ok, status, js = send_telegram_safe(self.bot_token, chat_id, text_out)
        # Do NOT also send any additional fallback here.

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