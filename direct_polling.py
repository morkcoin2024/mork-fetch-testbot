#!/usr/bin/env python3
"""
Direct polling bot - simplified version that just works
"""
import logging
import os
import time

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main polling function"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found")
        return

    base_url = f"https://api.telegram.org/bot{token}"
    offset = 0

    # Clear webhook
    try:
        requests.post(f"{base_url}/deleteWebhook", timeout=5)
        logger.info("Webhook cleared")
    except Exception as e:
        logger.warning(f"Failed to clear webhook: {e}")

    # Test API
    try:
        resp = requests.get(f"{base_url}/getMe", timeout=10)
        if resp.status_code == 200:
            bot_info = resp.json().get("result", {})
            logger.info(f"Bot ready: @{bot_info.get('username', 'unknown')}")
        else:
            logger.error(f"API test failed: {resp.status_code}")
            return
    except Exception as e:
        logger.error(f"API connection failed: {e}")
        return

    logger.info("Starting polling loop...")

    while True:
        try:
            # Get updates
            params = {"offset": offset, "timeout": 10}
            resp = requests.get(f"{base_url}/getUpdates", params=params, timeout=15)

            if resp.status_code != 200:
                logger.error(f"getUpdates failed: {resp.status_code}")
                time.sleep(5)
                continue

            data = resp.json()
            if not data.get("ok"):
                logger.error(f"API error: {data}")
                time.sleep(5)
                continue

            updates = data.get("result", [])
            logger.info(f"Got {len(updates)} updates")

            for update in updates:
                try:
                    # Simple ping response
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat_id = msg.get("chat", {}).get("id")

                    if text.lower().startswith("/ping") and chat_id:
                        response_text = "🤖 Pong! Direct polling bot active."

                        send_resp = requests.post(
                            f"{base_url}/sendMessage",
                            json={"chat_id": chat_id, "text": response_text},
                            timeout=10,
                        )

                        if send_resp.ok:
                            msg_id = send_resp.json().get("result", {}).get("message_id")
                            logger.info(f"Sent response message_id={msg_id} to chat_id={chat_id}")
                        else:
                            logger.error(f"Failed to send response: {send_resp.status_code}")

                    # Update offset
                    offset = update["update_id"] + 1

                except Exception as e:
                    logger.error(f"Error processing update: {e}")
                    offset = update.get("update_id", offset) + 1

            if not updates:
                logger.info(f"Heartbeat - offset={offset}")

        except KeyboardInterrupt:
            logger.info("Stopped by user")
            break
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
