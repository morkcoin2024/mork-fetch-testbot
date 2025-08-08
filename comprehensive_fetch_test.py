#!/usr/bin/env python3
"""
Comprehensive test using the funded wallet with proper key format handling
"""
import requests
import base58
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def comprehensive_fetch_test():
    """Test the complete fetch process with proper error handling"""
    print("🎯 COMPREHENSIVE FETCH TEST")
    print(f"Time: {datetime.now()}")
    print("Target: Complete end-to-end trading test")
    print("=" * 60)
    
    try:
        # Read wallet info
        with open('test_wallet_info.txt', 'r') as f:
            content = f.read().strip()
            print(f"Raw wallet file content:\n{content}")
            
            lines = content.split('\n')
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"\n📍 Public Key: {public_key}")
        print(f"🔑 Private Key: {private_key}")
        print(f"📏 Private Key Length: {len(private_key)} characters")
        
        # Decode and analyze the private key
        try:
            decoded_key = base58.b58decode(private_key)
            print(f"🔓 Decoded Key Length: {len(decoded_key)} bytes")
            print(f"🔍 Key Format: {decoded_key[:8].hex()}...{decoded_key[-8:].hex()}")
            
            # Check if this is a full 64-byte keypair or 32-byte seed
            if len(decoded_key) == 32:
                print("✅ 32-byte seed format detected")
                key_type = "seed"
            elif len(decoded_key) == 64:
                print("✅ 64-byte keypair format detected")
                key_type = "keypair"
            else:
                print(f"❌ Unexpected key length: {len(decoded_key)} bytes")
                return {'success': False, 'error': 'invalid_key_length'}
                
        except Exception as e:
            print(f"❌ Key decoding failed: {e}")
            return {'success': False, 'error': f'key_decode_failed: {e}'}
        
        # Test keypair creation with proper method
        print(f"\n🔑 Testing keypair creation...")
        try:
            from solders.keypair import Keypair
            
            if key_type == "seed":
                # Use from_seed for 32-byte seeds (ChatGPT's fix)
                keypair = Keypair.from_seed(decoded_key)
                print("✅ Keypair created using from_seed (32-byte)")
            else:
                # Use from_bytes for 64-byte keypairs
                keypair = Keypair.from_bytes(decoded_key)
                print("✅ Keypair created using from_bytes (64-byte)")
            
            # Verify the keypair matches the public key
            derived_public = str(keypair.pubkey())
            if derived_public == public_key:
                print("✅ Keypair verification successful")
            else:
                print(f"❌ Public key mismatch:")
                print(f"  Expected: {public_key}")
                print(f"  Derived:  {derived_public}")
                return {'success': False, 'error': 'public_key_mismatch'}
                
        except Exception as e:
            print(f"❌ Keypair creation failed: {e}")
            return {'success': False, 'error': f'keypair_creation_failed: {e}'}
        
        # Check wallet balance
        print(f"\n💰 Checking wallet balance...")
        try:
            from solana.rpc.api import Client
            from solders.pubkey import Pubkey as PublicKey
            
            client = Client("https://api.mainnet-beta.solana.com")
            pubkey = PublicKey.from_string(public_key)
            balance_response = client.get_balance(pubkey)
            
            if balance_response.value:
                sol_balance = balance_response.value / 1_000_000_000
                print(f"✅ Current balance: {sol_balance:.6f} SOL")
                
                if sol_balance < 0.005:
                    print(f"⚠️ Insufficient balance for trading")
                    return {
                        'success': False, 
                        'error': 'insufficient_balance',
                        'balance': sol_balance,
                        'keypair_working': True
                    }
            else:
                print(f"❌ Could not fetch balance")
                return {'success': False, 'error': 'balance_check_failed'}
                
        except Exception as e:
            print(f"❌ Balance check failed: {e}")
            return {'success': False, 'error': f'balance_error: {e}'}
        
        # Test PumpPortal API with properly formatted request
        print(f"\n🚀 Testing PumpPortal API...")
        
        # Use the actual Clippy token the user provided
        clippy_token = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"
        
        # Format request exactly as in documentation
        trade_data = {
            "publicKey": public_key,
            "action": "buy",
            "mint": clippy_token,
            "amount": 0.005,  # Small amount: 0.005 SOL
            "denominatedInSol": "true",
            "slippage": 15,   # Higher slippage for better success
            "priorityFee": 0.005,
            "pool": "pump"
        }
        
        print("Request parameters:")
        for key, value in trade_data.items():
            print(f"  {key}: {value}")
        
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local",
            data=trade_data,
            timeout=30
        )
        
        print(f"\n📥 PumpPortal Response:")
        print(f"Status Code: {response.status_code}")
        print(f"Response Length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            print("🎉 SUCCESS: Transaction received from PumpPortal!")
            
            # If we got here, the API is working and we have a valid transaction
            return {
                'success': True,
                'api_working': True,
                'transaction_received': True,
                'keypair_working': True,
                'balance': sol_balance,
                'response_length': len(response.content),
                'ready_for_signing': True,
                'token_address': clippy_token
            }
        else:
            error_text = response.text
            print(f"❌ API error {response.status_code}: {error_text}")
            
            return {
                'success': False,
                'api_reachable': True,
                'error': error_text,
                'status_code': response.status_code,
                'keypair_working': True,
                'balance': sol_balance
            }
            
    except Exception as e:
        print(f"💥 General exception: {e}")
        return {'success': False, 'error': f'general: {e}'}

if __name__ == "__main__":
    result = comprehensive_fetch_test()
    
    print("\n" + "=" * 60)
    print("🏁 COMPREHENSIVE TEST RESULTS:")
    
    for key, value in result.items():
        print(f"{key}: {value}")
    
    if result.get('ready_for_signing'):
        print("\n🎉 COMPLETE SUCCESS: Ready for transaction signing!")
        print("✅ Wallet keypair working correctly")
        print("✅ PumpPortal API responding with transaction")
        print("✅ All components functional")
        print("🎯 Next: Sign and send transaction")
    elif result.get('keypair_working'):
        print("\n🟡 PARTIAL SUCCESS: Technical infrastructure working")
        print("✅ Keypair creation successful")
        if result.get('api_reachable'):
            print("✅ PumpPortal API reachable")
            print("🔧 Issue: API parameter or token validation")
        else:
            print("🔧 Issue: Network or API connectivity")
    else:
        error = result.get('error', 'unknown')
        print(f"\n🔴 TECHNICAL FAILURE: {error}")
        print("Need to debug fundamental issue")