#!/usr/bin/env python3
"""
Debug PumpPortal API based on official documentation
"""
import requests
import base58
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def debug_pumpportal_api():
    """Debug PumpPortal API with exact documentation requirements"""
    print("🔍 PUMPPORTAL API DEBUG")
    print(f"Time: {datetime.now()}")
    print("Goal: Identify exact API requirements")
    print("=" * 60)
    
    try:
        # Load wallet
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.read().strip().split('\n')
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"Wallet: {public_key}")
        
        # Test various API configurations based on documentation
        test_configs = [
            {
                "name": "Exact Doc Format (denominatedInSol false)",
                "data": {
                    "publicKey": public_key,
                    "action": "buy",
                    "mint": "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump",
                    "amount": 100000,  # amount of tokens like in docs
                    "denominatedInSol": "false",  # false like in docs
                    "slippage": 10,
                    "priorityFee": 0.005,
                    "pool": "auto"
                }
            },
            {
                "name": "SOL Denominated Small Amount",
                "data": {
                    "publicKey": public_key,
                    "action": "buy",
                    "mint": "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump",
                    "amount": 0.001,  # very small SOL amount
                    "denominatedInSol": "true",
                    "slippage": 20,
                    "priorityFee": 0.001,
                    "pool": "pump"
                }
            },
            {
                "name": "All String Values",
                "data": {
                    "publicKey": public_key,
                    "action": "buy",
                    "mint": "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump",
                    "amount": "0.001",
                    "denominatedInSol": "true",
                    "slippage": "20",
                    "priorityFee": "0.001",
                    "pool": "pump"
                }
            },
            {
                "name": "Minimal Required Fields",
                "data": {
                    "publicKey": public_key,
                    "action": "buy",
                    "mint": "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump",
                    "amount": 0.001,
                    "denominatedInSol": "true",
                    "slippage": 15,
                    "priorityFee": 0.005
                    # pool is optional, omitting it
                }
            }
        ]
        
        for i, config in enumerate(test_configs, 1):
            print(f"\n🧪 Test {i}: {config['name']}")
            print("Parameters:")
            for key, value in config['data'].items():
                print(f"  {key}: {value} ({type(value).__name__})")
            
            try:
                response = requests.post(
                    url="https://pumpportal.fun/api/trade-local",
                    data=config['data'],
                    timeout=30
                )
                
                print(f"Status: {response.status_code}")
                print(f"Headers: {dict(response.headers)}")
                print(f"Response length: {len(response.content)} bytes")
                
                if response.status_code == 200:
                    print(f"✅ SUCCESS with {config['name']}!")
                    print("This configuration works!")
                    
                    # Validate response contains transaction
                    if len(response.content) > 100:  # Basic check for transaction data
                        print("✅ Transaction data received")
                        
                        return {
                            'success': True,
                            'working_config': config,
                            'transaction_length': len(response.content),
                            'ready_for_execution': True
                        }
                    else:
                        print("⚠️ Response too short for transaction")
                else:
                    error_text = response.text
                    print(f"❌ Error: {error_text}")
                    
                    # Analyze specific errors
                    if "invalid" in error_text.lower():
                        print("Hint: Parameter validation issue")
                    elif "token" in error_text.lower():
                        print("Hint: Token address issue")
                    elif "balance" in error_text.lower():
                        print("Hint: Insufficient balance")
                    
            except Exception as e:
                print(f"❌ Request exception: {e}")
        
        # Test with different token if Clippy fails
        print(f"\n🧪 Testing with different token (known working)...")
        
        # Try with a well-known token that should work
        test_with_different_token = {
            "publicKey": public_key,
            "action": "buy", 
            "mint": "So11111111111111111111111111111111111111112",  # SOL itself
            "amount": 0.001,
            "denominatedInSol": "true",
            "slippage": 10,
            "priorityFee": 0.001,
            "pool": "auto"
        }
        
        try:
            response = requests.post(
                url="https://pumpportal.fun/api/trade-local",
                data=test_with_different_token,
                timeout=30
            )
            
            print(f"Different token test - Status: {response.status_code}")
            print(f"Response: {response.text[:100]}")
            
            if response.status_code == 200:
                print("✅ API works with different token - Clippy token might be the issue")
                return {
                    'success': False,
                    'clippy_token_issue': True,
                    'api_functional': True,
                    'working_token': "So11111111111111111111111111111111111111112"
                }
            
        except Exception as e:
            print(f"Different token test failed: {e}")
        
        return {
            'success': False,
            'all_tests_failed': True,
            'api_reachable': True,
            'issue': 'parameter_validation_or_token_specific'
        }
        
    except Exception as e:
        print(f"Debug failed: {e}")
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    result = debug_pumpportal_api()
    
    print("\n" + "=" * 60)
    print("🏁 PUMPPORTAL API DEBUG RESULTS:")
    
    for key, value in result.items():
        if key not in ['working_config', 'transaction_data']:
            print(f"{key}: {value}")
    
    if result.get('ready_for_execution'):
        print("\n🎉 PumpPortal API working! Found correct parameters.")
        print("Ready to execute real transaction.")
    elif result.get('api_functional'):
        print("\n🟡 API functional but token-specific issue.")
        print("Need to find valid pump.fun token address.")
    else:
        print("\n🔧 Continue systematic debugging.")
        print("Check wallet balance, token validity, or parameter format.")