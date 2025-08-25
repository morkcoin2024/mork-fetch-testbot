#!/usr/bin/env python3
"""
Robust polling worker that integrates with the main app
"""
import logging
import os
import sys
import time

import requests

# Set environment for scanner-free operation
os.environ["FETCH_ENABLE_SCANNERS"] = "0"

# Import app functionality
try:
    from app import process_telegram_command
    from simple_polling_bot import SimplePollingBot
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RobustPollingWorker:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found")

        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.running = False

    def clear_webhook(self):
        """Clear any existing webhook"""
        try:
            resp = requests.post(f"{self.base_url}/deleteWebhook", timeout=5)
            logger.info("Webhook cleared")
            return True
        except Exception as e:
            logger.warning(f"Failed to clear webhook: {e}")
            return False

    def test_api(self):
        """Test API connection"""
        try:
            resp = requests.get(f"{self.base_url}/getMe", timeout=10)
            if resp.status_code == 200:
                bot_info = resp.json().get("result", {})
                username = bot_info.get("username", "unknown")
                logger.info(f"🤖 Bot ready: @{username}")
                return True
            else:
                logger.error(f"API test failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"API connection failed: {e}")
            return False

    def send_message(self, chat_id, text):
        """Send a message"""
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10
            )
            if resp.ok:
                result = resp.json().get("result", {})
                msg_id = result.get("message_id")
                logger.info(f"✅ Sent message_id={msg_id} to chat_id={chat_id}")
                return True
            else:
                logger.error(f"Failed to send message: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def process_update(self, update):
        """Process a single update"""
        try:
            msg = update.get("message", {})
            text = msg.get("text", "").strip()
            chat_id = msg.get("chat", {}).get("id")
            user = msg.get("from", {})
            user_id = user.get("id")

            if not text or not chat_id:
                return

            logger.info(f"Processing: '{text}' from user {user_id}")

            # Simple ping response
            if text.lower().startswith("/ping"):
                response = "🤖 Pong! Polling worker active and operational."
                self.send_message(chat_id, response)
                return

            # Try to use the main app's command processing
            try:
                result = process_telegram_command(update)
                if result and isinstance(result, str):
                    self.send_message(chat_id, result)
                else:
                    logger.info("Command processed, no response needed")
            except Exception as e:
                logger.error(f"Error in main command processing: {e}")
                # Fallback response
                if text.startswith("/"):
                    self.send_message(chat_id, f"Command received but encountered an error: {e}")

        except Exception as e:
            logger.error(f"Error processing update: {e}")

    def start(self):
        """Start the polling loop"""
        if not self.clear_webhook():
            logger.warning("Could not clear webhook, continuing anyway...")

        if not self.test_api():
            logger.error("API test failed, cannot start")
            return False

        self.running = True
        logger.info("🚀 Starting polling loop...")

        consecutive_errors = 0
        max_errors = 5

        while self.running:
            try:
                # Get updates
                params = {"offset": self.offset, "timeout": 10}
                resp = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=15)

                if resp.status_code != 200:
                    logger.error(f"getUpdates failed: {resp.status_code}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        logger.error("Too many consecutive errors, stopping")
                        break
                    time.sleep(5)
                    continue

                data = resp.json()
                if not data.get("ok"):
                    logger.error(f"API error: {data}")
                    consecutive_errors += 1
                    time.sleep(5)
                    continue

                # Reset error counter on success
                consecutive_errors = 0

                updates = data.get("result", [])

                if updates:
                    logger.info(f"📥 Processing {len(updates)} updates")

                    for update in updates:
                        self.process_update(update)
                        self.offset = update["update_id"] + 1
                else:
                    logger.info(f"💓 Heartbeat - offset={self.offset}")

            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    logger.error("Too many consecutive errors, stopping")
                    break
                time.sleep(5)

        self.running = False
        logger.info("Polling stopped")
        return True

    def stop(self):
        """Stop the polling loop"""
        self.running = False


def main():
    """Main function"""
    worker = RobustPollingWorker()
    worker.start()


if __name__ == "__main__":
    main()
