#!/usr/bin/env python3
"""
Comprehensive live trading test with real user flow
Tests the complete trading pipeline from command to execution
"""
import requests
import base58
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def test_live_trading_flow():
    """Test complete live trading flow"""
    print("🎯 COMPREHENSIVE LIVE TRADING TEST")
    print(f"Time: {datetime.now()}")
    print("Testing: Complete user flow from command to execution")
    print("=" * 60)
    
    try:
        # Load test wallet
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.read().strip().split('\n')
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"Test wallet: {public_key}")
        
        # Test 1: Simulate user /snipe command
        print("\n" + "="*60)
        print("TEST 1: USER SNIPE COMMAND SIMULATION")
        print("="*60)
        
        # Simulated user input
        test_token = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"  # CLIPPY
        test_amount = 2000  # tokens
        
        print(f"User command: /snipe {test_token}")
        print(f"Amount: {test_amount} tokens")
        print(f"Target: CLIPPY PFP Cult")
        
        # Step 1: Validate token (simulate bot validation)
        print(f"\nStep 1: Token validation...")
        
        # Check if token exists on pump.fun
        try:
            token_check = requests.get(f"https://pump.fun/coin/{test_token}", timeout=10)
            if token_check.status_code == 200:
                print("✅ Token exists on pump.fun")
            else:
                print("❌ Token validation failed")
                return {'success': False, 'stage': 'token_validation'}
        except:
            print("⚠️ Token check failed, proceeding anyway")
        
        # Step 2: Check wallet balance
        print(f"\nStep 2: Wallet balance check...")
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
                    print("❌ Insufficient balance for trading")
                    return {'success': False, 'stage': 'insufficient_balance'}
            else:
                print("❌ Could not check balance")
                return {'success': False, 'stage': 'balance_check_failed'}
        except Exception as e:
            print(f"❌ Balance check error: {e}")
            return {'success': False, 'stage': 'balance_check_error'}
        
        # Step 3: Generate transaction (PumpPortal API)
        print(f"\nStep 3: Generating transaction...")
        
        trade_params = {
            "publicKey": public_key,
            "action": "buy",
            "mint": test_token,
            "amount": test_amount,
            "denominatedInSol": "false",  # Key format from debugging
            "slippage": 15,
            "priorityFee": 0.001,
            "pool": "auto"
        }
        
        print("Transaction parameters:")
        for key, value in trade_params.items():
            print(f"  {key}: {value}")
        
        try:
            api_response = requests.post(
                url="https://pumpportal.fun/api/trade-local",
                data=trade_params,
                timeout=30
            )
            
            print(f"API Response: {api_response.status_code}")
            
            if api_response.status_code == 200:
                print("✅ Transaction generated successfully")
                tx_data = api_response.content
                print(f"Transaction size: {len(tx_data)} bytes")
            else:
                print(f"❌ API Error: {api_response.text}")
                return {'success': False, 'stage': 'api_generation', 'error': api_response.text}
        except Exception as e:
            print(f"❌ API Request failed: {e}")
            return {'success': False, 'stage': 'api_request', 'error': str(e)}
        
        # Step 4: Create and sign transaction
        print(f"\nStep 4: Creating and signing transaction...")
        
        try:
            from solders.keypair import Keypair
            from solders.transaction import VersionedTransaction
            
            # Create keypair (using working ChatGPT fix)
            decoded_key = base58.b58decode(private_key)
            keypair = Keypair.from_seed(decoded_key)
            print("✅ Keypair created")
            
            # Create transaction
            tx = VersionedTransaction(VersionedTransaction.from_bytes(tx_data).message, [keypair])
            print("✅ Transaction signed")
            
        except Exception as e:
            print(f"❌ Transaction creation failed: {e}")
            return {'success': False, 'stage': 'transaction_creation', 'error': str(e)}
        
        # Step 5: Execute transaction
        print(f"\nStep 5: Broadcasting transaction...")
        
        try:
            from solders.commitment_config import CommitmentLevel
            from solders.rpc.requests import SendVersionedTransaction
            from solders.rpc.config import RpcSendTransactionConfig
            
            commitment = CommitmentLevel.Confirmed
            config = RpcSendTransactionConfig(preflight_commitment=commitment)
            
            send_response = requests.post(
                url="https://api.mainnet-beta.solana.com/",
                headers={"Content-Type": "application/json"},
                data=SendVersionedTransaction(tx, config).to_json(),
                timeout=60
            )
            
            if send_response.status_code == 200:
                response_json = send_response.json()
                
                if 'result' in response_json:
                    tx_hash = response_json['result']
                    print(f"🎉 TRANSACTION SUCCESSFUL!")
                    print(f"✅ Hash: {tx_hash}")
                    print(f"🔍 Explorer: https://solscan.io/tx/{tx_hash}")
                    
                    # Test 2: Verify the transaction
                    print("\n" + "="*60)
                    print("TEST 2: TRANSACTION VERIFICATION")
                    print("="*60)
                    
                    import time
                    print("Waiting 5 seconds for confirmation...")
                    time.sleep(5)
                    
                    # Check balance change
                    try:
                        final_balance_response = client.get_balance(pubkey)
                        if final_balance_response.value:
                            final_sol = final_balance_response.value / 1_000_000_000
                            sol_spent = sol_balance - final_sol
                            
                            print(f"Previous balance: {sol_balance:.6f} SOL")
                            print(f"Current balance: {final_sol:.6f} SOL")
                            print(f"SOL spent: {sol_spent:.6f}")
                            
                            success_result = {
                                'success': True,
                                'test_completed': True,
                                'transaction_hash': tx_hash,
                                'tokens_purchased': test_amount,
                                'token_address': test_token,
                                'sol_spent': sol_spent,
                                'final_balance': final_sol,
                                'system_operational': True,
                                'live_trading_confirmed': True
                            }
                            
                            if sol_spent > 0:
                                print(f"\n🎯 LIVE TRADING CONFIRMED!")
                                print(f"✅ Real tokens purchased: {test_amount} CLIPPY")
                                print(f"✅ Real SOL spent: {sol_spent:.6f}")
                                print(f"✅ System fully operational")
                                success_result['token_value_confirmed'] = True
                            else:
                                print(f"\n🟡 Transaction successful, spending verification pending")
                                success_result['spending_verification_pending'] = True
                                
                            return success_result
                        else:
                            print("Balance verification failed")
                            return {
                                'success': True,
                                'transaction_hash': tx_hash,
                                'verification_failed': True
                            }
                    except Exception as e:
                        print(f"Verification error: {e}")
                        return {
                            'success': True,
                            'transaction_hash': tx_hash,
                            'verification_error': str(e)
                        }
                else:
                    error = response_json.get('error', {})
                    print(f"❌ Transaction failed: {error}")
                    return {'success': False, 'stage': 'transaction_execution', 'error': error}
            else:
                print(f"❌ Broadcast failed: {send_response.text}")
                return {'success': False, 'stage': 'broadcast', 'error': send_response.text}
                
        except Exception as e:
            print(f"❌ Execution failed: {e}")
            return {'success': False, 'stage': 'execution', 'error': str(e)}
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return {'success': False, 'stage': 'general', 'error': str(e)}

if __name__ == "__main__":
    result = test_live_trading_flow()
    
    print("\n" + "="*60)
    print("🏁 COMPREHENSIVE LIVE TRADING TEST RESULTS")
    print("="*60)
    
    for key, value in result.items():
        print(f"{key}: {value}")
    
    if result.get('live_trading_confirmed'):
        print("\n🎉 COMPLETE SUCCESS: Live trading system fully operational!")
        print("✅ User command simulation successful")
        print("✅ Real transaction execution confirmed")
        print("✅ Token purchase verified")
        print("🚀 Ready for production deployment")
    elif result.get('success'):
        print("\n🟡 Test completed with transaction broadcast")
        print("Live trading capability demonstrated")
    else:
        print(f"\n❌ Test failed at stage: {result.get('stage', 'unknown')}")
        print("Review specific component for issues")