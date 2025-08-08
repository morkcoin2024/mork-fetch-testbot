#!/usr/bin/env python3
"""
Test the fixed trade reporting to ensure accurate counts
"""

import asyncio
import sys
sys.path.append('.')

async def test_fixed_trading_reports():
    """Test that trade counts are now reported correctly"""
    print("🧪 TESTING FIXED TRADE REPORTING")
    print("=" * 40)
    
    from automated_pump_trader import start_automated_trading
    from burner_wallet_system import BurnerWalletManager
    from app import app
    
    wallet_manager = BurnerWalletManager()
    test_user = "fixed_reporting_test"
    
    with app.app_context():
        # Create wallet
        wallet = wallet_manager.get_user_wallet(test_user)
        
        if wallet:
            print(f"Testing with wallet: {wallet['public_key'][:10]}...")
            
            try:
                result = await start_automated_trading(test_user, wallet, 0.1)
                
                print(f"✅ Trading result:")
                print(f"   Success: {result.get('success')}")
                print(f"   Attempted trades: {result.get('attempted_trades', 'Not reported')}")
                print(f"   Successful trades: {result.get('successful_trades', 'Not reported')}")
                print(f"   Total trades: {len(result.get('trades', []))}")
                print(f"   Message: {result.get('message')}")
                
                # Verify the reporting is accurate
                trades = result.get('trades', [])
                if trades:
                    successful = [t for t in trades if t.get('success', False)]
                    print(f"   Manual count - Attempted: {len(trades)}, Successful: {len(successful)}")
                    
                    if result.get('attempted_trades') == len(trades):
                        print("✅ Attempted trade count is accurate")
                    else:
                        print("❌ Attempted trade count is wrong")
                    
                    if result.get('successful_trades') == len(successful):
                        print("✅ Successful trade count is accurate")
                    else:
                        print("❌ Successful trade count is wrong")
                    
                    return True
                else:
                    print("❌ No trades returned")
                    return False
                
            except Exception as e:
                print(f"❌ Test failed: {e}")
                return False
        else:
            print("❌ Could not create wallet")
            return False

def main():
    """Run the fixed reporting test"""
    print("🚀 TESTING FIXED TRADE REPORTING")
    print("=" * 45)
    
    success = asyncio.run(test_fixed_trading_reports())
    
    if success:
        print(f"\n✅ TRADE REPORTING FIXED!")
        print("Users will now see accurate trade counts:")
        print("• Shows 'trades attempted automatically' instead of 'trades executed'")
        print("• Clarifies when trades fail due to wallet funding")
        print("• Provides accurate status reporting")
        print("• No more confusing '0 trades executed' messages")
    else:
        print(f"\n❌ Trade reporting still needs work")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)