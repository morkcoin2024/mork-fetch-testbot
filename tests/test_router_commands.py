#!/usr/bin/env python3
"""
Minimal router command tests (no network)
Tests command parsing and routing logic
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import process_telegram_command

def make_update(text, user_id=999999):
    """Helper to create test update"""
    return {
        "message": {
            "text": text,
            "from": {"id": user_id},
            "chat": {"id": 12345}
        }
    }

def test_commands():
    """Test command routing"""
    
    # Test 1: /wallet (non-admin user ID) → status "ok" (admin-deny text)
    result = process_telegram_command(make_update("/wallet"))
    assert result["status"] == "ok", f"Expected ok, got {result['status']}"
    assert "Admin only" in result["response"] or "Wallet System" in result["response"]
    print("✓ Test 1: /wallet non-admin")
    
    # Test 2: /autosell_status (non-admin) → status "ok" (admin-deny text) 
    result = process_telegram_command(make_update("/autosell_status"))
    assert result["status"] == "ok", f"Expected ok, got {result['status']}"
    assert "Admin only" in result["response"] or "AutoSell" in result["response"]
    print("✓ Test 2: /autosell_status non-admin")
    
    # Test 3: /ping → status "ok"
    result = process_telegram_command(make_update("/ping"))
    assert result["status"] == "ok", f"Expected ok, got {result['status']}"
    print("✓ Test 3: /ping")
    
    # Test 4: /help → status "ok"
    result = process_telegram_command(make_update("/help"))
    assert result["status"] == "ok", f"Expected ok, got {result['status']}"
    assert "Mork F.E.T.C.H Bot" in result["response"]
    print("✓ Test 4: /help")
    
    # Test 5: /wallet@SomeBot → status "ok" (parsed to /wallet)
    result = process_telegram_command(make_update("/wallet@SomeBot"))
    assert result["status"] == "ok", f"Expected ok, got {result['status']}"
    print("✓ Test 5: /wallet@SomeBot")
    
    # Test 6: leading-space " /wallet" → status "ok"
    result = process_telegram_command(make_update(" /wallet"))
    assert result["status"] == "ok", f"Expected ok, got {result['status']}"
    print("✓ Test 6: ' /wallet' with leading space")
    
    # Test 7: /not_a_real_cmd → status "unknown_command"
    result = process_telegram_command(make_update("/not_a_real_cmd"))
    assert result["status"] == "unknown_command", f"Expected unknown_command, got {result['status']}"
    assert "Command not recognized" in result["response"]
    print("✓ Test 7: /not_a_real_cmd unknown command")

if __name__ == "__main__":
    test_commands()
    print("All tests passed!")