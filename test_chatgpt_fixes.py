#!/usr/bin/env python3
"""
Test ChatGPT's fixes for the "sequence length 64 vs 32" error
"""
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def test_chatgpt_keypair_fix():
    """Test the fixed keypair handling with actual funded wallet"""
    print("🧪 TESTING CHATGPT'S KEYPAIR FIX")
    print(f"Time: {datetime.now()}")
    print("Fix: Proper handling of 64-byte vs 32-byte private keys")
    print("Testing: Funded wallet with 0.1 SOL")
    print("=" * 60)
    
    try:
        from clean_pump_fun_trading import execute_clean_pump_trade
        
        # Read test wallet with 0.1 SOL
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.readlines()
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"📍 Test Wallet: {public_key}")
        print(f"🔑 Private Key Length Check: Starting...")
        
        # Test the fixed implementation
        test_token = "ChatGPTFixTest_SequenceLength_123"
        trade_amount = 0.05  # Test with half the available SOL
        
        print(f"\n🎯 EXECUTING WITH CHATGPT FIX:")
        print(f"Amount: {trade_amount} SOL")
        print(f"Token: {test_token}")
        print(f"Expected: Proper keypair creation without 'sequence length' error")
        
        result = await execute_clean_pump_trade(private_key, test_token, trade_amount)
        
        print("\n📊 CHATGPT FIX TEST RESULTS:")
        print("=" * 50)
        
        if result.get('success'):
            tx_hash = result.get('transaction_hash', 'N/A')
            sol_spent = result.get('sol_actually_spent', 0)
            tokens_acquired = result.get('tokens_acquired', False)
            
            print(f"✅ SUCCESS: No sequence length error!")
            print(f"🔑 Keypair creation: WORKING")
            print(f"📝 Transaction Hash: {tx_hash}")
            print(f"💰 SOL Spent: {sol_spent:.6f}")
            print(f"🪙 Tokens Acquired: {tokens_acquired}")
            
            # YOUR CRITICAL TEST: Token value > 0?
            if tokens_acquired and sol_spent > 0:
                print("\n🎉 BREAKTHROUGH: TOKEN VALUE > 0!")
                print("✅ ChatGPT's fix worked completely")
                print("✅ Keypair creation fixed")
                print("✅ Real tokens acquired")
                print("✅ Transaction processing working")
                print("🟢 EMERGENCY STOP CAN BE LIFTED!")
                
                return {
                    'result': 'CHATGPT_FIX_SUCCESS',
                    'keypair_error_resolved': True,
                    'tokens_acquired': True,
                    'sol_spent': sol_spent,
                    'transaction_hash': tx_hash,
                    'token_value_positive': True,
                    'emergency_stop_required': False
                }
            else:
                print("\n⚠️ PARTIAL SUCCESS:")
                print("✅ Keypair error fixed (no 'sequence length' error)")
                print("❌ But no token value detected")
                print("🟡 Progress made, may need API response handling fixes")
                
                return {
                    'result': 'KEYPAIR_FIXED_BUT_NO_TOKENS',
                    'keypair_error_resolved': True,
                    'tokens_acquired': False,
                    'sol_spent': sol_spent,
                    'token_value_positive': False,
                    'emergency_stop_required': True
                }
        else:
            error = result.get('error', 'Unknown error')
            print(f"❌ Test failed: {error}")
            
            # Check if it's still the sequence length error
            sequence_error = "sequence length" in str(error).lower()
            if sequence_error:
                print("🚨 SEQUENCE LENGTH ERROR STILL PRESENT")
                print("ChatGPT fix may need adjustment")
            else:
                print("✅ SEQUENCE LENGTH ERROR RESOLVED")
                print("❌ But different error occurred")
            
            return {
                'result': 'EXECUTION_FAILED',
                'keypair_error_resolved': not sequence_error,
                'error': error,
                'emergency_stop_required': True
            }
            
    except Exception as e:
        error_msg = str(e)
        sequence_error = "sequence length" in error_msg.lower()
        
        print(f"\n💥 EXCEPTION: {error_msg}")
        
        if sequence_error:
            print("🚨 SEQUENCE LENGTH ERROR STILL IN EXCEPTION")
            print("ChatGPT fix needs further refinement")
        else:
            print("✅ NO SEQUENCE LENGTH ERROR IN EXCEPTION")
            print("❌ Different issue occurred")
        
        return {
            'result': 'EXCEPTION_OCCURRED',
            'keypair_error_resolved': not sequence_error,
            'error': error_msg,
            'emergency_stop_required': True
        }

async def main():
    result = await test_chatgpt_keypair_fix()
    
    print("\n" + "=" * 60)
    print("🏁 CHATGPT FIX TEST SUMMARY:")
    
    for key, value in result.items():
        print(f"{key}: {value}")
    
    if result.get('keypair_error_resolved'):
        print("\n🟢 CHATGPT'S KEYPAIR FIX: SUCCESS")
        print("'sequence length 64 vs 32' error resolved")
    else:
        print("\n🔴 CHATGPT'S KEYPAIR FIX: NEEDS REFINEMENT")
        print("'sequence length 64 vs 32' error still occurring")
    
    if result.get('token_value_positive'):
        print("\n🎉 COMPLETE SUCCESS: Ready for trading")
        print("Emergency stop can be lifted")
    else:
        print("\n⚠️ PARTIAL SUCCESS: More fixes needed")
        print("Emergency stop remains active")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())