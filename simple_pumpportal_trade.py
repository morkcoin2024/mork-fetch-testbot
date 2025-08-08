#!/usr/bin/env python3
"""
Simple PumpPortal trading using exact documentation approach
Following official PumpPortal API docs exactly as shown in screenshot
"""
import requests
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
import logging

def execute_simple_pumpportal_trade(public_key, private_key, token_mint, amount_tokens):
    """
    Execute trade using EXACT PumpPortal documentation approach
    
    Args:
        public_key: Wallet public key
        private_key: Wallet private key (base58 string)
        token_mint: Token contract address
        amount_tokens: Number of tokens to buy
    
    Returns:
        dict: Result with success status and transaction hash
    """
    try:
        logging.info(f"Simple PumpPortal trade: {amount_tokens} tokens of {token_mint}")
        
        # Step 1: Get transaction from PumpPortal (EXACT docs approach)
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local", 
            data={
                "publicKey": public_key,
                "action": "buy",
                "mint": token_mint,
                "amount": amount_tokens,
                "denominatedInSol": "false",  # amount is number of tokens
                "slippage": 10,
                "priorityFee": 0.005,
                "pool": "auto"
            }
        )
        
        if response.status_code != 200:
            return {
                'success': False,
                'error': f"PumpPortal API failed: {response.text}",
                'stage': 'api_call'
            }
        
        logging.info("✅ PumpPortal transaction received")
        
        # Step 2: Sign transaction (EXACT docs approach)
        # Note: Documentation shows from_base58_string but we need to handle different key formats
        try:
            # Try documentation format first
            keypair = Keypair.from_base58_string(private_key)
        except:
            # Fallback to seed format if needed
            import base58
            decoded_key = base58.b58decode(private_key)
            keypair = Keypair.from_seed(decoded_key)
            
        tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [keypair])
        
        logging.info("✅ Transaction signed")
        
        # Step 3: Send transaction (EXACT docs approach)
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
                'error': f"Transaction send failed: {send_response.text}",
                'stage': 'send_transaction'
            }
        
        response_json = send_response.json()
        
        if 'result' in response_json:
            tx_signature = response_json['result']
            logging.info(f"✅ Transaction successful: {tx_signature}")
            
            return {
                'success': True,
                'transaction_hash': tx_signature,
                'explorer_url': f'https://solscan.io/tx/{tx_signature}',
                'tokens_amount': amount_tokens,
                'token_mint': token_mint
            }
        else:
            error = response_json.get('error', 'Unknown error')
            return {
                'success': False,
                'error': f"Transaction failed: {error}",
                'stage': 'transaction_execution'
            }
            
    except Exception as e:
        logging.error(f"Simple PumpPortal trade failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'stage': 'general_error'
        }

def test_simple_trade():
    """Test the simple PumpPortal approach"""
    print("🧪 Testing Simple PumpPortal Trade")
    print("Using exact documentation approach...")
    
    try:
        # Load test wallet
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.read().strip().split('\n')
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        # Test with CLIPPY token and small amount
        result = execute_simple_pumpportal_trade(
            public_key=public_key,
            private_key=private_key,
            token_mint="7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump",  # CLIPPY
            amount_tokens=500  # Small test amount
        )
        
        print(f"Result: {result}")
        
        if result['success']:
            print(f"✅ SUCCESS! Transaction: {result['transaction_hash']}")
            print(f"🔍 Explorer: {result['explorer_url']}")
        else:
            print(f"❌ FAILED: {result['error']}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_simple_trade()