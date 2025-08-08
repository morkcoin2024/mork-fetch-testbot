#!/usr/bin/env python3
"""
Test /fetch command with main bot handler
"""
import requests
import json
import time

def test_fetch_command():
    """Test the /fetch command flow"""
    print("🧪 TESTING /fetch COMMAND WITH MAIN BOT")
    print("="*50)
    
    # Simulate /fetch command
    test_webhook = {
        "update_id": 888888888,
        "message": {
            "message_id": 3001,
            "from": {"id": 88888, "first_name": "FetchTest", "username": "fetchtest"},
            "chat": {"id": 88888, "first_name": "FetchTest", "type": "private"},
            "date": int(time.time()),
            "text": "/fetch"
        }
    }
    
    try:
        response = requests.post("http://0.0.0.0:5000/webhook", json=test_webhook, timeout=10)
        print(f"Bot response: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ /fetch command processed successfully")
            return True
        else:
            print(f"❌ Bot response failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_fetch_command()
    
    if success:
        print("\n✅ Main bot handler is now active")
        print("🚀 /fetch command should work properly now")
    else:
        print("\n❌ Still having issues with /fetch")