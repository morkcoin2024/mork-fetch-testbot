#!/usr/bin/env python3
"""
Comprehensive /fetch command diagnostic for ChatGPT analysis
"""

import traceback
import asyncio
from datetime import datetime

def test_fetch_command_comprehensive():
    """Comprehensive test of /fetch command flow"""
    
    print("🔍 COMPREHENSIVE /FETCH DIAGNOSTIC REPORT")
    print("=" * 60)
    print(f"Test Date: {datetime.now()}")
    print()
    
    # Test 1: Import Chain
    print("TEST 1: Import Chain Analysis")
    print("-" * 30)
    
    try:
        print("Testing simplified_bot import...")
        import simplified_bot
        print("✅ simplified_bot imported successfully")
    except Exception as e:
        print(f"❌ simplified_bot import failed: {e}")
        traceback.print_exc()
        return
    
    try:
        print("Testing pump_fun_trading import...")
        from pump_fun_trading import PumpFunTrader
        print("✅ pump_fun_trading imported successfully")
    except Exception as e:
        print(f"❌ pump_fun_trading import failed: {e}")
        traceback.print_exc()
    
    try:
        print("Testing automated_pump_trader import...")
        from automated_pump_trader import AutomatedPumpTrader
        print("✅ automated_pump_trader imported successfully")
    except Exception as e:
        print(f"❌ automated_pump_trader import failed: {e}")
        traceback.print_exc()
    
    print()
    
    # Test 2: /fetch Handler Function
    print("TEST 2: /fetch Handler Function Analysis")
    print("-" * 30)
    
    try:
        # Check if handle_fetch_command exists
        if hasattr(simplified_bot, 'handle_fetch_command'):
            print("✅ handle_fetch_command function found")
            
            # Try to call it with a test chat_id
            print("Testing handle_fetch_command execution...")
            simplified_bot.handle_fetch_command(999999)  # Test chat ID
            print("✅ handle_fetch_command executed without errors")
            
        else:
            print("❌ handle_fetch_command function NOT FOUND")
            
    except Exception as e:
        print(f"❌ handle_fetch_command execution failed: {e}")
        traceback.print_exc()
    
    print()
    
    # Test 3: Core Trading System
    print("TEST 3: Core Trading System Analysis")
    print("-" * 30)
    
    try:
        from pump_fun_trading import PumpFunTrader
        trader = PumpFunTrader()
        print("✅ PumpFunTrader initialized")
        
        # Test balance check
        result = trader.check_wallet_balance("So11111111111111111111111111111111111111112")
        print(f"✅ Balance check result: {result.get('success', False)}")
        
    except Exception as e:
        print(f"❌ Core trading system test failed: {e}")
        traceback.print_exc()
    
    print()
    
    # Test 4: Database Connection
    print("TEST 4: Database Connection Analysis")
    print("-" * 30)
    
    try:
        from app import app
        from models import UserSession
        
        with app.app_context():
            print("✅ App context created")
            
            # Try to query a user session
            session = UserSession.query.filter_by(chat_id="999999").first()
            print(f"✅ Database query executed (session: {session is not None})")
            
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        traceback.print_exc()
    
    print()
    
    # Test 5: Webhook Integration
    print("TEST 5: Webhook Integration Analysis")  
    print("-" * 30)
    
    try:
        # Test webhook processing
        test_update = {
            "update_id": 999999,
            "message": {
                "chat": {"id": 999999},
                "from": {"first_name": "TestUser"},
                "text": "/fetch"
            }
        }
        
        result = simplified_bot.handle_telegram_update(test_update)
        print("✅ Webhook processing test completed")
        
    except Exception as e:
        print(f"❌ Webhook integration test failed: {e}")
        traceback.print_exc()
    
    print()
    
    # Summary for ChatGPT
    print("SUMMARY FOR CHATGPT ANALYSIS")
    print("=" * 40)
    print("PROBLEM: /fetch command not executing properly")
    print()
    print("POTENTIAL ISSUES TO INVESTIGATE:")
    print("1. Import chain failures preventing module loading")
    print("2. Missing or corrupted handle_fetch_command function")
    print("3. Database connection issues preventing user state management")
    print("4. Webhook processing errors blocking command execution")
    print("5. Trading system initialization failures")
    print()
    print("CHATGPT SHOULD FOCUS ON:")
    print("• Function definition completeness in simplified_bot.py")
    print("• Error handling in command processing")
    print("• Async/sync compatibility issues")
    print("• Database session management")
    print("• Import dependency resolution")

if __name__ == "__main__":
    test_fetch_command_comprehensive()