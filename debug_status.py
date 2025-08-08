#!/usr/bin/env python3
"""
Debug the exact point where /fetch freezes
"""

import asyncio
import sys
import time
import threading
sys.path.append('.')

def debug_fetch_freeze():
    """Debug where exactly the /fetch command is freezing"""
    print("🔍 DEBUGGING /fetch FREEZE ISSUE")
    print("=" * 40)
    
    from bot import handle_fetch_command
    from app import app
    
    test_chat_id = "debug_freeze_test"
    
    def timeout_handler():
        """Handle timeout if function hangs"""
        time.sleep(10)  # Wait 10 seconds
        print("\n⏰ TIMEOUT: /fetch command appears to be hanging")
        print("This confirms the freeze issue exists")
        import os
        os._exit(1)
    
    # Start timeout thread
    timeout_thread = threading.Thread(target=timeout_handler)
    timeout_thread.daemon = True
    timeout_thread.start()
    
    with app.app_context():
        try:
            print("Executing handle_fetch_command...")
            print("Time:", time.strftime("%H:%M:%S"))
            
            handle_fetch_command(test_chat_id)
            
            print("✅ Command completed successfully")
            print("Time:", time.strftime("%H:%M:%S"))
            return True
            
        except Exception as e:
            print(f"❌ Command failed: {e}")
            print("Time:", time.strftime("%H:%M:%S"))
            import traceback
            traceback.print_exc()
            return False

async def debug_automated_trader():
    """Debug the automated trader component directly"""
    print("\n🤖 DEBUGGING AUTOMATED TRADER")
    print("=" * 35)
    
    from automated_pump_trader import start_automated_trading
    from burner_wallet_system import BurnerWalletManager
    
    wallet_manager = BurnerWalletManager()
    test_user = "debug_trader_test"
    
    # Create wallet
    wallet = wallet_manager.get_user_wallet(test_user)
    
    if wallet and 'private_key' in wallet:
        print(f"Testing with wallet: {wallet['public_key'][:10]}...")
        
        try:
            print("Starting automated trading...")
            print("Time:", time.strftime("%H:%M:%S"))
            
            result = await asyncio.wait_for(
                start_automated_trading(test_user, wallet, 0.05),
                timeout=15.0  # 15 second timeout
            )
            
            print("✅ Automated trading completed")
            print("Time:", time.strftime("%H:%M:%S"))
            print(f"Result: {result.get('success')}")
            print(f"Trades: {len(result.get('trades', []))}")
            
            return True
            
        except asyncio.TimeoutError:
            print("⏰ TIMEOUT: Automated trading hung after 15 seconds")
            print("Time:", time.strftime("%H:%M:%S"))
            return False
        except Exception as e:
            print(f"❌ Automated trading failed: {e}")
            print("Time:", time.strftime("%H:%M:%S"))
            return False
    else:
        print("❌ Could not create wallet")
        return False

def main():
    """Run debugging tests"""
    print("🚀 COMPREHENSIVE /fetch FREEZE DEBUGGING")
    print("=" * 50)
    
    # Test 1: Direct bot command
    print("TEST 1: Direct bot command handler")
    bot_success = debug_fetch_freeze()
    
    # Test 2: Automated trader component
    print("\nTEST 2: Automated trader component")
    trader_success = asyncio.run(debug_automated_trader())
    
    print(f"\n🎯 DEBUGGING RESULTS:")
    print(f"Bot Command: {'PASS' if bot_success else 'HANG/FAIL'}")
    print(f"Automated Trader: {'PASS' if trader_success else 'HANG/FAIL'}")
    
    if not bot_success:
        print("\n🔍 ISSUE IDENTIFIED: Bot command handler is hanging")
        print("This explains why users see freeze at PHASE 1")
    elif not trader_success:
        print("\n🔍 ISSUE IDENTIFIED: Automated trader is hanging")
        print("The freeze happens in the trading logic")
    else:
        print("\n✅ NO HANG DETECTED: Issue may be intermittent")
    
    return bot_success and trader_success

if __name__ == "__main__":
    success = main()