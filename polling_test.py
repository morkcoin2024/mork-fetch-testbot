#!/usr/bin/env python3
"""
Emergency polling mode to bypass webhook delivery issues
"""

import logging
import os
import time

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID")


def get_updates(offset=None):
    """Get updates using polling"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset

    try:
        response = requests.get(url, params=params, timeout=15)
        return response.json()
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return None


# Import the centralized bridge function
try:
    from telegram_polling import send_message
except ImportError:
    # Fallback for backward compatibility
    def send_message(chat_id, text):
        """Fallback: Send message via direct Telegram API"""
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

        try:
            response = requests.post(url, json=data, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None


def main():
    logger.info("Starting polling mode test...")
    logger.info(f"Admin ID: {ADMIN_ID}")

    offset = None

    while True:
        try:
            result = get_updates(offset)
            if not result or not result.get("ok"):
                logger.warning(f"Bad response: {result}")
                time.sleep(5)
                continue

            updates = result.get("result", [])
            if updates:
                logger.info(f"Received {len(updates)} updates")

                for update in updates:
                    offset = update["update_id"] + 1

                    if "message" in update:
                        message = update["message"]
                        text = message.get("text", "")
                        user_id = message.get("from", {}).get("id", "")
                        chat_id = message.get("chat", {}).get("id", "")

                        logger.info(f"Message: '{text}' from user {user_id}")

                        # Only respond to admin
                        if str(user_id) == str(ADMIN_ID):
                            if text == "/test123":
                                response = "✅ /test123 works via polling!"
                                send_message(chat_id, response)
                                logger.info("Sent test123 response")
                            elif text == "/help":
                                response = "📖 Help command works via polling!"
                                send_message(chat_id, response)
                                logger.info("Sent help response")
                            elif text.startswith("/"):
                                response = f"🤖 Received command: {text} (via polling)"
                                send_message(chat_id, response)
                                logger.info(f"Sent generic response for {text}")
                        else:
                            logger.info(f"Ignoring message from non-admin user {user_id}")

            time.sleep(2)

        except KeyboardInterrupt:
            logger.info("Polling stopped")
            break
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
