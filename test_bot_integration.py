#!/usr/bin/env python3
"""
Test the bot integration with live trading
"""
import requests
import json

def test_bot_snipe_command():
    """Test the /snipe command with live trading integration"""
    print("🧪 TESTING BOT SNIPE COMMAND")
    print("="*50)
    
    # Simulate webhook from Telegram
    test_webhook_data = {
        "update_id": 123456789,
        "message": {
            "message_id": 1001,
            "from": {
                "id": 12345,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
                "language_code": "en"
            },
            "chat": {
                "id": 12345,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": 1691500000,
            "text": "/snipe"
        }
    }
    
    try:
        # Send test webhook to our bot
        response = requests.post(
            "http://0.0.0.0:5000/webhook",
            json=test_webhook_data,
            timeout=30
        )
        
        print(f"Bot response: {response.status_code}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Bot is responding to commands")
            return True
        else:
            print("❌ Bot not responding correctly")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_bot_snipe_command()
    
    if success:
        print("\n🎉 Bot integration test successful!")
        print("Ready for live user testing")
    else:
        print("\n❌ Bot integration needs debugging")