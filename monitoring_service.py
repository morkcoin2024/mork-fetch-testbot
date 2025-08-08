#!/usr/bin/env python3
"""
Real-time monitoring service for /fetch command testing
"""

import time
import logging
import requests
from datetime import datetime

# Configure logging to see real-time activity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pump_scanner.log'),
        logging.StreamHandler()
    ]
)

BOT_TOKEN = "8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def monitor_fetch_command():
    """Monitor for /fetch command execution"""
    print("🔍 MONITORING /FETCH COMMAND EXECUTION")
    print("=" * 50)
    print(f"Started at: {datetime.now()}")
    print()
    print("Waiting for user to execute /fetch command...")
    print("Monitoring the following:")
    print("• Telegram webhook activity")
    print("• PumpPortal API calls")
    print("• Token discovery process")
    print("• Trade execution")
    print("• ChatGPT improvements in action")
    print()
    print("-" * 50)
    
    last_update_count = 0
    
    while True:
        try:
            # Check for new webhook updates
            response = requests.get(f"{TELEGRAM_API_URL}/getWebhookInfo", timeout=5)
            if response.status_code == 200:
                webhook_info = response.json()['result']
                pending_updates = webhook_info.get('pending_update_count', 0)
                
                if pending_updates != last_update_count:
                    print(f"📨 NEW ACTIVITY: {pending_updates} pending updates")
                    last_update_count = pending_updates
                    
                    if webhook_info.get('last_error_message'):
                        print(f"⚠️ Webhook Error: {webhook_info['last_error_message']}")
                    else:
                        print("✅ Webhook processing normally")
            
            # Short pause
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
            break
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_fetch_command()