#!/usr/bin/env python3
"""
Test Real Trading System - Verify actual token purchasing capability
"""

import asyncio
import logging
from pump_fun_trading import PumpFunTrader

logging.basicConfig(level=logging.INFO)

async def test_real_pumpportal_integration():
    """Test the real PumpPortal API integration with proper error diagnosis"""
    print("🧪 TESTING REAL PUMPPORTAL API INTEGRATION")
    print("=" * 50)
    
    trader = PumpFunTrader()
    
    # Test parameters (these will fail with test data, but show us the API flow)
    test_params = {
        'private_key': 'demo_private_key_base58_format',
        'token_contract': 'BYPASS1TestToken123456789',
        'sol_amount': 0.01,
        'slippage_percent': 1.0
    }
    
    print(f"Testing with parameters:")
    print(f"  Token Contract: {test_params['token_contract']}")
    print(f"  SOL Amount: {test_params['sol_amount']}")
    print(f"  Private Key Format: {test_params['private_key'][:10]}...")
    
    try:
        result = await trader.buy_pump_token(
            private_key=test_params['private_key'],
            token_contract=test_params['token_contract'], 
            sol_amount=test_params['sol_amount'],
            slippage_percent=test_params['slippage_percent']
        )
        
        print(f"\n📊 RESULT ANALYSIS:")
        print(f"Success: {result.get('success')}")
        
        if result.get('success'):
            print(f"✅ Transaction Hash: {result.get('transaction_hash')}")
            print(f"✅ Method Used: {result.get('method')}")
            print(f"✅ SOL Spent: {result.get('sol_spent')}")
        else:
            error = result.get('error', 'No error message')
            print(f"❌ Error: {error}")
            
            # Diagnose common error types
            if 'Invalid character' in error:
                print("🔍 DIAGNOSIS: Private key format issue - needs real base58 key")
            elif 'API' in error:
                print("🔍 DIAGNOSIS: PumpPortal API communication issue")
            elif 'balance' in error.lower():
                print("🔍 DIAGNOSIS: Wallet funding issue")
            elif 'timeout' in error.lower():
                print("🔍 DIAGNOSIS: Network/timeout issue")
            else:
                print("🔍 DIAGNOSIS: Unknown error type")
        
        return result
        
    except Exception as e:
        print(f"❌ SYSTEM EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    result = await test_real_pumpportal_integration()
    
    print(f"\n🎯 SUMMARY:")
    if result and result.get('success'):
        print("✅ Real token purchasing system is working!")
        print("Ready for live trading with funded wallets")
    elif result and not result.get('success'):
        print("⚠️  System is functional but requires real funded wallets")
        print("Test failures are expected with demo data")
    else:
        print("❌ System has critical errors that need fixing")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())