#!/usr/bin/env python3
import json
import sys
import traceback

# Simulate the exact webhook call that's failing
def test_webhook_error():
    try:
        # This might be where the error originates
        print("Testing potential error sources...")
        
        # Check if mork_bot variable exists and what happens when it's None
        mork_bot = None
        if not mork_bot:
            print("✓ mork_bot is None - this might trigger the error")
            
        # Test the exact error message
        if not mork_bot:
            raise Exception("Bot not available")
            
    except Exception as e:
        print(f"Caught exception: {e}")
        print(f"Exception type: {type(e).__name__}")
        print("This matches the webhook error pattern!")
        return {"error": str(e)}, 500

if __name__ == "__main__":
    result = test_webhook_error()
    print(f"Result: {result}")
