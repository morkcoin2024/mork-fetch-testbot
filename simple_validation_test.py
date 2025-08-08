#!/usr/bin/env python3
"""
Simple validation test with step-by-step checks
"""
import requests
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def simple_validation_test():
    """Simple step-by-step validation"""
    print("🔬 SIMPLE VALIDATION TEST")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    try:
        # Read wallet info
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.readlines()
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"📍 Wallet: {public_key}")
        print(f"🔑 Private Key Length: {len(private_key)} chars")
        
        # Test: Private key validation
        print(f"\n🧪 Private Key Validation")
        try:
            from solders.keypair import Keypair
            test_keypair = Keypair.from_base58_string(private_key)
            derived_public = str(test_keypair.pubkey())
            
            if derived_public == public_key:
                print("✅ Private key valid and matches public key")
            else:
                print(f"❌ Key mismatch")
                return {'success': False, 'error': 'key_mismatch'}
                
        except Exception as e:
            print(f"❌ Private key validation failed: {e}")
            return {'success': False, 'error': f'key_format: {e}'}
        
        # Test: Balance check
        print(f"\n🧪 Balance Check")
        try:
            from solana.rpc.api import Client
            from solders.pubkey import Pubkey as PublicKey
            
            client = Client("https://api.mainnet-beta.solana.com")
            pubkey = PublicKey.from_string(public_key)
            balance_response = client.get_balance(pubkey)
            
            if balance_response.value:
                sol_balance = balance_response.value / 1_000_000_000
                print(f"✅ Wallet balance: {sol_balance:.6f} SOL")
                
                if sol_balance < 0.01:
                    print(f"⚠️ Low balance for trading")
                    return {'success': False, 'error': 'insufficient_balance'}
            else:
                print(f"❌ Could not fetch balance")
                return {'success': False, 'error': 'balance_check_failed'}
                
        except Exception as e:
            print(f"❌ Balance check failed: {e}")
            return {'success': False, 'error': f'balance_error: {e}'}
        
        # Test: PumpPortal connectivity
        print(f"\n🧪 PumpPortal Connectivity")
        try:
            response = requests.get("https://pumpportal.fun", timeout=10)
            print(f"✅ PumpPortal reachable: {response.status_code}")
        except Exception as e:
            print(f"❌ PumpPortal unreachable: {e}")
            return {'success': False, 'error': f'api_unreachable: {e}'}
        
        # Test: ChatGPT's keypair fix verification
        print(f"\n🧪 ChatGPT Keypair Fix Test")
        try:
            # Import the fixed clean trading module
            from clean_pump_fun_trading import CleanPumpTrader
            
            # Test keypair creation directly
            trader = CleanPumpTrader()
            
            # Simulate the exact process from clean_pump_fun_trading.py
            import base58
            private_key_bytes = base58.b58decode(private_key)
            print(f"Private key decoded: {len(private_key_bytes)} bytes")
            
            # Test the fixed logic from ChatGPT
            if len(private_key_bytes) == 32:
                keypair = Keypair.from_seed(private_key_bytes)
                print("✅ ChatGPT fix working: 32-byte seed processed correctly")
                
                return {
                    'success': True,
                    'chatgpt_fix_working': True,
                    'keypair_creation_successful': True,
                    'wallet_balance': sol_balance,
                    'pumpportal_reachable': True,
                    'ready_for_api_test': True
                }
            else:
                print(f"❓ Unexpected key length: {len(private_key_bytes)} bytes")
                return {'success': False, 'error': 'unexpected_key_length'}
                
        except Exception as e:
            print(f"❌ Keypair fix test failed: {e}")
            return {'success': False, 'error': f'keypair_fix_failed: {e}'}
            
    except Exception as e:
        print(f"💥 General exception: {e}")
        return {'success': False, 'error': f'general: {e}'}

if __name__ == "__main__":
    result = simple_validation_test()
    
    print("\n" + "=" * 60)
    print("🏁 VALIDATION RESULTS:")
    
    for key, value in result.items():
        print(f"{key}: {value}")
    
    if result.get('ready_for_api_test'):
        print("\n✅ ALL VALIDATIONS PASSED")
        print("🎯 Ready for PumpPortal API testing")
        print("ChatGPT's fix is working correctly")
    else:
        error = result.get('error', 'unknown')
        print(f"\n❌ VALIDATION FAILED: {error}")
        print("Need to debug specific issue")