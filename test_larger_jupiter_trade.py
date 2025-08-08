#!/usr/bin/env python3
"""
Test Jupiter with larger amount to verify if small trades are the issue
"""
import requests
import json
import base64
import base58
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig

def test_larger_jupiter_trade():
    """Test Jupiter with 0.002 SOL to see if larger amounts work"""
    
    print("🪐 JUPITER LARGER AMOUNT TEST")
    print("=" * 40)
    print("Testing: 0.002 SOL -> CLIPPY")
    print("Goal: Verify if larger amounts deliver tokens")
    print()
    
    try:
        # Load test wallet
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.read().strip().split('\n')
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        # Record starting token balance
        starting_balance = get_clippy_balance(public_key)
        print(f"Starting CLIPPY balance: {starting_balance:,.0f}")
        
        # Token details
        sol_mint = "So11111111111111111111111111111111111111112"
        clippy_mint = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"
        amount_lamports = 2000000  # 0.002 SOL (4x larger)
        
        print(f"Trading: {amount_lamports} lamports SOL -> CLIPPY")
        print()
        
        # Get Jupiter quote
        quote_params = {
            "inputMint": sol_mint,
            "outputMint": clippy_mint,
            "amount": amount_lamports,
            "slippageBps": 1000  # 10% slippage
        }
        
        quote_response = requests.get(
            "https://quote-api.jup.ag/v6/quote",
            params=quote_params,
            timeout=30
        )
        
        if quote_response.status_code != 200:
            print(f"❌ Quote failed: {quote_response.text}")
            return False
        
        quote_data = quote_response.json()
        expected_tokens = int(quote_data.get('outAmount', 0))
        
        print(f"Expected output: {expected_tokens:,.0f} CLIPPY")
        print(f"Price impact: {quote_data.get('priceImpactPct', 'N/A')}%")
        print()
        
        # Get swap transaction
        swap_payload = {
            "quoteResponse": quote_data,
            "userPublicKey": public_key,
            "wrapAndUnwrapSol": True,
            "computeUnitPriceMicroLamports": 2000000  # Higher priority fee
        }
        
        swap_response = requests.post(
            "https://quote-api.jup.ag/v6/swap",
            json=swap_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if swap_response.status_code != 200:
            print(f"❌ Swap failed: {swap_response.text}")
            return False
        
        swap_data = swap_response.json()
        swap_transaction = swap_data["swapTransaction"]
        
        # Sign and broadcast
        transaction_bytes = base64.b64decode(swap_transaction)
        transaction = VersionedTransaction.from_bytes(transaction_bytes)
        
        try:
            keypair = Keypair.from_base58_string(private_key)
        except:
            decoded_key = base58.b58decode(private_key)
            keypair = Keypair.from_seed(decoded_key)
        
        signed_tx = VersionedTransaction(transaction.message, [keypair])
        
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        
        send_response = requests.post(
            url="https://api.mainnet-beta.solana.com/",
            headers={"Content-Type": "application/json"},
            data=SendVersionedTransaction(signed_tx, config).to_json(),
            timeout=30
        )
        
        if send_response.status_code != 200:
            print(f"❌ Broadcast failed: {send_response.text}")
            return False
        
        response_json = send_response.json()
        
        if 'result' in response_json:
            tx_hash = response_json['result']
            print(f"✅ Transaction broadcast: {tx_hash}")
            print(f"🔗 Explorer: https://solscan.io/tx/{tx_hash}")
            print()
            
            # Wait and verify
            import time
            print("Waiting 20 seconds for confirmation...")
            time.sleep(20)
            
            ending_balance = get_clippy_balance(public_key)
            token_change = ending_balance - starting_balance
            
            print(f"Ending CLIPPY balance: {ending_balance:,.0f}")
            print(f"Token change: {token_change:+,.0f}")
            
            if token_change > 0:
                print(f"🎯 SUCCESS: {token_change:,.0f} new CLIPPY tokens received!")
                print(f"✅ Jupiter works with larger amounts")
                return True
            else:
                print(f"❌ FAILED: No new tokens received")
                print(f"Same issue as small amounts")
                return False
                
        else:
            error = response_json.get('error', 'Unknown error')
            print(f"❌ Transaction failed: {error}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def get_clippy_balance(wallet_address):
    """Get current CLIPPY token balance"""
    try:
        clippy_mint = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"
        
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
                    
                    if mint == clippy_mint:
                        return balance
        
        return 0
        
    except Exception:
        return 0

if __name__ == "__main__":
    test_larger_jupiter_trade()