#!/usr/bin/env python3
"""
Minimal router command tests (no network)
Tests command parsing and routing logic
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import process_telegram_command

def mk(cmd, user_id=999999):
    """Helper to create test update"""
    return {
        "message": {
            "text": cmd,
            "from": {"id": user_id},
            "chat": {"id": 12345}
        }
    }

def test_wallet_non_admin():
    """Test /wallet (non-admin user ID) → status "ok" """
    result = process_telegram_command(mk("/wallet"))
    assert result["status"] == "ok"

def test_autosell_status_non_admin():
    """Test /autosell_status (non-admin) → status "ok" """
    result = process_telegram_command(mk("/autosell_status"))
    assert result["status"] == "ok"

def test_ping():
    """Test /ping → status "ok" """
    result = process_telegram_command(mk("/ping"))
    assert result["status"] == "ok"

def test_help():
    """Test /help → status "ok" """
    result = process_telegram_command(mk("/help"))
    assert result["status"] == "ok"

def test_wallet_with_bot_suffix():
    """Test /wallet@SomeBot → status "ok" (parsed to /wallet)"""
    result = process_telegram_command(mk("/wallet@SomeBot"))
    assert result["status"] == "ok"

def test_wallet_with_leading_space():
    """Test leading-space " /wallet" → status "ok" """
    result = process_telegram_command(mk(" /wallet"))
    assert result["status"] == "ok"

def test_unknown_command():
    """Test /not_a_real_cmd → status "unknown_command" """
    result = process_telegram_command(mk("/not_a_real_cmd"))
    assert result["status"] == "unknown_command"

if __name__ == "__main__":
    # Run all test functions manually if not using pytest
    tests = [
        test_wallet_non_admin,
        test_autosell_status_non_admin,
        test_ping,
        test_help,
        test_wallet_with_bot_suffix,
        test_wallet_with_leading_space,
        test_unknown_command,
    ]
    
    for test_func in tests:
        test_func()
        print(f"✓ {test_func.__name__}")
    
    print("All tests passed!")