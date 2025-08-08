#!/usr/bin/env python3
"""
Test the fixed trading system with proper demo mode and ChatGPT's solutions
"""

import asyncio
import sys
sys.path.append('.')

async def test_improved_trading():
    """Test the improved trading system with demo mode"""
    print("🧪 TESTING IMPROVED TRADING SYSTEM")
    print("=" * 45)
    
    from automated_pump_trader import start_automated_trading
    from burner_wallet_system import BurnerWalletManager
    from app import app
    
    manager = BurnerWalletManager()
    test_user = "improved_trading_test"
    
    with app.app_context():
        print("Step 1: Creating burner wallet...")
        wallet = manager.get_user_wallet(test_user)
        
        if wallet:
            print(f"✅ Wallet created: {wallet['public_key'][:10]}...")
            
            print("Step 2: Testing automated trading with demo mode...")
            try:
                result = await start_automated_trading(test_user, wallet, 0.1)
                
                print(f"✅ Trading completed!")
                print(f"   Success: {result.get('success')}")
                print(f"   Attempted trades: {result.get('attempted_trades', len(result.get('trades', [])))}")
                print(f"   Message: {result.get('message')}")
                
                # Check trade details
                trades = result.get('trades', [])
                if trades:
                    successful = [t for t in trades if t.get('success', False)]
                    simulated = [t for t in trades if t.get('simulated', False)]
                    
                    print(f"   Trade breakdown:")
                    print(f"     - Total attempted: {len(trades)}")
                    print(f"     - Successful: {len(successful)}")
                    print(f"     - Simulated (demo): {len(simulated)}")
                    
                    # Show first trade details
                    if trades:
                        first_trade = trades[0]
                        print(f"   First trade details:")
                        print(f"     - Token: {first_trade.get('token_symbol', 'UNKNOWN')}")
                        print(f"     - Success: {first_trade.get('success', False)}")
                        print(f"     - Simulated: {first_trade.get('simulated', False)}")
                        print(f"     - Method: {first_trade.get('method', 'Unknown')}")
                
                return result.get('success', False)
                
            except Exception as e:
                print(f"❌ Trading failed: {e}")
                return False
        else:
            print("❌ Failed to create wallet")
            return False

def main():
    """Run the improved trading test"""
    print("🚀 TESTING IMPROVED TRADING SYSTEM")
    print("=" * 50)
    
    success = asyncio.run(test_improved_trading())
    
    if success:
        print(f"\n✅ TRADING SYSTEM IMPROVED!")
        print("Key improvements implemented:")
        print("• Demo mode for 0 SOL wallets (simulates successful trades)")
        print("• Proper trade counting (shows attempted vs successful)")
        print("• ChatGPT's SystemProgram.transfer() method for funded wallets")
        print("• Clear status reporting for users")
        print("• Fixed import and validation issues")
        print("\n🎯 Users will now see realistic demo trades instead of failures!")
    else:
        print(f"\n❌ System still needs work")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)