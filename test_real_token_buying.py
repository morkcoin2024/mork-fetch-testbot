#!/usr/bin/env python3
"""
Test real token buying capabilities vs demo mode
"""

import asyncio
import sys
sys.path.append('.')

async def test_real_vs_demo():
    """Test the difference between demo and real trading"""
    print("TESTING REAL TOKEN BUYING VS DEMO MODE")
    print("=" * 50)
    
    from automated_pump_trader import start_automated_trading
    from burner_wallet_system import BurnerWalletManager
    from app import app
    
    manager = BurnerWalletManager()
    test_user = "token_buying_test"
    
    with app.app_context():
        # Create wallet
        wallet = manager.get_user_wallet(test_user)
        
        if wallet:
            print(f"Created wallet: {wallet['public_key'][:10]}...")
            
            # Test 1: Current system (should be demo mode with 0 SOL)
            print("\nTest 1: Current automated trading (0 SOL wallet)")
            print("-" * 45)
            
            result1 = await start_automated_trading(test_user, wallet, 0.1)
            
            print(f"Result:")
            print(f"  Success: {result1.get('success')}")
            print(f"  Attempted: {result1.get('attempted_trades', len(result1.get('trades', [])))}")
            print(f"  Message: {result1.get('message')}")
            
            # Check if trades were simulated
            trades = result1.get('trades', [])
            if trades:
                first_trade = trades[0]
                print(f"  First trade method: {first_trade.get('method')}")
                print(f"  First trade simulated: {first_trade.get('simulated', False)}")
                print(f"  First trade TX: {first_trade.get('transaction_hash', 'None')}")
            
            # Test 2: Mock funded wallet scenario
            print(f"\nTest 2: Simulated funded wallet (should attempt real trading)")
            print("-" * 60)
            
            # Temporarily patch the balance check to simulate a funded wallet
            from pump_fun_trading import PumpFunTrader
            original_check = PumpFunTrader.check_wallet_balance
            
            def mock_funded_check(self, wallet_address):
                return {
                    "success": True,
                    "sol_balance": 0.5,  # 0.5 SOL balance
                    "lamports": 500_000_000,
                    "funded": True,
                    "trading_ready": True
                }
            
            # Apply the mock for funded testing
            PumpFunTrader.check_wallet_balance = mock_funded_check
            
            try:
                result2 = await start_automated_trading(test_user + "_funded", wallet, 0.1)
                
                print(f"Funded wallet result:")
                print(f"  Success: {result2.get('success')}")
                print(f"  Attempted: {result2.get('attempted_trades', len(result2.get('trades', [])))}")
                print(f"  Message: {result2.get('message')}")
                
                # Check if trades attempted real execution
                trades2 = result2.get('trades', [])
                if trades2:
                    first_trade2 = trades2[0]
                    print(f"  First trade method: {first_trade2.get('method')}")
                    print(f"  First trade simulated: {first_trade2.get('simulated', False)}")
                    print(f"  First trade error: {first_trade2.get('error', 'None')}")
                
            finally:
                # Restore original method
                PumpFunTrader.check_wallet_balance = original_check
            
            # Analysis
            print(f"\nANALYSIS:")
            print("-" * 20)
            
            unfunded_trades = result1.get('trades', [])
            funded_trades = result2.get('trades', []) if 'result2' in locals() else []
            
            unfunded_simulated = any(t.get('simulated', False) for t in unfunded_trades)
            funded_attempted_real = any(not t.get('simulated', True) for t in funded_trades)
            
            print(f"Unfunded wallet (demo mode):")
            print(f"  - Trades processed: {len(unfunded_trades)}")
            print(f"  - Simulated trades: {unfunded_simulated}")
            print(f"  - Demo mode working: {'YES' if unfunded_simulated else 'NO'}")
            
            print(f"Funded wallet (real mode):")
            print(f"  - Trades processed: {len(funded_trades)}")
            print(f"  - Real trades attempted: {funded_attempted_real}")
            print(f"  - Live mode working: {'YES' if funded_attempted_real else 'NO'}")
            
            if unfunded_simulated and funded_attempted_real:
                print(f"\n✅ DUAL-MODE SYSTEM WORKING!")
                print("The system correctly:")
                print("• Simulates trades for unfunded wallets (demo)")
                print("• Attempts real trades for funded wallets (live)")
                return True
            else:
                print(f"\n⚠️ SYSTEM PARTIALLY WORKING")
                print("Issues found:")
                if not unfunded_simulated:
                    print("• Demo mode not simulating trades correctly")
                if not funded_attempted_real:
                    print("• Live mode not attempting real trades")
                return False
        else:
            print("Failed to create wallet")
            return False

def main():
    """Run the real vs demo test"""
    success = asyncio.run(test_real_vs_demo())
    
    if success:
        print(f"\n🎯 READY FOR REAL TOKEN BUYING!")
        print("Users with funded wallets will execute real trades.")
        print("Users with unfunded wallets will see demo trades.")
    else:
        print(f"\n❌ Real token buying needs more work")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)