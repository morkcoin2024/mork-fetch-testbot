#!/usr/bin/env python3
"""Simple polling bot to replace broken webhook - Mork F.E.T.C.H Bot"""

import os
import sys
import time
import logging
import fcntl
import requests
import traceback
# Import moved to process_update to avoid initialization blocking
# from app import process_telegram_command

# Setup logging
import os
log_level = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def _escape_markdown_v2(text: str) -> str:
    """
    Escape Telegram MarkdownV2 special characters.
    Docs: _,*,[,],(,),~,`,>,#, +,-,=,|,{,},.,!
    Also escape backslash FIRST.
    """
    if text is None:
        return ""
    text = text.replace("\\", "\\\\")
    for ch in "_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text

def _is_mdv2_parse_error(resp) -> bool:
    try:
        if resp.status_code != 400:
            return False
        j = resp.json()
        desc = (j.get("description") or "").lower()
        return "can't parse entities" in desc
    except Exception:
        return False

class SimplePollingBot:
    def __init__(self):
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.offset = 0
        self.running = False
        
    def get_updates(self):
        """Get updates from Telegram API with resilient timeouts and clear logs."""
        import time
        try:
            params = {
                "timeout": 8,                 # Telegram long-poll window (seconds)
                "offset": self.offset,
                "allowed_updates": ["message"]  # only what we handle
            }
            url = f"{self.base_url}/getUpdates"
            r = requests.get(url, params=params, timeout=(5, 10))  # (connect, read)
            if r.status_code == 200:
                data = r.json()
                res = data.get("result", [])
                logger.info(f"[poll] got {len(res)} updates; last_offset={self.offset}")
                return data
            if r.status_code == 409:
                logger.error("[poll] 409 Conflict (webhook or another poller). Stopping.")
                self.running = False
                return {"ok": False}
            logger.warning(f"[poll] getUpdates unexpected status={r.status_code} body={r.text[:160]}")
            time.sleep(1)
            return {"ok": False}
        except requests.Timeout:
            logger.warning("[poll] getUpdates timeout; retrying soon")
            return {"ok": False}
        except Exception as e:
            logger.error(f"[poll] getUpdates error: {e}")
            time.sleep(1)
            return {"ok": False}
    
    def send_message(self, chat_id, text):
        url = f"{self.base_url}/sendMessage"
        # Attempt 1: as-is (keep any intentional formatting)
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200 and r.json().get("ok") is True:
            logger.info("Delivered message_id=%s to chat_id=%s",
                        r.json().get("result", {}).get("message_id"), chat_id)
            return True

        # Attempt 2: if MarkdownV2 parsing failed, escape and retry
        r2_status = "N/A"
        if _is_mdv2_parse_error(r):
            safe_text = _escape_markdown_v2(text)
            payload["text"] = safe_text
            r2 = requests.post(url, json=payload, timeout=15)
            r2_status = r2.status_code
            if r2.status_code == 200 and r2.json().get("ok") is True:
                logger.info("Delivered message_id=%s to chat_id=%s",
                            r2.json().get("result", {}).get("message_id"), chat_id)
                return True
            logger.error(f"MarkdownV2 escaped send failed: {r2.status_code} - {r2.text}")

        # Attempt 3: plain text fallback (no parse_mode)
        payload.pop("parse_mode", None)
        payload["text"] = text
        r3 = requests.post(url, json=payload, timeout=15)
        if r3.status_code == 200 and r3.json().get("ok") is True:
            logger.info("Delivered message_id=%s to chat_id=%s",
                        r3.json().get("result", {}).get("message_id"), chat_id)
            return True

        logger.error(f"Failed to send message (all attempts): "
                     f"r1={r.status_code} r2={r2_status} "
                     f"r3={r3.status_code} body3={r3.text}")
        return False
    
    def process_update(self, update):
        """Process a single update"""
        try:
            import json
            print("[poll] raw update:", json.dumps(update)[:800])
            
            if 'message' not in update:
                return
                
            message = update['message']
            text = message.get('text', '')
            user_id = message.get('from', {}).get('id', '')
            chat_id = message.get('chat', {}).get('id', '')
            
            if not text.startswith('/'):
                return
                
            print("[poll] text repr:", repr(text), "chat_id=", chat_id, "user_id=", user_id)
            logger.info(f"Processing command '{text}' from user {user_id}")
            
            # Use the existing command processor (lazy import to avoid init blocking)
            from app import process_telegram_command
            result = process_telegram_command(update)
            
            # Extract response
            if isinstance(result, dict) and result.get("handled"):
                response_text = result.get("response", "Command processed")
            elif isinstance(result, str):
                response_text = result
            else:
                response_text = "⚠️ Command processing error"
            
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
            # Single-instance lock (Linux)
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
                    bot_info = response.json().get('result', {})
                    logger.info(f"Bot ready: @{bot_info.get('username', 'unknown')}")
                else:
                    logger.error("Failed to get bot info")
                    return
            except Exception as e:
                logger.error(f"Failed to connect to Telegram API: {e}")
                return
            
            logger.info(f"[poll] startup OK offset={self.offset}")
            
            while self.running:
                try:
                    updates_data = self.get_updates()
                    
                    if updates_data and updates_data.get('ok'):
                        updates = updates_data.get('result', [])
                        if isinstance(updates, list):
                            print("[poll] got", len(updates), "updates; last_update_id=", updates[-1]['update_id'] if updates else None)
                        else:
                            updates = []
                            print("[poll] got 0 updates; invalid result format")
                        
                        for update in updates:
                            try:
                                self.process_update(update)
                                # Update offset to mark message as processed
                                self.offset = update['update_id'] + 1
                            except Exception as e:
                                logger.error(f"Error processing individual update: {e}")
                                # Still update offset to avoid getting stuck
                                self.offset = update['update_id'] + 1
                        
                        # after processing updates list:
                        if not updates:
                            logger.info("[poll] heartbeat offset=%s (no updates)", self.offset)
                    
                    else:
                        time.sleep(1)  # Brief pause if no updates
                        
                except KeyboardInterrupt:
                    logger.info("Bot stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Polling error: {e}")
                    time.sleep(5)  # Wait before retrying
            
        except Exception as e:
            logger.error(f"Failed to initialize polling bot: {e}")
            return
        
        self.running = False
        logger.info("Bot stopped")

def main():
    try:
        bot = SimplePollingBot()
        bot.run()
    except Exception as e:
        import traceback
        logger.error(f"Failed to start bot: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    import time, traceback, os
    print("[POLL] boot pid=", os.getpid())
    while True:
        try:
            bot = SimplePollingBot()
            bot.run()  # returns when self.running becomes False or an error happens
        except Exception as e:
            logger.exception("[poll] FATAL: unhandled exception; will restart")
        # brief pause to avoid hot-looping on persistent errors
        time.sleep(2)