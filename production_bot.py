#!/usr/bin/env python3
"""
Production-ready polling bot for Telegram
Bypasses external domain routing issues
"""
import logging
import os
import sys
import time
from datetime import datetime

import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ProductionBot:
    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not found")
            sys.exit(1)

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.running = True
        self.offset = 0
        self.processed_messages = set()

    def send_message(self, chat_id, text):
        """Send message via Telegram API"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            response = requests.post(url, json=payload, timeout=10)

            if response.ok:
                result = response.json().get("result", {})
                msg_id = result.get("message_id")
                logger.info(f"✅ Sent message_id={msg_id} to chat_id={chat_id}")
                return True
            else:
                logger.error(f"Failed to send message: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def process_command(self, text, user_id, chat_id, username="Unknown"):
        """Process incoming commands"""
        text = text.strip()

        # Admin check (replace with your admin ID)
        is_admin = user_id == 1653046781

        logger.info(f"[CMD] '{text}' from {username} (admin: {is_admin})")

        if text.startswith("/ping"):
            return "🤖 **Mork F.E.T.C.H Bot**\n✅ Production polling mode active\n🔥 Ready to fetch profits!"

        elif text.startswith("/status"):
            return f"""✅ **Mork F.E.T.C.H Bot Status**
            
**Mode**: Production Polling  
**Status**: Operational  
**Time**: {datetime.now().strftime('%H:%M:%S UTC')}  
**Version**: 1.0

Ready for trading commands!"""

        elif text.startswith("/help"):
            return """🐕 **Mork F.E.T.C.H Bot Help**

**Available Commands:**
• `/ping` - Test bot connectivity  
• `/status` - Check system status  
• `/help` - Show this help  

**Trading Commands:** _(Premium Features)_
• `/wallet` - View wallet info  
• `/snipe <token>` - Manual token snipe  
• `/fetch` - Auto token discovery  

Bot is running in production polling mode for maximum reliability."""

        elif text.startswith("/wallet") and is_admin:
            return "🔐 **Wallet System**\n\nWallet management available.\nUse `/wallet_addr` for address info."

        elif text.startswith("/"):
            return f"Command `{text}` not recognized.\nUse `/help` for available commands."

        return None

    def poll_updates(self):
        """Poll for new messages"""
        try:
            url = f"{self.api_url}/getUpdates"
            params = {"offset": self.offset, "limit": 10, "timeout": 30}

            response = requests.get(url, params=params, timeout=35)

            if not response.ok:
                logger.error(f"Poll failed: {response.status_code}")
                return

            data = response.json()
            if not data.get("ok"):
                logger.error(f"API error: {data}")
                return

            updates = data.get("result", [])

            for update in updates:
                self.offset = max(self.offset, update.get("update_id", 0) + 1)

                message = update.get("message")
                if not message:
                    continue

                # Extract message info
                text = message.get("text", "")
                user = message.get("from", {})
                chat = message.get("chat", {})

                user_id = user.get("id")
                chat_id = chat.get("id")
                username = user.get("username", "Unknown")

                if not text or not chat_id:
                    continue

                # Deduplication
                msg_key = f"{user_id}_{text[:50]}_{message.get('date')}"
                if msg_key in self.processed_messages:
                    continue
                self.processed_messages.add(msg_key)

                # Keep only recent message keys (prevent memory growth)
                if len(self.processed_messages) > 1000:
                    self.processed_messages = set(list(self.processed_messages)[-500:])

                # Process command
                response = self.process_command(text, user_id, chat_id, username)

                if response:
                    self.send_message(chat_id, response)

        except requests.exceptions.Timeout:
            logger.debug("Poll timeout - normal operation")
        except Exception as e:
            logger.error(f"Poll error: {e}")
            time.sleep(5)  # Wait before retry

    def run(self):
        """Main bot loop"""
        logger.info("🚀 Starting Mork F.E.T.C.H Bot (Production Polling)")

        # Delete any existing webhook
        try:
            requests.post(f"{self.api_url}/deleteWebhook", timeout=10)
            logger.info("Webhook deleted (polling mode)")
        except:
            pass

        # Main polling loop
        while self.running:
            try:
                self.poll_updates()
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                self.running = False
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(10)


def main():
    bot = ProductionBot()
    bot.run()


if __name__ == "__main__":
    main()
