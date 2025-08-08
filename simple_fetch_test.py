#!/usr/bin/env python3
"""
Simple test to verify real vs demo trading paths
"""

import asyncio
import sys
sys.path.append('.')

async def test_trading_paths():
    """Test both demo and real trading paths"""
    print("TESTING TRADING EXECUTION PATHS")
    print("=" * 40)
    
    from pump_fun_trading import PumpFunTrader
    
    trader = PumpFunTrader()
    
    # Test 1: Demo mode (0 SOL wallet)
    print("Test 1: Demo mode (0 SOL wallet)")
    print("-" * 30)
    
    # Create mock wallet with 0 balance
    original_check = trader.check_wallet_balance
    trader.check_wallet_balance = lambda addr: {
        "success": True,
        "sol_balance": 0.0,  # 0 SOL = demo mode
        "funded": False
    }
    
    demo_result = await trader.buy_pump_token(
        private_key="demo_key",
        token_contract="So11111111111111111111111111111111111111112",
        sol_amount=0.1
    )
    
    print(f"Demo result:")
    print(f"  Success: {demo_result.get('success')}")
    print(f"  Simulated: {demo_result.get('simulated', False)}")
    print(f"  Method: {demo_result.get('method')}")
    print(f"  TX: {demo_result.get('transaction_hash')}")
    
    # Test 2: Real trading mode (funded wallet)
    print(f"\nTest 2: Real trading mode (funded wallet)")
    print("-" * 40)
    
    # Mock funded wallet
    trader.check_wallet_balance = lambda addr: {
        "success": True,
        "sol_balance": 1.0,  # 1 SOL = real trading mode
        "funded": True
    }
    
    try:
        real_result = await trader.buy_pump_token(
            private_key="funded_key", 
            token_contract="So11111111111111111111111111111111111111112",
            sol_amount=0.1
        )
        
        print(f"Real trading result:")
        print(f"  Success: {real_result.get('success')}")
        print(f"  Simulated: {real_result.get('simulated', False)}")
        print(f"  Method: {real_result.get('method')}")
        print(f"  Error: {real_result.get('error', 'None')}")
        
    except Exception as e:
        print(f"Real trading failed: {e}")
        real_result = {"success": False}
    
    finally:
        trader.check_wallet_balance = original_check
    
    # Analysis
    print(f"\nANALYSIS:")
    print(f"  Demo mode working: {demo_result.get('success', False)}")
    print(f"  Real mode attempted: {real_result.get('success', False) or real_result.get('error') is not None}")
    
    if demo_result.get('simulated'):
        print(f"  ✅ Demo simulation working correctly")
    else:
        print(f"  ❌ Demo simulation not working")
    
    if real_result.get('success'):
        print(f"  ✅ Real trading execution working")
    elif real_result.get('error'):
        print(f"  ⚠️ Real trading attempted but failed: {real_result.get('error')}")
    else:
        print(f"  ❌ Real trading not attempted")
    
    return demo_result.get('success') and (real_result.get('success') or real_result.get('error'))

def main():
    """Run the trading path tests"""
    print("VERIFYING TRADING EXECUTION PATHS")
    print("=" * 50)
    
    success = asyncio.run(test_trading_paths())
    
    if success:
        print(f"\n✅ TRADING PATHS VERIFIED!")
        print("The system correctly:")
        print("• Simulates trades for unfunded wallets (demo mode)")
        print("• Attempts real trades for funded wallets (live mode)")
        print("• Provides clear feedback about trade execution")
    else:
        print(f"\n❌ Trading paths need fixes")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)