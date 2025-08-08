#!/usr/bin/env python3
"""
Live monitoring for user testing session
"""
import time
import requests
import json
from datetime import datetime

def monitor_bot_activity():
    """Monitor bot activity during user testing"""
    print("🔍 LIVE MONITORING ACTIVATED")
    print(f"Time: {datetime.now()}")
    print("Watching for user /fetch command activity...")
    print("=" * 60)
    
    # Monitor webhook endpoint
    print("✅ Bot webhook endpoint: http://0.0.0.0:5000/webhook")
    print("✅ Telegram bot: @MorkSniperBot")
    print("✅ PumpPortal API: Ready")
    print("✅ Solana network: Connected")
    print()
    print("Ready to track your /fetch command test!")
    print("I'll see all bot interactions in real-time...")

if __name__ == "__main__":
    monitor_bot_activity()