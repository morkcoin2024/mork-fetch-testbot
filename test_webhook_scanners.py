#!/usr/bin/env python3
"""
Test script to verify scanner state in webhook process
"""
import time

import requests


def test_diag_command():
    """Test the /diag command and parse webhook logs"""
    print("=== WEBHOOK SCANNER SYNCHRONIZATION TEST ===")

    # Send /diag command
    webhook_url = "https://telegram-bot-morkcoin2024.replit.app/webhook"
    payload = {
        "message": {
            "chat": {"id": 1653046781},
            "from": {"id": 1653046781, "username": "Drahcir196"},
            "text": "/diag",
        }
    }

    response = requests.post(webhook_url, json=payload, timeout=10)
    print(f"Webhook response: {response.json()}")

    # The actual diagnostic response should be sent to Telegram
    # Since we can't easily retrieve it, let's test solscanstats instead
    time.sleep(2)

    print("\n=== TESTING /solscanstats FOR SCANNER STATE ===")
    payload["message"]["text"] = "/solscanstats"
    response = requests.post(webhook_url, json=payload, timeout=10)
    print(f"Solscanstats response: {response.json()}")


if __name__ == "__main__":
    test_diag_command()
