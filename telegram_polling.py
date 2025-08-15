#!/usr/bin/env python3
"""
Telegram Polling Service - Integrated with main application
"""

import os
import sys
import time
import requests
import threading
import logging
from typing import Dict, Any, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)

# Perimeter deduplication system 
_seen = OrderedDict()
_MAX = 200

def _dupe(uid):
    if uid in _seen: 
        return True
    _seen[uid] = 1
    while len(_seen) > _MAX: 
        _seen.popitem(last=False)
    return False

# Global process lock to prevent multiple polling instances
_polling_lock = threading.Lock()
_polling_active = False

class TelegramPollingService:
    def __init__(self):
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.admin_id = int(os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID', '0') or 0)
        self.last_update_id = 0
        self.running = False
        self.thread = None
        
        if not self.bot_token or not self.admin_id:
            raise ValueError("Missing TELEGRAM_BOT_TOKEN or ASSISTANT_ADMIN_TELEGRAM_ID")
            
        logger.info(f"TelegramPollingService initialized for admin {self.admin_id}")
    
    def start(self):
        """Start polling in background thread with process lock"""
        global _polling_active
        
        with _polling_lock:
            if _polling_active or self.running:
                logger.warning("Polling already active, skipping start")
                return
            _polling_active = True
            
        # Simple webhook cleanup before starting polling
        try:
            delete_url = f"https://api.telegram.org/bot{self.bot_token}/deleteWebhook"
            requests.post(delete_url, json={"drop_pending_updates": True}, timeout=10)
            logger.info("Webhook cleanup completed")
        except Exception:
            pass
            
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info("Telegram polling service started")
    
    def stop(self):
        """Stop polling and release lock"""
        global _polling_active
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            
        with _polling_lock:
            _polling_active = False
            
        logger.info("Telegram polling service stopped")
    
    def _poll_loop(self):
        """Main polling loop"""
        while self.running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self.handle_update(update)
                time.sleep(2)  # Poll every 2 seconds
            except Exception as e:
                if "409" in str(e) or "Conflict" in str(e):
                    logger.warning(f"409 conflict detected, backing off: {e}")
                    time.sleep(10)  # Longer backoff for conflicts
                else:
                    logger.error(f"Polling error: {e}")
                    time.sleep(5)  # Wait longer on error
    
    def _get_updates(self) -> list:
        """Get new updates from Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                "offset": self.last_update_id + 1,
                "limit": 10,
                "timeout": 5
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('ok'):
                updates = data.get('result', [])
                if updates:
                    self.last_update_id = updates[-1]['update_id']
                return updates
            else:
                logger.error(f"Failed to get updates: {data}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    def _send_message(self, chat_id: int, text: str) -> bool:
        """Send message to chat"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"Message sent successfully to {chat_id}")
                return True
            else:
                logger.error(f"Failed to send message: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def _process_autosell_command(self, cmd: str, args: str) -> str:
        """Process AutoSell commands directly"""
        try:
            # Import autosell module functions directly
            import sys
            import os
            sys.path.insert(0, '/home/runner/workspace')
            
            # Import autosell module
            import autosell
            
            def _reply(msg: str, status: str = "ok") -> str:
                """Helper function for consistent replies with optional status"""
                return msg
            
            if cmd == "/autosell_status":
                st = autosell.status()
                if isinstance(st, dict):
                    return _reply(f"🤖 AutoSell Status\nEnabled: {st.get('enabled', False)}\nInterval: {st.get('interval_sec', 0)}s\nRules: {st.get('rules_count', 0)}\nThread alive: {st.get('thread_alive', False)}")
                else:
                    return _reply("🤖 AutoSell Status: Unable to fetch status")
            
            elif cmd == "/autosell_on":
                autosell.enable()
                return _reply("🟢 AutoSell enabled.")
            
            elif cmd == "/autosell_off":
                autosell.disable()
                return _reply("🔴 AutoSell disabled.")
            
            elif cmd == "/autosell_list":
                rules = autosell.get_rules()
                if not rules:
                    return _reply("🤖 AutoSell rules: (none)")
                
                lines = ["🤖 AutoSell rules:"]
                for mint, rule in rules.items():
                    take_profit = rule.get('tp_pct', 'None')
                    stop_loss = rule.get('sl_pct', 'None') 
                    lines.append(f"• {mint[:8]}... TP:{take_profit}% SL:{stop_loss}%")
                
                return _reply("\n".join(lines))
            
            elif cmd == "/autosell_interval":
                if args:
                    try:
                        interval = int(args)
                        autosell.set_interval(interval)
                        return _reply(f"⏱️ AutoSell interval set to {interval}s")
                    except ValueError:
                        return _reply("❌ Invalid interval. Use: /autosell_interval <seconds>")
                else:
                    st = autosell.status()
                    current_interval = st.get('interval_sec', 0) if isinstance(st, dict) else 0
                    return _reply(f"⏱️ AutoSell interval: {current_interval}s\nUsage: /autosell_interval <seconds>")
            
            else:
                clean = (cmd or "").replace("\n", " ")
                return _reply(f"❓ Unknown AutoSell command: {clean}\nUse /help for available commands.", status="unknown_command")
                
        except Exception as e:
            logger.error(f"Error processing AutoSell command {cmd}: {e}")
            return f"❌ Error processing command: {str(e)}"
    
    def handle_update(self, update):
        """Handle update with perimeter deduplication"""
        uid = update.get("update_id")
        if uid is not None and _dupe(uid): 
            return  # ignore duplicate delivery

        # Import required modules for the router
        import sys
        sys.path.insert(0, '/home/runner/workspace')
        
        from app import process_telegram_command
        from telegram_safety import send_telegram_safe
        
        # Get chat_id for responses
        message = update.get("message") or {}
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        
        # Only process messages from admin
        if user_id != self.admin_id or not chat_id:
            return
        
        try:
            result = process_telegram_command(update)
            if isinstance(result, dict) and result.get("handled"):
                out = result["response"]
            elif isinstance(result, str):
                out = result
            else:
                out = "⚠️ Processing error occurred."
            
            send_telegram_safe(self.bot_token or "", chat_id, out)
            
        except Exception as e:
            logger.error(f"Error in handle_update: {e}")
            send_telegram_safe(self.bot_token or "", chat_id, "⚠️ Processing error occurred.")

# Global instance
polling_service = None

def start_polling_service():
    """Start the global polling service"""
    global polling_service
    try:
        if polling_service is None:
            polling_service = TelegramPollingService()
        polling_service.start()
        return True
    except Exception as e:
        logger.error(f"Failed to start polling service: {e}")
        return False

def stop_polling_service():
    """Stop the global polling service"""
    global polling_service
    if polling_service:
        polling_service.stop()