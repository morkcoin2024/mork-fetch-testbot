#!/usr/bin/env python3
"""Quick polling bot without filelock dependency"""

import logging
import os
import time

import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("quick_poll")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def process_command(text):
    cmd = text.strip().lower()
    if cmd == "/ping":
        return "🏓 Pong! Mork F.E.T.C.H Bot is alive!"
    elif cmd == "/help":
        return "🐕 Mork F.E.T.C.H Bot - Commands:\n/ping, /help, /wallet, /autosell_status"
    elif cmd == "/wallet":
        return "👛 Wallet: Not configured. Use /wallet_new to create."
    elif cmd == "/autosell_status":
        return "🚀 AutoSell: OFF. No active rules."
    elif cmd.startswith("/"):
        return f"Command not recognized: {cmd[:30]}"
    return None


def send_message(chat_id, text):
    try:
        response = requests.post(
            f"{API_BASE}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10
        )
        return response.status_code == 200
    except:
        return False


def main():
    log.info("🤖 Quick polling bot started")
    offset = 0

    while True:
        try:
            response = requests.get(
                f"{API_BASE}/getUpdates", params={"offset": offset, "timeout": 10}, timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    if updates:
                        log.info(f"Processing {len(updates)} updates")

                        for update in updates:
                            offset = update["update_id"] + 1
                            msg = update.get("message", {})
                            text = msg.get("text", "")
                            chat_id = msg.get("chat", {}).get("id")

                            if text and chat_id:
                                log.info(f"Command: {text}")
                                response_text = process_command(text)
                                if response_text:
                                    success = send_message(chat_id, response_text)
                                    log.info(f"Response sent: {success}")

            time.sleep(1)

        except Exception as e:
            log.error(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
