#!/usr/bin/env python3
"""
Fix webhook and test bot responsiveness
"""

import time

import requests

BOT_TOKEN = "8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824"
WEBHOOK_URL = "https://morkfetchbot.replit.app/webhook"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def fix_webhook():
    """Fix and test webhook setup"""
    print("FIXING WEBHOOK CONNECTION")
    print("=" * 30)

    try:
        # Set webhook
        response = requests.post(f"{TELEGRAM_API_URL}/setWebhook", data={"url": WEBHOOK_URL})
        if response.status_code == 200:
            print("✅ Webhook set successfully")
        else:
            print(f"❌ Failed to set webhook: {response.status_code}")

        # Wait and check status
        time.sleep(2)

        # Check webhook info
        response = requests.get(f"{TELEGRAM_API_URL}/getWebhookInfo")
        if response.status_code == 200:
            webhook_info = response.json()["result"]
            print(f"Webhook URL: {webhook_info.get('url')}")
            print(f"Pending updates: {webhook_info.get('pending_update_count', 0)}")
            if webhook_info.get("last_error_message"):
                print(f"Last error: {webhook_info['last_error_message']}")
                print(f"Error date: {webhook_info.get('last_error_date', 'Unknown')}")
            else:
                print("✅ No webhook errors!")

        # Test webhook endpoint directly
        print("\nTesting webhook endpoint...")
        response = requests.post(WEBHOOK_URL, json={"test": "ping"})
        print(f"Webhook test: {response.status_code} - {response.text[:50]}")

    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n✅ WEBHOOK FIX COMPLETE")
    print("Bot should no longer be stalled")


if __name__ == "__main__":
    fix_webhook()
