#!/usr/bin/env python3
"""
Ultra-minimal Flask app for webhook testing
"""
import logging
import os

import requests
from flask import Flask, jsonify, request

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create minimal Flask app
app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


@app.route("/")
def home():
    return jsonify({"status": "online", "bot": "Mork F.E.T.C.H", "mode": "minimal"})


@app.route("/webhook", methods=["POST"])
def webhook():
    logger.info("[WEBHOOK] Request received")
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "no_data"}), 400

        msg = data.get("message", {})
        text = msg.get("text", "")
        chat_id = msg.get("chat", {}).get("id")

        if text and chat_id and BOT_TOKEN:
            # Send simple response
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": f"✅ Webhook working! You sent: {text}"}
            requests.post(url, json=payload, timeout=10)
            logger.info(f"[WEBHOOK] Processed: {text}")

        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"[WEBHOOK] Error: {e}")
        return jsonify({"status": "error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
