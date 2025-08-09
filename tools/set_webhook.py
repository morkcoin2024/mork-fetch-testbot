#!/usr/bin/env python3
"""
Webhook Setup Tool for Mork F.E.T.C.H Bot
Sets the Telegram webhook URL for the bot
"""

import os
import requests

def set_webhook():
    """Set the Telegram webhook URL"""
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable not set")
        return False
    
    # Get the public webhook URL (e.g., your Replit HTTPS URL + /webhook/<token>)
    WEBHOOK_URL = os.environ.get("PUBLIC_WEBHOOK_URL")
    if not WEBHOOK_URL:
        print("ERROR: PUBLIC_WEBHOOK_URL environment variable not set")
        print("Example: https://your-repl-name--username.replit.app/webhook/your-bot-token")
        return False
    
    print(f"Setting webhook URL: {WEBHOOK_URL}")
    
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={"url": WEBHOOK_URL}
        )
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text}")
        
        if r.status_code == 200:
            response_data = r.json()
            if response_data.get("ok"):
                print("✅ Webhook set successfully!")
                return True
            else:
                print(f"❌ Webhook setup failed: {response_data.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP error: {r.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error setting webhook: {e}")
        return False

if __name__ == "__main__":
    set_webhook()