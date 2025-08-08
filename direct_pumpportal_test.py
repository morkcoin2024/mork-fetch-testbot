#!/usr/bin/env python3
"""
Direct PumpPortal API test using exact documentation format
"""
import requests
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def test_direct_pumpportal():
    """Test PumpPortal API using exact format from their documentation"""
    print("🧪 DIRECT PUMPPORTAL API TEST")
    print(f"Time: {datetime.now()}")
    print("Format: Exact documentation example")
    print("=" * 60)
    
    try:
        # Read test wallet
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.readlines()
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"📍 Wallet: {public_key}")
        
        # Use exact format from PumpPortal documentation
        clippy_token = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"
        
        # Test data exactly as shown in docs
        trade_data = {
            "publicKey": public_key,
            "action": "buy",
            "mint": clippy_token,
            "amount": 0.01,  # 0.01 SOL
            "denominatedInSol": "true",
            "slippage": 10,
            "priorityFee": 0.005,
            "pool": "pump"
        }
        
        print(f"\n📤 Request data:")
        for key, value in trade_data.items():
            print(f"  {key}: {value}")
        
        print(f"\n🔄 Making POST request to: https://pumpportal.fun/api/trade-local")
        
        # Use requests.post with data parameter as shown in docs
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local", 
            data=trade_data
        )
        
        print(f"\n📥 Response:")
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: PumpPortal API responded with 200")
            print(f"Response length: {len(response.content)} bytes")
            
            # Check if we got a transaction
            if len(response.content) > 0:
                print("🎉 BREAKTHROUGH: Received transaction data!")
                print(f"Transaction bytes: {len(response.content)}")
                
                # This indicates the API integration is working
                return {
                    'success': True,
                    'api_working': True,
                    'transaction_received': True,
                    'status_code': response.status_code,
                    'response_length': len(response.content)
                }
            else:
                print("⚠️ Empty response received")
                return {
                    'success': False,
                    'api_working': True,
                    'empty_response': True
                }
        else:
            # Get detailed error info
            try:
                error_text = response.text
            except:
                error_text = "Unable to decode error"
            
            print(f"❌ API Error {response.status_code}: {error_text}")
            
            # Check specific error codes
            if response.status_code == 400:
                print("🔍 400 Bad Request - Likely parameter issue")
                print("Common causes:")
                print("  - Invalid token address")
                print("  - Incorrect parameter format")
                print("  - Missing required field")
            elif response.status_code == 429:
                print("⏰ 429 Rate Limited - Too many requests")
            elif response.status_code == 500:
                print("🚨 500 Server Error - PumpPortal issue")
            
            return {
                'success': False,
                'status_code': response.status_code,
                'error': error_text,
                'api_reachable': True
            }
            
    except requests.RequestException as e:
        print(f"🚨 REQUEST EXCEPTION: {e}")
        return {
            'success': False,
            'network_error': True,
            'error': str(e)
        }
    except Exception as e:
        print(f"💥 GENERAL EXCEPTION: {e}")
        return {
            'success': False,
            'general_error': True,
            'error': str(e)
        }

if __name__ == "__main__":
    result = test_direct_pumpportal()
    
    print("\n" + "=" * 60)
    print("🏁 DIRECT PUMPPORTAL TEST SUMMARY:")
    
    for key, value in result.items():
        print(f"{key}: {value}")
    
    if result.get('transaction_received'):
        print("\n🎉 COMPLETE SUCCESS: PumpPortal API fully functional")
        print("✅ API integration working")
        print("✅ Transaction data received")
        print("🎯 Ready for transaction signing and sending")
    elif result.get('api_reachable'):
        print("\n🟡 PARTIAL SUCCESS: API reachable but parameter issues")
        print("✅ Network communication working")
        print("🔧 Need to debug request parameters")
    else:
        print("\n🔴 NETWORK OR CONNECTION ISSUES")
        print("Need to check connectivity or API endpoint")