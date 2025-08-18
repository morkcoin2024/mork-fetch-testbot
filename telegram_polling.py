"""
Telegram Polling Service - Integrated with Flask App
Runs as a background thread within the Flask process
"""
import requests, logging, os, time, json, random, signal
import threading
from typing import Optional
try:
    import fcntl
except Exception:  # windows safety; replit is linux so fine
    fcntl = None

logger = logging.getLogger("telegram_polling")
_LAST_409_ALERT_TS = 0

# --- Rotating logs + console mirror (idempotent) ---
def _ensure_logging():
    try:
        from logging.handlers import RotatingFileHandler
        if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
            fh = RotatingFileHandler("live_bot.log", maxBytes=1_000_000, backupCount=5)
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            logger.addHandler(fh)
        if not any(h for h in logger.handlers if getattr(h, "_is_console", False)):
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            ch._is_console = True
            logger.addHandler(ch)
    except Exception as e:
        logger.error("log setup failed: %s", e)

_ensure_logging()

# Import unified sender and command processor from app
from app import process_telegram_command, tg_send

class TelegramPollingService:
    def __init__(self, token, admin_chat_id=None):
        self.token = token
        self.admin_chat_id = admin_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self._hb_last = 0
        self._lock_fd = None
        self.running = False
        self.polling_thread = None
        
    def send_message(self, chat_id, text):
        ln = len(text or "")
        preview = (text or "")[:120].replace("\n"," ")
        logger.info("[SEND] chat=%s len=%s preview=%r", chat_id, ln, preview)
        res = tg_send(chat_id, text, preview=True)
        ok = bool(res.get("ok"))
        logger.info("[SEND] result=%s json=%s", ok, json.dumps(res)[:300])
        return ok

    # --- single-instance lock using flock (linux) or soft lock fallback ---
    def acquire_lock(self, path="/tmp/mork_polling.lock"):
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
            self._lock_fd = fd
            if fcntl:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except Exception:
                    logger.error("[lock] another poller holds %s; exiting", path)
                    return False
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode())
            logger.info("[lock] acquired %s pid=%s", path, os.getpid())
            return True
        except Exception as e:
            logger.error("[lock] failed: %s", e)
            return True  # don't block startup if lock fails oddly

    def release_lock(self, path="/tmp/mork_polling.lock"):
        try:
            if self._lock_fd is not None:
                if fcntl:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            # leave file present for diagnostics
            logger.info("[lock] released %s", path)
        except Exception:
            pass

    def get_updates(self, timeout=25):
        """Get updates from Telegram API"""
        try:
            response = requests.get(
                f"{self.base_url}/getUpdates",
                params={
                    "timeout": timeout,
                    "offset": self.offset,
                },
                timeout=(10, timeout+5)  # (connect, read)
            )
            if response.status_code == 409:
                global _LAST_409_ALERT_TS
                now = time.time()
                # Webhook/poller conflict — alert admin and exit for supervisor to restart
                desc = ""
                try: desc = response.json().get("description","")
                except Exception: desc = response.text[:200]
                logger.error("[poll] 409 Conflict from Telegram API: %s", desc)
                if self.admin_chat_id and now - _LAST_409_ALERT_TS > 120:  # alert at most once per 2 minutes
                    try:
                        tg_send(self.admin_chat_id, "⚠️ 409 Conflict: another consumer is using this bot token.\nPoller will exit so supervisor can restart.", preview=True)
                        _LAST_409_ALERT_TS = now
                    except Exception: pass
                # exit main loop by raising
                raise RuntimeError("409 conflict")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error("Failed to get updates: %s - %s", response.status_code, response.text)
                return None
        except requests.exceptions.ReadTimeout:
            # harmless in long polling; just loop
            return {"ok": True, "result": []}
        except Exception as e:
            logger.error(f"Failed to connect to Telegram API: {e}")
            return None
    
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
            
            # Use comprehensive process_telegram_command router
            if text.startswith('/'):
                if process_telegram_command:
                    try:
                        result = process_telegram_command(update)
                        if result and isinstance(result, dict):
                            response = result.get('response', '')
                            if response:
                                self.send_message(chat_id, response)
                            else:
                                logger.warning(f"Empty response from router for: {text}")
                        else:
                            logger.error(f"Invalid router result: {result}")
                            cmd = text.split()[0]
                            self.send_message(chat_id, f"Command `{cmd}` processing error.")
                    except Exception as e:
                        logger.error(f"Router error for {text}: {e}")
                        cmd = text.split()[0]
                        self.send_message(chat_id, f"Command `{cmd}` encountered an error.")
                else:
                    # Fallback for basic commands when router not available
                    if text.startswith('/ping'):
                        response = "🤖 **Mork F.E.T.C.H Bot**\n✅ Integrated polling active\n🔥 Bot responding from Flask app!"
                        self.send_message(chat_id, response)
                    elif text.startswith('/help'):
                        response = "🐕 **Mork F.E.T.C.H Bot Help**\n\n📋 **Available Commands:**\n• `/ping` - Test connection\n• `/help` - Show help\n\n🔥 Router temporarily unavailable!"
                        self.send_message(chat_id, response)
                    else:
                        cmd = text.split()[0]
                        self.send_message(chat_id, f"Command `{cmd}` not available - router loading.")
                    
        except Exception as e:
            logger.error(f"Error processing update: {e}")
    
    def clear_pending_updates(self):
        """Clear any pending Telegram updates"""
        try:
            logger.info("Clearing pending updates...")
            response = requests.get(f"{self.base_url}/getUpdates", timeout=10)
            if response.ok:
                updates = response.json().get('result', [])
                if updates:
                    last_update_id = max(update.get('update_id', 0) for update in updates)
                    requests.get(f"{self.base_url}/getUpdates", 
                               params={'offset': last_update_id + 1}, timeout=10)
                    logger.info(f"Cleared {len(updates)} pending updates")
                else:
                    logger.info("No pending updates")
            else:
                logger.error(f"Failed to get updates: {response.status_code}")
        except Exception as e:
            logger.error(f"Error clearing updates: {e}")
    
    def run(self):
        """Main polling loop"""
        logger.info("Polling service started")

        # single-instance lock (for main process only, skip in thread)
        if threading.current_thread() is threading.main_thread():
            if not self.acquire_lock():
                return
        
        # Test API connectivity
        test = self.get_updates(timeout=1)
        if not test or not test.get('ok', False):
            logger.error("Initial connectivity test failed")
            return
        logger.info("Polling service started successfully")
        backoff = 1.0
        while self.running:
            # heartbeat every ~60s
            now = time.time()
            if now - self._hb_last > 60:
                self._hb_last = now
                logger.info("[hb] alive offset=%s", self.offset)
            updates_data = self.get_updates()
            if updates_data and updates_data.get('ok'):
                updates = updates_data.get('result', [])
                if updates:
                    last_id = updates[-1]['update_id']
                    logger.info("[poll] got %s updates; last_update_id=%s", len(updates), last_id)
                    for upd in updates:
                        try:
                            self.process_update(upd)
                        except Exception as e:
                            logger.error("Error processing update: %s", e)
                        finally:
                            # advance offset even on individual errors
                            self.offset = upd['update_id'] + 1
                    # success — reset backoff
                    backoff = 1.0
                else:
                    # idle — small jitter
                    time.sleep(0.5 + random.random()*0.3)
                    backoff = min(backoff*1.1, 8.0)
            else:
                # request problem — backoff with jitter
                wait = min(backoff, 15.0) + random.random()*0.5
                logger.warning("[poll] transient issue; backing off %.1fs", wait)
                time.sleep(wait)
                backoff = min(backoff*2.0, 30.0)
        # exit path
        if threading.current_thread() is threading.main_thread():
            self.release_lock()
        logger.info("Polling service stopped")
    
    def start_polling(self):
        """Start polling in background thread"""
        if self.running:
            logger.warning("Polling already running")
            return False
            
        self.running = True
        self.polling_thread = threading.Thread(target=self.run, daemon=True)
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
    
    admin_chat_id = os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID')
    _polling_service = TelegramPollingService(bot_token, admin_chat_id)
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