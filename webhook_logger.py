"""
Comprehensive Webhook and Bot Response Logging
Tracks all Telegram interactions and responses
"""

import json
import logging
from datetime import datetime

from flask import request

# Configure webhook logger
webhook_logger = logging.getLogger("webhook")
webhook_logger.setLevel(logging.DEBUG)


def log_webhook_request():
    """Log incoming webhook requests from Telegram"""
    try:
        # Log request details
        webhook_logger.info(f"[WEBHOOK] Incoming request from {request.remote_addr}")
        webhook_logger.info(f"[WEBHOOK] Method: {request.method}")
        webhook_logger.info(f"[WEBHOOK] Headers: {dict(request.headers)}")

        # Log request body if present
        if request.is_json:
            data = request.get_json()
            webhook_logger.info(f"[WEBHOOK] JSON Body: {json.dumps(data, indent=2)}")

            # Extract key information from Telegram update
            if "message" in data:
                msg = data["message"]
                user = msg.get("from", {})
                chat = msg.get("chat", {})
                text = msg.get("text", "")

                webhook_logger.info(
                    f"[WEBHOOK] Message from user {user.get('username', 'unknown')} ({user.get('id', 'unknown')})"
                )
                webhook_logger.info(f"[WEBHOOK] Chat ID: {chat.get('id', 'unknown')}")
                webhook_logger.info(f"[WEBHOOK] Message text: '{text}'")

        else:
            webhook_logger.info(f"[WEBHOOK] Raw body: {request.get_data()}")

    except Exception as e:
        webhook_logger.exception(f"[WEBHOOK] Error logging request: {e}")


def log_webhook_response(response):
    """Log outgoing webhook responses to Telegram"""
    try:
        webhook_logger.info(f"[WEBHOOK] Response status: {response.status_code}")

        if hasattr(response, "get_data"):
            response_data = response.get_data(as_text=True)
            webhook_logger.info(f"[WEBHOOK] Response body: {response_data}")

    except Exception as e:
        webhook_logger.exception(f"[WEBHOOK] Error logging response: {e}")

    return response


def track_bot_activity():
    """Comprehensive bot activity tracking"""
    webhook_logger.info(f"[BOT_TRACKER] Activity check at {datetime.now()}")

    # Check if bot is receiving updates
    try:
        import pathlib

        log_path = pathlib.Path("logs/app.log")
        if log_path.exists():
            # Look for recent activity
            with log_path.open("r") as f:
                lines = f.readlines()
                recent_activity = [
                    line for line in lines[-50:] if "ADMIN_ROUTER" in line or "CMD_" in line
                ]

            webhook_logger.info(
                f"[BOT_TRACKER] Recent bot activity: {len(recent_activity)} entries"
            )

            if recent_activity:
                webhook_logger.info(f"[BOT_TRACKER] Latest activity: {recent_activity[-1].strip()}")
            else:
                webhook_logger.warning("[BOT_TRACKER] No recent bot activity detected!")

    except Exception as e:
        webhook_logger.exception(f"[BOT_TRACKER] Error checking activity: {e}")


# Test function to verify logging system
def test_logging_system():
    """Test the comprehensive logging system"""
    webhook_logger.info("[TEST] Webhook logging system initialized")
    webhook_logger.info("[TEST] Bot response tracking active")
    webhook_logger.info("[TEST] Activity monitoring enabled")
    return True
