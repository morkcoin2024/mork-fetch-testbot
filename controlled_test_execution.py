#!/usr/bin/env python3
"""
Controlled Test Execution for Whale Token
Testing different approaches to understand token delivery failures
"""
import requests
import json
import logging
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig

def test_whale_token_approaches():
    """Test multiple approaches with Whale token to identify working method"""
    
    whale_mint = "G4irCda4dFsePvSrhc1H1u9uZUR2TSUiUCsHm661pump"
    
    print("🐋 TESTING WHALE TOKEN - CONTROLLED EXECUTION")
    print("=" * 60)
    print(f"Token: It's just a whale")
    print(f"Contract: {whale_mint}")
    print(f"Market Cap: $11.6K")
    print(f"Age: 28 minutes")
    print()
    
    try:
        # Load test wallet
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.read().strip().split('\n')
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"Wallet: {public_key}")
        print()
        
        # Test 1: Small amount using EXACT CLIPPY parameters (what worked)
        print("TEST 1: Using exact CLIPPY parameters")
        print("-" * 40)
        
        result1 = test_pumpportal_trade(
            public_key=public_key,
            private_key=private_key,
            token_mint=whale_mint,
            amount=100,  # Very small amount
            denominated_in_sol="false",
            slippage=10,
            priority_fee=0.005,
            pool="auto"
        )
        
        print(f"Result 1: {result1}")
        print()
        
        # Test 2: SOL-denominated approach
        print("TEST 2: Using SOL-denominated approach")
        print("-" * 40)
        
        result2 = test_pumpportal_trade(
            public_key=public_key,
            private_key=private_key,
            token_mint=whale_mint,
            amount=0.001,  # 0.001 SOL
            denominated_in_sol="true",
            slippage=15,
            priority_fee=0.01,
            pool="pump"
        )
        
        print(f"Result 2: {result2}")
        print()
        
        # Test 3: Higher slippage for newer token
        print("TEST 3: Higher slippage for newer token")
        print("-" * 40)
        
        result3 = test_pumpportal_trade(
            public_key=public_key,
            private_key=private_key,
            token_mint=whale_mint,
            amount=50,
            denominated_in_sol="false",
            slippage=25,  # Higher slippage
            priority_fee=0.02,  # Higher priority fee
            pool="pump"
        )
        
        print(f"Result 3: {result3}")
        
        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        working_tests = []
        if result1.get('success'): working_tests.append("Test 1 (CLIPPY params)")
        if result2.get('success'): working_tests.append("Test 2 (SOL-denominated)")
        if result3.get('success'): working_tests.append("Test 3 (High slippage)")
        
        if working_tests:
            print(f"✅ WORKING METHODS: {', '.join(working_tests)}")
        else:
            print("❌ ALL TESTS FAILED - Systematic issue confirmed")
            
    except Exception as e:
        print(f"❌ Testing failed: {e}")

def test_pumpportal_trade(public_key, private_key, token_mint, amount, denominated_in_sol, slippage, priority_fee, pool):
    """Test single PumpPortal trade with specific parameters"""
    try:
        # Step 1: Get transaction from PumpPortal
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local", 
            data={
                "publicKey": public_key,
                "action": "buy",
                "mint": token_mint,
                "amount": amount,
                "denominatedInSol": denominated_in_sol,
                "slippage": slippage,
                "priorityFee": priority_fee,
                "pool": pool
            }
        )
        
        if response.status_code != 200:
            return {
                'success': False,
                'error': f"PumpPortal API failed: {response.text}",
                'stage': 'api_call'
            }
        
        print(f"✅ PumpPortal API response received")
        
        # Step 2: Sign transaction
        try:
            keypair = Keypair.from_base58_string(private_key)
        except:
            import base58
            decoded_key = base58.b58decode(private_key)
            keypair = Keypair.from_seed(decoded_key)
            
        tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [keypair])
        print(f"✅ Transaction signed")
        
        # Step 3: Broadcast (but wait to verify)
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        
        send_response = requests.post(
            url="https://api.mainnet-beta.solana.com/",
            headers={"Content-Type": "application/json"},
            data=SendVersionedTransaction(tx, config).to_json()
        )
        
        if send_response.status_code != 200:
            return {
                'success': False,
                'error': f"Broadcast failed: {send_response.text}",
                'stage': 'broadcast'
            }
        
        response_json = send_response.json()
        
        if 'result' in response_json:
            tx_hash = response_json['result']
            print(f"✅ Transaction broadcast: {tx_hash}")
            
            # Step 4: Verify token delivery
            import time
            time.sleep(10)  # Wait longer for confirmation
            
            token_delivered = verify_token_delivery(public_key, token_mint)
            
            return {
                'success': token_delivered,
                'transaction_hash': tx_hash,
                'tokens_verified': token_delivered,
                'explorer_url': f'https://solscan.io/tx/{tx_hash}'
            }
        else:
            error = response_json.get('error', 'Unknown error')
            return {
                'success': False,
                'error': f"Transaction failed: {error}",
                'stage': 'execution'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'stage': 'general_error'
        }

def verify_token_delivery(wallet_address, token_mint):
    """Verify if tokens were actually delivered to wallet"""
    try:
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getTokenAccountsByOwner',
            'params': [
                wallet_address,
                {'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},
                {'encoding': 'jsonParsed'}
            ]
        }

        response = requests.post('https://api.mainnet-beta.solana.com/', json=payload)
        data = response.json()

        if 'result' in data and data['result']['value']:
            accounts = data['result']['value']
            
            for account in accounts:
                parsed = account['account']['data']['parsed']
                if parsed and 'info' in parsed:
                    mint = parsed['info']['mint']
                    balance = float(parsed['info']['tokenAmount']['uiAmount'])
                    
                    if mint == token_mint and balance > 0:
                        print(f"🎯 TOKENS FOUND: {balance:,.0f} tokens in wallet")
                        return True
        
        print(f"❌ NO TOKENS FOUND for mint {token_mint}")
        return False
        
    except Exception as e:
        print(f"❌ Token verification failed: {e}")
        return False

if __name__ == "__main__":
    test_whale_token_approaches()