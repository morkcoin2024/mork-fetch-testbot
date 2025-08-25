#!/usr/bin/env python3
"""
DIRECT POLLING BOT - Minimal, bulletproof implementation
"""
import logging
import os
import sys
import time

import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOT] %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not found")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    """Send message to Telegram"""
    try:
        url = f"{API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        response = requests.post(url, json=data, timeout=10)

        if response.ok:
            result = response.json().get("result", {})
            msg_id = result.get("message_id")
            logger.info(f"✅ Sent message {msg_id} to chat {chat_id}")
            return True
        else:
            logger.error(f"❌ Send failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Send error: {e}")
        return False


def process_message(message):
    """Process a single message"""
    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    username = message.get("from", {}).get("username", "Unknown")

    if not text or not chat_id:
        return

    logger.info(f"📨 Processing: '{text}' from {username} ({user_id})")

    # Process commands
    if text.startswith("/ping"):
        response = (
            "🤖 **Mork F.E.T.C.H Bot**\n✅ Direct polling mode active\n🔥 Bot is working perfectly!"
        )
        send_message(chat_id, response)

    elif text.startswith("/status"):
        response = f"✅ **Bot Status: OPERATIONAL**\n⚡ Mode: Direct Polling\n🕐 Time: {time.strftime('%H:%M:%S UTC')}\n\nReady for trading commands!"
        send_message(chat_id, response)

    elif text.startswith("/help"):
        response = "🐕 **Mork F.E.T.C.H Bot Help**\n\n📋 **Available Commands:**\n• `/ping` - Test bot connection\n• `/status` - System status\n• `/help` - Show this help\n\n🔥 Bot is fully operational in direct polling mode!"
        send_message(chat_id, response)

    elif text.startswith("/"):
        response = f"Command `{text}` not recognized.\nUse `/help` for available commands."
        send_message(chat_id, response)


def main():
    logger.info("🚀 Starting Direct Polling Bot")

    # Delete webhook
    try:
        requests.post(f"{API_URL}/deleteWebhook", timeout=10)
        logger.info("Webhook deleted - polling mode active")
    except Exception as e:
        logger.error(f"Webhook delete error: {e}")

    offset = 0
    processed_messages = set()

    while True:
        try:
            # Get updates
            url = f"{API_URL}/getUpdates"
            params = {"offset": offset, "limit": 10, "timeout": 25}

            logger.debug(f"Polling with offset {offset}...")
            response = requests.get(url, params=params, timeout=30)

            if not response.ok:
                logger.error(f"Poll failed: {response.status_code}")
                time.sleep(5)
                continue

            data = response.json()
            if not data.get("ok"):
                logger.error(f"API error: {data}")
                time.sleep(5)
                continue

            updates = data.get("result", [])

            if updates:
                logger.info(f"📥 Received {len(updates)} updates")

                for update in updates:
                    update_id = update.get("update_id", 0)
                    offset = max(offset, update_id + 1)

                    # Skip duplicates
                    if update_id in processed_messages:
                        continue
                    processed_messages.add(update_id)

                    # Clean old processed IDs
                    if len(processed_messages) > 1000:
                        processed_messages = set(list(processed_messages)[-500:])

                    message = update.get("message")
                    if message:
                        process_message(message)
            else:
                logger.debug("No new updates")

        except requests.exceptions.Timeout:
            logger.debug("Poll timeout - continuing")
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
