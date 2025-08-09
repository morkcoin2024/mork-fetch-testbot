"""
jupiter_engine.py — Safe Jupiter swap module (ChatGPT recommended)
Replaces the broken Jupiter integration with reliable transaction handling
"""
import os
import json
import time
import base64
import base58
import logging
from decimal import Decimal

import requests

# Use the existing solders imports that are already working in the project
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.rpc.requests import GetBalance, SendRawTransaction, GetTokenAccountBalance
from solders.rpc.config import RpcSendTransactionConfig
from solders.commitment_config import CommitmentLevel
from spl.token.instructions import get_associated_token_address

logger = logging.getLogger(__name__)

SOL_MINT = "So11111111111111111111111111111111111111112"
JUP_BASE = os.getenv("JUPITER_BASE", "https://quote-api.jup.ag/v6")

def safe_swap_via_jupiter(
    private_key_b58: str,
    output_mint_str: str,
    amount_in_sol: float,
    slippage_bps: int = 150,
    min_post_delta_raw: int = 1
) -> dict:
    """
    Reliable Jupiter swap with proper error handling and verification
    Returns dict with success, signature, delta_raw, error fields
    """
    try:
        print(f"🪐 SAFE JUPITER SWAP")
        print(f"Token: {output_mint_str[:8]}...{output_mint_str[-8:]}")
        print(f"Amount: {amount_in_sol} SOL")
        
        # Initialize RPC connection
        rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        
        # Reconstruct keypair from base58 private key
        try:
            keypair = Keypair.from_base58_string(private_key_b58)
            owner_pubkey = keypair.pubkey()
        except Exception as e:
            return {"success": False, "error": f"Invalid private key: {e}"}
        
        print(f"1. Wallet: {str(owner_pubkey)}")
        
        # Check SOL balance using direct RPC
        balance_payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getBalance',
            'params': [str(owner_pubkey)]
        }
        balance_response = requests.post(rpc_url, json=balance_payload)
        sol_balance = balance_response.json()['result']['value'] / 1_000_000_000
        
        if sol_balance < amount_in_sol + 0.01:  # Include fees
            return {"success": False, "error": f"Insufficient SOL: {sol_balance:.4f} < {amount_in_sol + 0.01:.4f}"}
        
        print(f"✅ SOL Balance: {sol_balance:.6f}")
        
        # Get token balance BEFORE trade
        try:
            token_mint = Pubkey.from_string(output_mint_str)
            ata = get_associated_token_address(owner_pubkey, token_mint)
            
            # Get token balance using direct RPC
            token_balance_payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'getTokenAccountBalance',
                'params': [str(ata)]
            }
            
            try:
                token_response = requests.post(rpc_url, json=token_balance_payload)
                token_data = token_response.json()
                before_amount = int(token_data['result']['value']['amount']) if 'result' in token_data and token_data['result']['value'] else 0
            except:
                before_amount = 0
                
            print(f"2. Token balance before: {before_amount}")
            
        except Exception as e:
            return {"success": False, "error": f"Token account setup failed: {e}"}
        
        # Get Jupiter quote
        print("3. Getting Jupiter quote...")
        amount_lamports = int(amount_in_sol * 1_000_000_000)
        
        params = {
            "inputMint": SOL_MINT,
            "outputMint": output_mint_str,
            "amount": str(amount_lamports),
            "slippageBps": str(slippage_bps),
            "onlyDirectRoutes": "false",
            "asLegacyTransaction": "false"
        }
        
        quote_response = requests.get(f"{JUP_BASE}/quote", params=params, timeout=20)
        if quote_response.status_code != 200:
            return {"success": False, "error": f"Quote failed: {quote_response.text}"}
        
        quote_data = quote_response.json()
        if not quote_data or "outAmount" not in quote_data:
            return {"success": False, "error": "No valid quote received"}
        
        expected_tokens = int(quote_data["outAmount"])
        print(f"✅ Expected tokens: {expected_tokens:,}")
        
        # Build swap transaction
        print("4. Building swap transaction...")
        headers = {"Content-Type": "application/json"}
        swap_payload = {
            "quoteResponse": quote_data,
            "userPublicKey": str(owner_pubkey),
            "wrapAndUnwrapSol": True,
            "useSharedAccounts": True,
            "asLegacyTransaction": False
        }
        
        swap_response = requests.post(
            f"{JUP_BASE}/swap",
            headers=headers,
            data=json.dumps(swap_payload),
            timeout=30
        )
        
        if swap_response.status_code != 200:
            return {"success": False, "error": f"Swap build failed: {swap_response.text}"}
        
        swap_data = swap_response.json()
        swap_transaction = swap_data.get("swapTransaction")
        
        if not swap_transaction:
            return {"success": False, "error": "No swap transaction returned"}
        
        print("✅ Swap transaction built")
        
        # Send transaction using correct RPC format  
        print("5. Broadcasting transaction...")
        try:
            # Use the correct sendTransaction RPC method format
            send_payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'sendTransaction',
                'params': [
                    swap_transaction,
                    {
                        'skipPreflight': True,
                        'preflightCommitment': 'confirmed',
                        'encoding': 'base64'
                    }
                ]
            }
            
            send_response = requests.post(rpc_url, json=send_payload, timeout=30)
            send_data = send_response.json()
            
            if 'result' in send_data:
                signature = send_data['result']
                
                # CRITICAL CHECK: Detect fake transaction hashes
                if signature == "1111111111111111111111111111111111111111111111111111111111111111" or len(set(signature)) <= 2:
                    print(f"🚨 FAKE TRANSACTION HASH DETECTED: {signature}")
                    return {"success": False, "error": f"EMERGENCY STOP: Fake transaction hash detected. System is generating false success reports instead of real blockchain transactions."}
                
                print(f"✅ Transaction broadcast: {signature}")
            else:
                error_msg = send_data.get('error', {})
                return {"success": False, "error": f"Transaction broadcast failed: {error_msg}"}
            
        except Exception as e:
            return {"success": False, "error": f"Transaction broadcast failed: {e}"}
        
        # Verify token delivery with retry logic
        print("6. Verifying token delivery...")
        for attempt in range(3):
            time.sleep(5 if attempt == 0 else 10)
            try:
                # Check token balance again using direct RPC
                token_response = requests.post(rpc_url, json=token_balance_payload)
                token_data = token_response.json()
                after_amount = int(token_data['result']['value']['amount']) if 'result' in token_data and token_data['result']['value'] else 0
                
                delta = after_amount - before_amount
                print(f"Token balance after: {after_amount}")
                print(f"Delta: {delta}")
                
                if delta >= min_post_delta_raw:
                    print(f"✅ SWAP SUCCESS - {delta:,} tokens delivered")
                    return {
                        "success": True,
                        "signature": signature,
                        "delta_raw": delta,
                        "expected_tokens": expected_tokens,
                        "actual_tokens": delta
                    }
                    
            except Exception as e:
                print(f"Verification attempt {attempt + 1} failed: {e}")
                continue
        
        # If we get here, token delivery verification failed
        print("🚨 EMERGENCY FAILSAFE TRIGGERED - ZERO TOKEN DELIVERY")
        print(f"Expected: {expected_tokens:,} tokens")
        print(f"Received: 0 tokens")
        print("This indicates the transaction may be fake or failed")
        
        return {
            "success": False,
            "signature": signature,
            "error": f"EMERGENCY FAILSAFE: Zero tokens delivered despite 'successful' transaction. This suggests fake transaction reporting. Trading halted for user protection.",
            "emergency_stop": True
        }
        
    except Exception as e:
        logger.exception(f"Jupiter swap failed: {e}")
        return {"success": False, "error": f"Swap error: {e}"}