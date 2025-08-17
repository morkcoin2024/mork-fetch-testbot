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
        """Get updates from Telegram API"""
        try:
            url = f"{self.base_url}/getUpdates"
            response = requests.get(
                url,
                params={"timeout": 25, "offset": self.offset},
                timeout=15
            )
            
            if response.status_code == 409:
                logger.error("[poll] 409 Conflict from Telegram: webhook set or another poller is consuming updates.")
                logger.error("[poll] run: curl -s -X POST \"https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook\"")
                self.running = False
                return {"ok": False}
            
            response_preview = response.text[:200] if response.text else "empty"
            logger.debug(f"[poll] GET {url} -> {response.status_code} {response_preview}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get updates: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return None
    
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
            return True

        # Attempt 2: if MarkdownV2 parsing failed, escape and retry
        if _is_mdv2_parse_error(r):
            safe_text = _escape_markdown_v2(text)
            payload["text"] = safe_text
            r2 = requests.post(url, json=payload, timeout=15)
            if r2.status_code == 200 and r2.json().get("ok") is True:
                return True
            logger.error(f"MarkdownV2 escaped send failed: {r2.status_code} - {r2.text}")

        # Attempt 3: plain text fallback (no parse_mode)
        payload.pop("parse_mode", None)
        payload["text"] = text
        r3 = requests.post(url, json=payload, timeout=15)
        if r3.status_code == 200 and r3.json().get("ok") is True:
            return True

        logger.error(f"Failed to send message (all attempts): "
                     f"r1={r.status_code} r2={'N/A' if not _is_mdv2_parse_error(r) else r2.status_code} "
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
                        print("[poll] got", len(updates), "updates; last_update_id=", updates[-1]['update_id'] if updates else None)
                        
                        for update in updates:
                            try:
                                self.process_update(update)
                                # Update offset to mark message as processed
                                self.offset = update['update_id'] + 1
                            except Exception as e:
                                logger.error(f"Error processing individual update: {e}")
                                # Still update offset to avoid getting stuck
                                self.offset = update['update_id'] + 1
                    
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
    main()