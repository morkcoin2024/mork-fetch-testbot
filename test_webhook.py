import logging
import os

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route("/test_webhook", methods=["POST"])
def test_webhook():
    """Ultra-simple webhook for testing"""
    try:
        logger.info("Test webhook called")
        data = request.get_json()

        if not data or not data.get("message"):
            return jsonify({"status": "ok", "message": "No message"}), 200

        text = data["message"].get("text", "")
        chat_id = data["message"]["chat"]["id"]

        logger.info(f"Received: {text} from {chat_id}")

        if text == "/ping":
            # Send response directly to Telegram
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if bot_token:
                payload = {"chat_id": chat_id, "text": "Test webhook pong!"}
                resp = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload
                )
                logger.info(f"Telegram response: {resp.status_code}")

        return jsonify({"status": "ok", "processed": True}), 200

    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
