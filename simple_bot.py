#!/usr/bin/env python3
"""
SIMPLE WORKING TELEGRAM BOT - No complexity, just works
"""
import logging
import os
import sys
import time

import requests

# Simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not set")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
offset = 0


def send_message(chat_id, text):
    """Send message to Telegram"""
    try:
        url = f"{API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        r = requests.post(url, json=data, timeout=10)
        if r.ok:
            log.info(f"SENT to {chat_id}: {text[:30]}...")
            return True
        else:
            log.error(f"SEND FAILED: {r.status_code}")
    except Exception as e:
        log.error(f"SEND ERROR: {e}")
    return False


def process_message(msg):
    """Process incoming message"""
    text = msg.get("text", "").strip()
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")

    if not text or not chat_id:
        return

    log.info(f"MSG from {user_id}: {text}")

    # Simple command responses
    if text.startswith("/ping"):
        send_message(chat_id, "🤖 Mork F.E.T.C.H Bot\n✅ ONLINE and working!\nPolling mode active.")

    elif text.startswith("/status"):
        send_message(
            chat_id,
            f"✅ Bot Status: OPERATIONAL\n⚡ Mode: Direct Polling\n🕐 Time: {time.strftime('%H:%M:%S')}",
        )

    elif text.startswith("/help"):
        send_message(
            chat_id,
            "🐕 Mork F.E.T.C.H Bot Commands:\n\n/ping - Test connection\n/status - System status\n/help - This help\n\nBot is fully operational!",
        )

    elif text.startswith("/"):
        send_message(
            chat_id, f"Command '{text}' not recognized.\nUse /help for available commands."
        )


def main():
    global offset
    log.info("🚀 Starting Mork F.E.T.C.H Bot - Simple Mode")

    # Delete webhook first
    try:
        requests.post(f"{API_URL}/deleteWebhook", timeout=10)
        log.info("Webhook deleted")
    except:
        pass

    # Main loop
    while True:
        try:
            # Get updates
            url = f"{API_URL}/getUpdates"
            params = {"offset": offset, "limit": 10, "timeout": 30}

            r = requests.get(url, params=params, timeout=35)

            if not r.ok:
                log.error(f"Poll failed: {r.status_code}")
                time.sleep(5)
                continue

            data = r.json()
            if not data.get("ok"):
                log.error(f"API error: {data}")
                time.sleep(5)
                continue

            updates = data.get("result", [])

            for update in updates:
                offset = max(offset, update.get("update_id", 0) + 1)

                msg = update.get("message")
                if msg:
                    process_message(msg)

            if len(updates) > 0:
                log.info(f"Processed {len(updates)} updates")

        except requests.exceptions.Timeout:
            log.debug("Poll timeout (normal)")
        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception as e:
            log.error(f"Error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
