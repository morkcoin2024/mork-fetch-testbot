#!/usr/bin/env python3
"""
Active Polling Bot for Telegram AutoSell Commands
Runs independently to process messages when webhook is unavailable
"""

import os
import sys
import time
import requests
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PollingBot:
    def __init__(self):
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.admin_id = int(os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID', '0') or 0)
        self.last_update_id = 0
        self.running = False
        
        if not self.bot_token or not self.admin_id:
            raise ValueError("Missing TELEGRAM_BOT_TOKEN or ASSISTANT_ADMIN_TELEGRAM_ID")
            
        logger.info(f"PollingBot initialized for admin {self.admin_id}")
    
    def get_updates(self) -> list:
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
    
    def send_message(self, chat_id: int, text: str) -> bool:
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
    
    def process_autosell_command(self, cmd: str, args: str) -> str:
        """Process AutoSell commands directly"""
        try:
            # Import autosell module
            sys.path.append('/home/runner/workspace')
            from autosell import AutoSell
            
            autosell = AutoSell()
            
            if cmd == "/autosell_status":
                enabled = autosell.enabled
                interval = autosell.interval
                rules_count = len(autosell.rules)
                thread_alive = autosell.thread and autosell.thread.is_alive()
                
                return f"🤖 AutoSell Status\nEnabled: {enabled}\nInterval: {interval}s\nRules: {rules_count}\nThread alive: {thread_alive}"
            
            elif cmd == "/autosell_on":
                autosell.enabled = True
                autosell.save_state()
                return "🟢 AutoSell enabled."
            
            elif cmd == "/autosell_off":
                autosell.enabled = False
                autosell.save_state()
                return "🔴 AutoSell disabled."
            
            elif cmd == "/autosell_list":
                if not autosell.rules:
                    return "🤖 AutoSell rules: (none)"
                
                lines = ["🤖 AutoSell rules:"]
                for mint, rule in autosell.rules.items():
                    take_profit = rule.get('take_profit', 'None')
                    stop_loss = rule.get('stop_loss', 'None') 
                    lines.append(f"• {mint[:8]}... TP:{take_profit}% SL:{stop_loss}%")
                
                return "\n".join(lines)
            
            elif cmd == "/autosell_interval":
                if args:
                    try:
                        interval = int(args)
                        autosell.interval = interval
                        autosell.save_state()
                        return f"🕐 AutoSell interval set to {interval}s"
                    except ValueError:
                        return "❌ Invalid interval. Use: /autosell_interval <seconds>"
                else:
                    return f"🕐 Current interval: {autosell.interval}s\nUsage: /autosell_interval <seconds>"
            
            else:
                return f"❓ Unknown AutoSell command: {cmd}"
                
        except Exception as e:
            logger.error(f"Error processing AutoSell command {cmd}: {e}")
            return f"❌ Error processing command: {str(e)}"
    
    def process_update(self, update: Dict[str, Any]) -> bool:
        """Process a single update"""
        try:
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
                response = self.process_autosell_command(cmd, args)
                self.send_message(chat_id, response)
                return True
            
            # Handle other commands
            elif cmd in ['/ping', '/test']:
                self.send_message(chat_id, "🏓 Pong! Polling bot is active.")
                return True
            
            else:
                # Unknown command
                self.send_message(chat_id, f"❓ Unknown command: {text}\nUse /help for available commands.")
                return True
                
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return False
    
    def run(self):
        """Main polling loop"""
        self.running = True
        logger.info("Polling bot started")
        
        try:
            while self.running:
                updates = self.get_updates()
                
                for update in updates:
                    self.process_update(update)
                
                # Small delay between polls
                time.sleep(2)
                
        except KeyboardInterrupt:
            logger.info("Polling bot stopped by user")
        except Exception as e:
            logger.error(f"Polling bot error: {e}")
        finally:
            self.running = False
            logger.info("Polling bot shutdown")

def main():
    """Main function"""
    try:
        bot = PollingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start polling bot: {e}")

if __name__ == "__main__":
    main()