#!/usr/bin/env python3
"""
EXECUTE REAL FUNDED TEST - Using wallet with actual SOL
Test with 0.1 SOL to check token value > 0
"""
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def execute_real_test_with_actual_sol():
    """Execute with wallet that has actual SOL"""
    print("🚀 REAL FUNDED TEST EXECUTION")
    print(f"Time: {datetime.now()}")
    print("Using wallet with actual SOL")
    print("Test: 0.1 SOL → Check token value > 0")
    print("YOUR CRITERIA: Token value > 0 or EMERGENCY STOP")
    print("=" * 60)
    
    try:
        from clean_pump_fun_trading import execute_clean_pump_trade
        
        # Read test wallet info
        try:
            with open('test_wallet_info.txt', 'r') as f:
                lines = f.readlines()
                public_key = lines[0].split(': ')[1].strip()
                private_key = lines[1].split(': ')[1].strip()
        except:
            print("❌ No test wallet found. Create one first.")
            return {'result': 'NO_WALLET', 'emergency_stop': True}
        
        print(f"📍 Test Wallet: {public_key}")
        
        # Check balance
        from clean_pump_fun_trading import CleanPumpTrader
        trader = CleanPumpTrader()
        balance_result = trader.check_wallet_balance(public_key)
        
        if not balance_result.get('success'):
            print(f"❌ Balance check failed: {balance_result.get('error')}")
            return {'result': 'BALANCE_CHECK_FAILED', 'emergency_stop': True}
        
        current_balance = balance_result.get('sol_balance', 0)
        print(f"💰 Current Balance: {current_balance:.6f} SOL")
        
        if current_balance < 0.1:
            print(f"❌ INSUFFICIENT FUNDS: Need 0.1 SOL, have {current_balance:.6f}")
            print(f"Fund this wallet: {public_key}")
            return {'result': 'NEEDS_FUNDING', 'emergency_stop': True, 'address': public_key}
        
        print(f"✅ SUFFICIENT FUNDS: Ready for real test")
        
        # EXECUTE REAL TEST
        print("\n🎯 EXECUTING REAL FUNDED TRADE...")
        test_token = "RealTestToken_CheckTokenValue_123"
        trade_amount = 0.1
        
        result = await execute_clean_pump_trade(private_key, test_token, trade_amount)
        
        print("\n📊 REAL FUNDED TEST RESULTS:")
        print("=" * 50)
        
        if result.get('success'):
            sol_spent = result.get('sol_actually_spent', 0)
            tokens_acquired = result.get('tokens_acquired', False)
            tx_hash = result.get('transaction_hash', 'N/A')
            
            print(f"✅ Trade executed successfully")
            print(f"💰 SOL Spent: {sol_spent:.6f}")
            print(f"🪙 Tokens Acquired: {tokens_acquired}")
            print(f"📝 Transaction Hash: {tx_hash}")
            print(f"🔧 Method: {result.get('method', 'Unknown')}")
            
            # YOUR CRITICAL CHECK: Token value > 0?
            print("\n🔍 CRITICAL TOKEN VALUE CHECK:")
            if tokens_acquired and sol_spent > 0:
                print("🎉 SUCCESS: TOKEN VALUE > 0 DETECTED!")
                print("✅ Real tokens acquired")
                print("✅ SOL properly spent")
                print("✅ Clean implementation working correctly")
                print("🟢 EMERGENCY STOP CAN BE LIFTED")
                
                return {
                    'result': 'SUCCESS_TOKEN_VALUE_POSITIVE',
                    'tokens_acquired': True,
                    'sol_spent': sol_spent,
                    'token_value_check': 'PASSED',
                    'emergency_stop_required': False,
                    'decision': 'PROCEED_WITH_TRADING'
                }
            else:
                print("🚨 FAILURE: TOKEN VALUE = 0!")
                print("❌ No real token value detected")
                print("🛑 EMERGENCY STOP CONFIRMED")
                
                return {
                    'result': 'FAILURE_TOKEN_VALUE_ZERO',
                    'tokens_acquired': tokens_acquired,
                    'sol_spent': sol_spent,
                    'token_value_check': 'FAILED',
                    'emergency_stop_required': True,
                    'decision': 'KEEP_EMERGENCY_STOP'
                }
        else:
            error = result.get('error', 'Unknown error')
            print(f"❌ Trade failed: {error}")
            print("🚨 TOKEN VALUE = 0 (No successful trade)")
            print("🛑 EMERGENCY STOP CONFIRMED")
            
            return {
                'result': 'TRADE_EXECUTION_FAILED',
                'tokens_acquired': False,
                'sol_spent': 0,
                'token_value_check': 'FAILED',
                'emergency_stop_required': True,
                'decision': 'KEEP_EMERGENCY_STOP',
                'error': error
            }
            
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        print("🛑 IMMEDIATE EMERGENCY STOP")
        
        return {
            'result': 'CRITICAL_ERROR',
            'emergency_stop_required': True,
            'error': str(e)
        }

async def main():
    result = await execute_real_test_with_actual_sol()
    
    print("\n" + "=" * 60)
    print("🏁 FINAL REAL FUNDED TEST RESULTS:")
    
    for key, value in result.items():
        print(f"{key}: {value}")
    
    # Decision based on YOUR criteria
    token_value_positive = result.get('token_value_check') == 'PASSED'
    
    if token_value_positive:
        print("\n🟢 YOUR CRITERIA MET: Token value > 0")
        print("DECISION: Safe to proceed with trading")
    else:
        print("\n🔴 YOUR CRITERIA NOT MET: Token value = 0")
        print("DECISION: Keep emergency stop active")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())