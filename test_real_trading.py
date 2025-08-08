#!/usr/bin/env python3
"""
Test the exact user flow that causes the freeze
"""

import asyncio
import sys
import time
sys.path.append('.')

def test_real_user_fetch_flow():
    """Test exactly what happens when a user runs /fetch"""
    print("🧪 TESTING REAL USER /fetch FLOW")
    print("=" * 40)
    
    from bot import handle_fetch_command, handle_message, get_or_create_session, update_session
    from models import UserSession, db
    from app import app
    
    test_chat_id = "real_user_test"
    
    with app.app_context():
        print("Step 1: Setting up fresh user session...")
        # Clean slate
        existing = UserSession.query.filter_by(chat_id=test_chat_id).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
        
        # Create wallet first (like a real user would)
        print("Step 2: Creating burner wallet...")
        from burner_wallet_system import BurnerWalletManager
        wallet_manager = BurnerWalletManager()
        wallet = wallet_manager.get_user_wallet(test_chat_id)
        
        if wallet:
            print(f"✅ Wallet created: {wallet['public_key'][:10]}...")
            
            print("Step 3: Running /fetch command...")
            try:
                # This is what happens when user types /fetch
                handle_fetch_command(test_chat_id)
                print("✅ /fetch command executed")
                
                # Check session state
                session = get_or_create_session(test_chat_id)
                print(f"Session state: {session.state}")
                print(f"Trading mode: {getattr(session, 'trading_mode', 'Not set')}")
                
                # Now simulate entering an amount (like user would)
                print("Step 4: Simulating user entering SOL amount...")
                message_text = "0.1"  # User enters 0.1 SOL
                
                result = handle_message(test_chat_id, message_text)
                print(f"✅ Amount processing result: {result}")
                
                # Check what happens next
                session = get_or_create_session(test_chat_id)
                print(f"Updated state: {session.state}")
                
                return True
                
            except Exception as e:
                print(f"❌ Error in flow: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print("❌ Failed to create wallet")
            return False

async def test_automated_trading_trigger():
    """Test the specific automated trading trigger"""
    print("\n🤖 TESTING AUTOMATED TRADING TRIGGER")
    print("=" * 42)
    
    from automated_pump_trader import AutomatedPumpTrader
    from burner_wallet_system import BurnerWalletManager
    
    trader = AutomatedPumpTrader()
    wallet_manager = BurnerWalletManager()
    
    test_user = "trigger_test"
    
    # Create wallet
    wallet = wallet_manager.get_user_wallet(test_user)
    
    if wallet:
        print(f"Testing automated trading with wallet: {wallet['public_key'][:10]}...")
        
        # Test with timeout to catch hangs
        try:
            print("Starting automated trading with timeout...")
            print("Time:", time.strftime("%H:%M:%S"))
            
            # This is the exact call that happens after user enters amount
            result = await asyncio.wait_for(
                trader.execute_automated_trading(test_user, wallet, 0.1),
                timeout=30.0  # 30 second timeout
            )
            
            print("✅ Automated trading completed")
            print("Time:", time.strftime("%H:%M:%S"))
            print(f"Success: {result.get('success')}")
            print(f"Message: {result.get('message', 'No message')}")
            
            trades = result.get('trades', [])
            print(f"Trades executed: {len(trades)}")
            
            return True
            
        except asyncio.TimeoutError:
            print("⏰ TIMEOUT: Automated trading hung!")
            print("Time:", time.strftime("%H:%M:%S"))
            print("This is likely where the freeze occurs")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Time:", time.strftime("%H:%M:%S"))
            import traceback
            traceback.print_exc()
            return False
    else:
        print("❌ Failed to create wallet")
        return False

def main():
    """Run the real user flow tests"""
    print("🚀 TESTING REAL USER /fetch FLOW")
    print("=" * 45)
    
    # Test 1: Full user flow
    flow_success = test_real_user_fetch_flow()
    
    # Test 2: Automated trading trigger
    trading_success = asyncio.run(test_automated_trading_trigger())
    
    print(f"\n🎯 REAL FLOW TEST RESULTS:")
    print(f"User Flow: {'PASS' if flow_success else 'FAIL'}")
    print(f"Trading Trigger: {'PASS' if trading_success else 'HANG/FAIL'}")
    
    if not flow_success:
        print("\n🔍 ISSUE: User flow is broken")
    elif not trading_success:
        print("\n🔍 ISSUE: Automated trading hangs during execution")
        print("This explains the 'PHASE 1' freeze users experience")
    else:
        print("\n✅ SYSTEM WORKING: No hang detected")
    
    return flow_success and trading_success

if __name__ == "__main__":
    success = main()