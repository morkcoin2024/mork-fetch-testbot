#!/usr/bin/env python3
"""
Quick smoke test for command routing logic
Tests the ALL_COMMANDS scope issue directly
"""

# Import the command list and processing function
from app import ALL_COMMANDS, process_telegram_command


def test_command_routing():
    """Test command routing without Telegram"""
    print(f"ALL_COMMANDS loaded: {len(ALL_COMMANDS)} commands")
    print(f"First few: {ALL_COMMANDS[:5]}")

    # Test known command
    test_update_wallet = {
        "message": {
            "text": "/wallet",
            "from": {"id": 1653046781},  # Admin ID
            "chat": {"id": 12345},
        }
    }

    # Test unknown command
    test_update_fake = {
        "message": {"text": "/not_a_real_cmd", "from": {"id": 1653046781}, "chat": {"id": 12345}}
    }

    print("\n=== Testing /wallet (known command) ===")
    try:
        result1 = process_telegram_command(test_update_wallet)
        print(f"Result: {result1}")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\n=== Testing /not_a_real_cmd (unknown command) ===")
    try:
        result2 = process_telegram_command(test_update_fake)
        print(f"Result: {result2}")
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    test_command_routing()
