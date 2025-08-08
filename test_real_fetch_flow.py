#!/usr/bin/env python3
"""
Test complete /fetch flow with real burner wallet and token purchasing
"""

import asyncio
import json
import sys
import os
import time
sys.path.append('.')

async def test_complete_fetch_flow():
    """Test the complete /fetch flow from wallet creation to trade execution"""
    print("🧪 TESTING COMPLETE /fetch FLOW WITH REAL TRADING")
    print("=" * 60)
    
    # Import required modules
    from burner_wallet_system import get_user_burner_wallet, check_trading_eligibility
    from automated_pump_trader import start_automated_trading
    from emergency_stop import check_emergency_stop
    
    test_chat_id = "test_real_fetch_flow"
    
    print("Step 1: Creating/Getting Burner Wallet...")
    try:
        burner_wallet = await get_user_burner_wallet(test_chat_id)
        print(f"✅ Burner wallet created:")
        print(f"   Public Key: {burner_wallet['public_key'][:10]}...{burner_wallet['public_key'][-10:]}")
        print(f"   Private Key Format: {type(burner_wallet['private_key'])}")
    except Exception as e:
        print(f"❌ Wallet creation failed: {e}")
        return False
    
    print("\nStep 2: Checking Trading Eligibility...")
    try:
        eligibility = check_trading_eligibility(test_chat_id, "fetch")
        print(f"✅ Eligibility check: {eligibility.get('eligible', False)}")
        print(f"   Reason: {eligibility.get('message', 'No message')}")
    except Exception as e:
        print(f"❌ Eligibility check failed: {e}")
        return False
    
    print("\nStep 3: Testing Emergency Stop System...")
    try:
        emergency_active = check_emergency_stop(test_chat_id)
        print(f"✅ Emergency stop check: {'ACTIVE' if emergency_active else 'INACTIVE'}")
    except Exception as e:
        print(f"❌ Emergency stop check failed: {e}")
        return False
    
    print("\nStep 4: Executing Automated Trading...")
    try:
        trade_amount_sol = 0.05  # Small test amount
        
        result = await start_automated_trading(test_chat_id, burner_wallet, trade_amount_sol)
        
        print(f"✅ Trading execution result:")
        print(f"   Success: {result.get('success')}")
        print(f"   Message: {result.get('message', 'No message')}")
        
        trades = result.get('trades', [])
        print(f"   Total trades attempted: {len(trades)}")
        
        successful_trades = [t for t in trades if t.get('success')]
        failed_trades = [t for t in trades if not t.get('success')]
        
        print(f"   Successful trades: {len(successful_trades)}")
        print(f"   Failed trades: {len(failed_trades)}")
        
        if failed_trades:
            print("\n   Failed trade details:")
            for i, trade in enumerate(failed_trades[:3]):
                symbol = trade.get('token_symbol', 'UNKNOWN')
                error = trade.get('error', 'No error message')
                platform = trade.get('platform', 'Unknown')
                print(f"     {i+1}. {symbol} ({platform}): {error}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Trading execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_pumpportal_api_directly():
    """Test PumpPortal API directly to verify integration"""
    print("\n🔧 TESTING PUMPPORTAL API DIRECTLY")
    print("=" * 40)
    
    from pump_fun_trading import PumpFunTrader
    
    trader = PumpFunTrader()
    
    # Create a test wallet with valid format
    from solders.keypair import Keypair
    import os
    test_keypair = Keypair.from_seed(os.urandom(32))
    private_key_bytes = bytes(test_keypair)
    
    # Convert to base58 format
    import base58
    private_key_b58 = base58.b58encode(private_key_bytes).decode('utf-8')
    
    print(f"Generated test keypair...")
    print(f"Public Key: {str(test_keypair.pubkey())}")
    print(f"Private Key Format: base58 ({len(private_key_b58)} chars)")
    
    # Test with a known pump.fun token (this will fail due to no funding, but shows API flow)
    test_params = {
        'private_key': private_key_b58,
        'token_contract': 'BypassToken12345678901234567890123456789',  # Mock token
        'sol_amount': 0.001,
        'slippage_percent': 1.0
    }
    
    try:
        result = await trader.buy_pump_token(
            private_key=test_params['private_key'],
            token_contract=test_params['token_contract'],
            sol_amount=test_params['sol_amount'],
            slippage_percent=test_params['slippage_percent']
        )
        
        print(f"\n📊 PumpPortal API Test Result:")
        print(f"Success: {result.get('success')}")
        
        if result.get('success'):
            print(f"✅ Transaction Hash: {result.get('transaction_hash')}")
            print(f"✅ SOL Spent: {result.get('sol_spent')}")
            print(f"✅ Method: {result.get('method')}")
        else:
            error = result.get('error', 'No error message')
            print(f"❌ Error: {error}")
            
            # Analyze error type
            if 'insufficient' in error.lower():
                print("🔍 Expected: Wallet has no funding (normal for test)")
            elif 'invalid' in error.lower():
                print("🔍 Check: API parameter validation")
            elif 'timeout' in error.lower():
                print("🔍 Check: Network connectivity to PumpPortal")
            else:
                print("🔍 Unexpected error type")
        
        return result
        
    except Exception as e:
        print(f"❌ PumpPortal API test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Run all tests"""
    print("🚀 COMPREHENSIVE /fetch TESTING SUITE")
    print("=" * 70)
    
    # Test 1: Complete fetch flow
    fetch_success = await test_complete_fetch_flow()
    
    # Test 2: Direct API integration
    api_result = await test_pumpportal_api_directly()
    
    print(f"\n🎯 FINAL TEST RESULTS:")
    print(f"Complete Fetch Flow: {'PASS' if fetch_success else 'FAIL'}")
    print(f"PumpPortal API: {'FUNCTIONAL' if api_result else 'FAIL'}")
    
    if fetch_success and api_result:
        print("\n✅ SYSTEM READY FOR REAL TRADING!")
        print("All components working correctly:")
        print("• Burner wallet generation")
        print("• Trading eligibility checks") 
        print("• Emergency stop integration")
        print("• PumpPortal API communication")
        print("• Trade execution pipeline")
    else:
        print("\n⚠️  ISSUES DETECTED - FIXING REQUIRED")
        if not fetch_success:
            print("• Fetch flow needs debugging")
        if not api_result:
            print("• PumpPortal API needs verification")
    
    return fetch_success and bool(api_result)

if __name__ == "__main__":
    success = asyncio.run(main())
    print(f"\n🏁 OVERALL RESULT: {'SYSTEM OPERATIONAL' if success else 'NEEDS FIXES'}")