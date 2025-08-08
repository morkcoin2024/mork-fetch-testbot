#!/usr/bin/env python3
"""
DIRECT FUNDED WALLET TEST
Using the exact address you funded: EFaozTXxM1zvhaX4aXjB49drCPjwYY7G5QaLKYhenBpe
No wallet system dependencies - direct test
"""
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def direct_funded_test():
    """Test with direct funded address"""
    print("🎯 DIRECT FUNDED WALLET TEST")
    print(f"Time: {datetime.now()}")
    print("Address: EFaozTXxM1zvhaX4aXjB49drCPjwYY7G5QaLKYhenBpe")
    print("Expected: 1 SOL funded")
    print("Test amount: 0.1 SOL")
    print("CRITICAL: Token value > 0 or EMERGENCY STOP")
    print("=" * 60)
    
    try:
        from clean_pump_fun_trading import CleanPumpTrader
        
        # Direct address check
        funded_address = "EFaozTXxM1zvhaX4aXjB49drCPjwYY7G5QaLKYhenBpe"
        trader = CleanPumpTrader()
        
        # Check funded balance directly
        print("💰 Checking funded wallet balance...")
        balance_result = trader.check_wallet_balance(funded_address)
        
        if not balance_result.get('success'):
            print(f"❌ BALANCE CHECK FAILED: {balance_result.get('error', 'Unknown error')}")
            return {'result': 'BALANCE_CHECK_FAILED', 'emergency_stop': True}
        
        current_balance = balance_result.get('sol_balance', 0)
        print(f"✅ Balance found: {current_balance:.6f} SOL")
        
        if current_balance < 0.1:
            print(f"❌ INSUFFICIENT: Need 0.1 SOL, have {current_balance:.6f}")
            print("Either funding not confirmed or wrong address")
            return {'result': 'INSUFFICIENT_FUNDS', 'emergency_stop': True}
        
        print(f"🎉 SUFFICIENT FUNDS: {current_balance:.6f} SOL available")
        print("Ready for real funded test!")
        
        # CRITICAL TEST: Since we don't have the private key for your funded wallet,
        # we'll simulate the test with a demo private key but show what would happen
        print("\n⚠️ SIMULATION MODE (No private key for funded wallet)")
        print("This shows what the clean implementation would do:")
        
        # Test the clean implementation logic without actual transaction
        test_token = "DirectFundedTestToken123"
        trade_amount = 0.1
        
        print(f"\n🧪 CLEAN IMPLEMENTATION TEST:")
        print(f"Address: {funded_address}")
        print(f"Balance: {current_balance:.6f} SOL")
        print(f"Trade amount: {trade_amount} SOL")
        print(f"Token: {test_token}")
        
        # Simulate what would happen
        if current_balance >= trade_amount:
            print("\n✅ FUNDING CHECK: PASSED")
            print(f"✅ Clean implementation would proceed with trade")
            print(f"✅ Sufficient balance: {current_balance:.6f} >= {trade_amount}")
            
            # For actual test, you'd need to provide private key or use test wallet
            print("\n⚠️ FOR REAL TEST:")
            print("1. Either provide private key for funded wallet, OR")
            print("2. Send 1 SOL to a test wallet we can control")
            
            return {
                'result': 'READY_FOR_REAL_TEST',
                'funded_address': funded_address,
                'balance': current_balance,
                'sufficient_funds': True,
                'emergency_stop': False,
                'next_step': 'NEED_PRIVATE_KEY_OR_CONTROLLED_WALLET'
            }
        else:
            print(f"\n❌ FUNDING CHECK: FAILED")
            print(f"❌ Insufficient balance: {current_balance:.6f} < {trade_amount}")
            
            return {
                'result': 'INSUFFICIENT_FUNDS',
                'funded_address': funded_address,
                'balance': current_balance,
                'sufficient_funds': False,
                'emergency_stop': True
            }
            
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        return {'result': 'ERROR', 'emergency_stop': True, 'error': str(e)}

async def main():
    result = await direct_funded_test()
    
    print("\n" + "=" * 60)
    print("🏁 DIRECT FUNDED TEST RESULTS:")
    for key, value in result.items():
        print(f"{key}: {value}")
    
    if result.get('sufficient_funds'):
        print("\n🟢 FUNDING CONFIRMED - Ready for real test")
        print("Need: Private key for funded wallet OR controlled test wallet")
    else:
        print("\n🔴 FUNDING ISSUE - Check wallet address or wait for confirmation")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())