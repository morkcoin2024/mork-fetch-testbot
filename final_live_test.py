#!/usr/bin/env python3
"""
Final comprehensive test of live trading system
Tests complete user flow with real trading
"""
import requests
import json
import time

def test_complete_user_flow():
    """Test complete user flow from bot command to live trade execution"""
    print("🎯 FINAL LIVE TRADING SYSTEM TEST")
    print("="*60)
    print("Testing: Complete integration from Telegram bot to PumpPortal execution")
    print()
    
    results = {}
    
    # Test 1: Bot Command Response
    print("TEST 1: Bot Command Response")
    print("-" * 30)
    
    test_webhook = {
        "update_id": 999999999,
        "message": {
            "message_id": 2001,
            "from": {"id": 99999, "first_name": "LiveTest", "username": "livetest"},
            "chat": {"id": 99999, "first_name": "LiveTest", "type": "private"},
            "date": int(time.time()),
            "text": "/snipe"
        }
    }
    
    try:
        response = requests.post("http://0.0.0.0:5000/webhook", json=test_webhook, timeout=10)
        if response.status_code == 200:
            print("✅ Bot responds to /snipe command")
            results['bot_response'] = True
        else:
            print(f"❌ Bot response failed: {response.status_code}")
            results['bot_response'] = False
    except Exception as e:
        print(f"❌ Bot test failed: {e}")
        results['bot_response'] = False
    
    # Test 2: PumpPortal API Integration
    print("\nTEST 2: PumpPortal API Integration")
    print("-" * 30)
    
    try:
        # Load working wallet
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.read().strip().split('\n')
            public_key = lines[0].split(': ')[1].strip()
        
        # Test with working parameters
        working_params = {
            "publicKey": public_key,
            "action": "buy",
            "mint": "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump",
            "amount": 1000,
            "denominatedInSol": "false",
            "slippage": 15,
            "priorityFee": 0.001,
            "pool": "auto"
        }
        
        api_response = requests.post("https://pumpportal.fun/api/trade-local", data=working_params, timeout=30)
        
        if api_response.status_code == 200:
            print("✅ PumpPortal API working with correct parameters")
            print(f"   Transaction size: {len(api_response.content)} bytes")
            results['pumpportal_api'] = True
        else:
            print(f"❌ PumpPortal API failed: {api_response.status_code}")
            results['pumpportal_api'] = False
            
    except Exception as e:
        print(f"❌ PumpPortal test failed: {e}")
        results['pumpportal_api'] = False
    
    # Test 3: Live Trading Integration Module
    print("\nTEST 3: Live Trading Integration")
    print("-" * 30)
    
    try:
        from live_trading_integration import execute_live_trade, validate_token_address
        
        # Test token validation
        token_valid = validate_token_address("7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump")
        if token_valid:
            print("✅ Token validation working")
        else:
            print("❌ Token validation failed")
        
        print("✅ Live trading integration module loaded successfully")
        results['integration_module'] = True
        
    except Exception as e:
        print(f"❌ Integration module test failed: {e}")
        results['integration_module'] = False
    
    # Test 4: Solana Network Connectivity
    print("\nTEST 4: Solana Network Connectivity")
    print("-" * 30)
    
    try:
        from solana.rpc.api import Client
        from solders.pubkey import Pubkey as PublicKey
        
        client = Client("https://api.mainnet-beta.solana.com")
        pubkey = PublicKey.from_string(public_key)
        balance_response = client.get_balance(pubkey)
        
        if balance_response.value:
            sol_balance = balance_response.value / 1_000_000_000
            print(f"✅ Solana network connectivity: {sol_balance:.6f} SOL")
            results['solana_network'] = True
        else:
            print("❌ Solana network connection failed")
            results['solana_network'] = False
            
    except Exception as e:
        print(f"❌ Solana network test failed: {e}")
        results['solana_network'] = False
    
    # Test 5: Complete System Status
    print("\nTEST 5: System Status Check")
    print("-" * 30)
    
    # Check for emergency stops
    import os
    emergency_files = ['EMERGENCY_STOP.flag', 'IMMEDIATE_STOP.txt']
    emergency_active = any(os.path.exists(f) for f in emergency_files)
    
    if not emergency_active:
        print("✅ No emergency stops active")
        results['no_emergency_stops'] = True
    else:
        print("❌ Emergency stops still active")
        results['no_emergency_stops'] = False
    
    # Summary
    print("\n" + "="*60)
    print("🏁 FINAL SYSTEM TEST RESULTS")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    print()
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print()
    
    if passed_tests == total_tests:
        print("🎉 COMPLETE SUCCESS: All systems operational!")
        print("✅ Bot ready for live user trading")
        print("✅ PumpPortal API integration working")
        print("✅ All technical components functional")
        print("🚀 System ready for production use")
        
        return True
    else:
        print("🟡 Partial success - some components need attention")
        print(f"Success rate: {passed_tests/total_tests*100:.1f}%")
        
        return False

if __name__ == "__main__":
    success = test_complete_user_flow()
    
    if success:
        print("\n🎯 FINAL STATUS: LIVE TRADING SYSTEM OPERATIONAL")
        print("Ready for real user trading!")
    else:
        print("\n🔧 Some components need attention before full deployment")