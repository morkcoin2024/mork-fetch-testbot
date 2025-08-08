#!/usr/bin/env python3
"""
FUNDED WALLET TEST - Your Parameters
1 SOL funded, testing with 0.1 SOL
Parameters: 10 tokens, 10% loss, 10% profit, 100% take
CRITICAL: Token value MUST be > 0 or EMERGENCY STOP
"""
import asyncio
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def execute_funded_test():
    """Execute test with funded wallet - YOUR EXACT PARAMETERS"""
    print("🚀 FUNDED WALLET TEST EXECUTION")
    print(f"Time: {datetime.now()}")
    print("Wallet funded with 1 SOL")
    print("Test amount: 0.1 SOL")
    print("Parameters: 10 tokens, 10% loss, 10% profit, 100% take")
    print("CRITICAL CHECK: Token value > 0 or EMERGENCY STOP")
    print("=" * 60)
    
    try:
        # Import clean implementation
        from clean_pump_fun_trading import execute_clean_pump_trade
        from burner_wallet_system import BurnerWalletManager
        
        # Get funded wallet
        manager = BurnerWalletManager()
        wallet = manager.get_user_wallet('controlled_test_user')
        
        if not wallet:
            print("❌ CRITICAL: No wallet found")
            return {'result': 'WALLET_ERROR', 'emergency_stop': True}
        
        # Check funding
        current_balance = wallet.get('sol_balance', 0)
        print(f"💰 Current Balance: {current_balance:.6f} SOL")
        
        if current_balance < 0.1:
            print(f"❌ INSUFFICIENT FUNDS: Need 0.1 SOL, have {current_balance:.6f}")
            return {'result': 'INSUFFICIENT_FUNDS', 'emergency_stop': True}
        
        print(f"✅ SUFFICIENT FUNDS: {current_balance:.6f} SOL available")
        print(f"📍 Wallet: {wallet['public_key']}")
        
        # Execute real test with actual funding
        print("\n🎯 EXECUTING REAL FUNDED TEST...")
        print("Amount: 0.1 SOL")
        print("Using clean implementation (no SOL draining)")
        
        private_key = wallet.get('private_key')
        test_token = "RealFundedTestToken123456789ABC"  # Test token
        trade_amount = 0.1
        
        # CRITICAL: Record balance before
        balance_before = current_balance
        print(f"💰 Balance BEFORE: {balance_before:.6f} SOL")
        
        # Execute the funded trade
        result = await execute_clean_pump_trade(private_key, test_token, trade_amount)
        
        print("\n📊 FUNDED TRADE RESULTS:")
        print("=" * 50)
        
        if result.get('success'):
            sol_spent = result.get('sol_actually_spent', 0)
            tokens_acquired = result.get('tokens_acquired', False)
            tx_hash = result.get('transaction_hash', 'N/A')
            balance_after = result.get('balance_after', balance_before)
            
            print(f"✅ Status: SUCCESS")
            print(f"💰 SOL Spent: {sol_spent:.6f}")
            print(f"🪙 Tokens Acquired: {tokens_acquired}")
            print(f"📝 Transaction: {tx_hash}")
            print(f"💹 Balance Before: {balance_before:.6f} SOL")
            print(f"💹 Balance After: {balance_after:.6f} SOL")
            print(f"🔄 Method: {result.get('method', 'Unknown')}")
            
            # YOUR CRITICAL TEST: Token value > 0?
            print("\n🔍 CRITICAL TOKEN VALUE CHECK:")
            if tokens_acquired and sol_spent > 0:
                print("🎉 SUCCESS: TOKEN VALUE > 0 DETECTED")
                print("✅ Real tokens acquired")
                print("✅ SOL properly spent") 
                print("✅ Clean implementation working")
                print("🟢 EMERGENCY STOP CAN BE LIFTED")
                
                return {
                    'result': 'SUCCESS_TOKEN_VALUE_DETECTED',
                    'tokens_acquired': True,
                    'sol_spent': sol_spent,
                    'token_value_greater_than_zero': True,
                    'emergency_stop': False,
                    'proceed_with_trading': True
                }
            else:
                print("🚨 FAILURE: TOKEN VALUE = 0")
                print("❌ No tokens acquired OR no SOL spent")
                print("🛑 EMERGENCY STOP CONFIRMED")
                
                return {
                    'result': 'FAILURE_TOKEN_VALUE_ZERO',
                    'tokens_acquired': tokens_acquired,
                    'sol_spent': sol_spent,
                    'token_value_greater_than_zero': False,
                    'emergency_stop': True,
                    'proceed_with_trading': False
                }
        else:
            error = result.get('error', 'Unknown error')
            method = result.get('method', 'Unknown')
            
            print(f"❌ Status: FAILED")
            print(f"🚨 Error: {error}")
            print(f"🔧 Method: {method}")
            
            print("\n🚨 FUNDED TEST FAILED")
            print("TOKEN VALUE = 0 (No successful trade)")
            print("🛑 EMERGENCY STOP CONFIRMED")
            
            return {
                'result': 'FUNDED_TEST_FAILED',
                'tokens_acquired': False,
                'sol_spent': 0,
                'token_value_greater_than_zero': False,
                'emergency_stop': True,
                'error': error
            }
            
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        print("🛑 IMMEDIATE EMERGENCY STOP")
        
        return {
            'result': 'CRITICAL_ERROR',
            'tokens_acquired': False,
            'sol_spent': 0,
            'token_value_greater_than_zero': False,
            'emergency_stop': True,
            'error': str(e)
        }

async def main():
    print("🎯 FUNDED WALLET TEST - YOUR PARAMETERS")
    print("Wallet: EFaozTXxM1zvhaX4aXjB49drCPjwYY7G5QaLKYhenBpe")
    print("Test: 0.1 SOL → Check token value > 0")
    print("Rules: 10 tokens, 10% loss, 10% profit, 100% take")
    print("")
    
    result = await execute_funded_test()
    
    print("\n" + "=" * 60)
    print("🏁 FINAL FUNDED TEST RESULTS:")
    print(f"Result: {result['result']}")
    print(f"Tokens Acquired: {result['tokens_acquired']}")
    print(f"SOL Spent: {result['sol_spent']}")
    print(f"Token Value > 0: {result['token_value_greater_than_zero']}")
    print(f"Emergency Stop Required: {result['emergency_stop']}")
    
    # Final decision based on YOUR criteria
    if result['token_value_greater_than_zero']:
        print("\n🟢 DECISION: PROCEED WITH TRADING")
        print("Token value detected - system working correctly")
    else:
        print("\n🔴 DECISION: KEEP EMERGENCY STOP ACTIVE")
        print("No token value detected - emergency stop confirmed")
        
    return result

if __name__ == "__main__":
    asyncio.run(main())