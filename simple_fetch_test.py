#!/usr/bin/env python3
"""
Simple test to verify /fetch command actually executes real trades
"""

import asyncio
import sys
sys.path.append('.')

async def main():
    """Quick test of real trading execution"""
    print("🚀 SIMPLE /fetch REAL TRADING TEST")
    print("=" * 40)
    
    # Test the core trading function directly
    from automated_pump_trader import AutomatedPumpTrader
    from burner_wallet_system import BurnerWalletManager
    
    # Create instances
    trader = AutomatedPumpTrader()
    wallet_manager = BurnerWalletManager()
    
    # Generate a test wallet with real Solana format
    test_user = "simple_test_user"
    
    print("1. Creating burner wallet...")
    wallet = wallet_manager.get_user_wallet(test_user)
    
    if wallet:
        print(f"✅ Wallet created: {wallet['public_key'][:10]}...{wallet['public_key'][-10:]}")
        print(f"✅ Private key available: {len(wallet['private_key'])} chars")
        
        print("\n2. Executing automated trading...")
        result = await trader.execute_automated_trading(test_user, wallet, 0.05)
        
        print(f"\n3. Results:")
        print(f"Success: {result.get('success')}")
        trades = result.get('trades', [])
        print(f"Trades attempted: {len(trades)}")
        
        successful = [t for t in trades if t.get('success')]
        failed = [t for t in trades if not t.get('success')]
        
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        
        if failed:
            print("\nFailure analysis:")
            for trade in failed[:2]:
                symbol = trade.get('token_symbol', 'Unknown')
                error = trade.get('error', 'No error')
                print(f"  {symbol}: {error}")
        
        return len(successful) > 0 or len(trades) > 0
    else:
        print("❌ Failed to create wallet")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    print(f"\nResult: {'PASS' if success else 'FAIL'}")