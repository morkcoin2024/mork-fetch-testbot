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

# Deduplication system for updates
_last_updates = OrderedDict()  # update_id -> ts
_MAX = 200

def _seen_update(uid):
    """Check if we've seen this update ID before"""
    now = time.time()
    if uid in _last_updates:
        return True
    _last_updates[uid] = now
    # trim LRU
    while len(_last_updates) > _MAX:
        _last_updates.popitem(last=False)
    return False

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
        """Start polling in background thread"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info("Telegram polling service started")
    
    def stop(self):
        """Stop polling"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Telegram polling service stopped")
    
    def _poll_loop(self):
        """Main polling loop"""
        while self.running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._process_update(update)
                time.sleep(2)  # Poll every 2 seconds
            except Exception as e:
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
            
            def _reply(msg: str) -> str:
                """Helper function for consistent replies"""
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
                return f"❓ Unknown AutoSell command: {cmd}"
                
        except Exception as e:
            logger.error(f"Error processing AutoSell command {cmd}: {e}")
            return f"❌ Error processing command: {str(e)}"
    
    def _process_update(self, update: Dict[str, Any]) -> bool:
        """Process a single update with deduplication"""
        try:
            # Debug logging for router
            print(f"[router] ENTER raw={repr((update.get('message') or {}).get('text'))}")
            
            # Get update ID for deduplication
            update_id = update.get('update_id')
            
            # Deduplicate at the perimeter
            if update_id is not None and _seen_update(update_id):
                return False  # silently ignore repeats
            
            if 'message' not in update:
                return False
            
            message = update['message']
            text = message.get('text', '').strip()
            user_id = message.get('from', {}).get('id')
            chat_id = message.get('chat', {}).get('id')
            
            # Only process messages from admin
            if user_id != self.admin_id:
                return False
            
            # Only process commands
            if not text.startswith('/'):
                return False
            
            # Parse command
            parts = text.split()
            cmd = parts[0].lower()
            args = ' '.join(parts[1:]) if len(parts) > 1 else ''
            
            # Remove @botname suffix if present
            if '@' in cmd:
                cmd = cmd.split('@')[0]
            
            logger.info(f"Processing command: {cmd} with args: {args}")
            
            # Handle AutoSell commands
            if cmd.startswith('/autosell'):
                response = self._process_autosell_command(cmd, args)
                self._send_message(chat_id, response)
                return True
            
            # Handle other commands
            elif cmd in ['/ping', '/test']:
                self._send_message(chat_id, "🏓 Pong! Polling service active.")
                return True
            
            elif cmd == '/help':
                help_text = """🐕 **Mork F.E.T.C.H Bot - The Degens' Best Friend**

**AutoSell Commands:**
/autosell_status - Show AutoSell status
/autosell_on - Enable AutoSell
/autosell_off - Disable AutoSell  
/autosell_list - List all rules
/autosell_interval <seconds> - Set check interval

**Other Commands:**
/ping - Test connection
/help - Show this help"""
                self._send_message(chat_id, help_text)
                return True
            
            else:
                # Unknown command
                self._send_message(chat_id, f"❓ Unknown command: {text}\nUse /help for available commands.")
                return True
                
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return False

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