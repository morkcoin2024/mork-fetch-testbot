"""
jupiter_engine.py - Safe Jupiter Swap Module
Handles all SOL->Token swaps with comprehensive safety checks
"""
import os
import json
import time
import base64
import base58
import logging
from decimal import Decimal

import requests
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from spl.token.instructions import get_associated_token_address

logger = logging.getLogger(__name__)

SOL_MINT = "So11111111111111111111111111111111111111112"
JUPITER_API_BASE = "https://quote-api.jup.ag/v6"
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

def safe_swap_via_jupiter(
    private_key_b58: str,
    output_mint_str: str,
    amount_in_sol: float,
    slippage_bps: int = 150,
    min_post_delta_raw: int = 1
) -> dict:
    """
    Execute a safe SOL->Token swap via Jupiter
    
    Returns:
    {
        "success": bool,
        "signature": str (if successful),
        "delta_raw": int (tokens received),
        "error": str (if failed),
        "pre_balance": int,
        "post_balance": int
    }
    """
    try:
        logger.info(f"🪐 JUPITER SAFE SWAP: {amount_in_sol} SOL -> {output_mint_str[:8]}...")
        
        # 1. Validate inputs
        if amount_in_sol <= 0:
            return {"success": False, "error": "Invalid SOL amount"}
            
        # 2. Setup keypair
        try:
            keypair = Keypair.from_base58_string(private_key_b58)
            wallet_pubkey = keypair.pubkey()
        except Exception as e:
            return {"success": False, "error": f"Invalid private key: {e}"}
            
        logger.info(f"Wallet: {str(wallet_pubkey)}")
        
        # 3. Check SOL balance and rent headroom
        sol_balance = _get_sol_balance(str(wallet_pubkey))
        required_sol = amount_in_sol + 0.01  # Include rent + fees
        
        if sol_balance < required_sol:
            return {
                "success": False, 
                "error": f"Insufficient SOL: {sol_balance:.6f} < {required_sol:.6f} (includes 0.01 rent headroom)"
            }
            
        logger.info(f"✅ SOL Balance: {sol_balance:.6f}")
        
        # 4. Get token balance BEFORE trade
        token_mint = Pubkey.from_string(output_mint_str)
        ata_address = get_associated_token_address(wallet_pubkey, token_mint)
        pre_balance = _get_token_balance(str(ata_address))
        
        logger.info(f"Pre-trade token balance: {pre_balance}")
        
        # 5. Get Jupiter quote
        amount_lamports = int(amount_in_sol * 1_000_000_000)
        quote_params = {
            "inputMint": SOL_MINT,
            "outputMint": output_mint_str,
            "amount": str(amount_lamports),
            "slippageBps": str(slippage_bps),
            "onlyDirectRoutes": "false"
        }
        
        quote_response = requests.get(f"{JUPITER_API_BASE}/quote", params=quote_params, timeout=20)
        if quote_response.status_code != 200:
            return {"success": False, "error": f"Quote failed: {quote_response.text}"}
            
        quote_data = quote_response.json()
        if not quote_data or "outAmount" not in quote_data:
            return {"success": False, "error": "No valid quote - token may not be bonded/routable"}
            
        expected_tokens = int(quote_data["outAmount"])
        logger.info(f"Expected tokens: {expected_tokens:,}")
        
        # 6. Build swap transaction
        swap_payload = {
            "quoteResponse": quote_data,
            "userPublicKey": str(wallet_pubkey),
            "wrapAndUnwrapSol": True,
            "useSharedAccounts": True,
            "computeUnitPriceMicroLamports": 2000000  # Priority fee
        }
        
        swap_response = requests.post(
            f"{JUPITER_API_BASE}/swap",
            json=swap_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if swap_response.status_code != 200:
            return {"success": False, "error": f"Swap build failed: {swap_response.text}"}
            
        swap_data = swap_response.json()
        swap_transaction = swap_data.get("swapTransaction")
        
        if not swap_transaction:
            return {"success": False, "error": "No swap transaction returned"}
            
        # 7. Send transaction
        send_payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'sendTransaction',
            'params': [
                swap_transaction,
                {
                    'skipPreflight': False,  # Enable preflight for safety
                    'preflightCommitment': 'confirmed',
                    'encoding': 'base64',
                    'maxRetries': 3
                }
            ]
        }
        
        send_response = requests.post(RPC_URL, json=send_payload, timeout=30)
        send_data = send_response.json()
        
        if 'result' in send_data:
            signature = send_data['result']
            logger.info(f"Transaction broadcast: {signature}")
        else:
            error = send_data.get('error', {})
            return {"success": False, "error": f"Transaction failed: {error}"}
            
        # 8. Wait for confirmation and verify token delivery
        logger.info("Waiting for confirmation...")
        time.sleep(10)
        
        # Check token balance after trade (with retries)
        for attempt in range(3):
            time.sleep(5)
            post_balance = _get_token_balance(str(ata_address))
            delta = post_balance - pre_balance
            
            logger.info(f"Post-trade balance: {post_balance}, Delta: {delta}")
            
            if delta >= min_post_delta_raw:
                return {
                    "success": True,
                    "signature": signature,
                    "delta_raw": delta,
                    "pre_balance": pre_balance,
                    "post_balance": post_balance,
                    "expected_tokens": expected_tokens
                }
                
        # If we get here, no tokens were delivered
        return {
            "success": False,
            "signature": signature,
            "error": f"Transaction confirmed but zero tokens delivered. Check: https://solscan.io/tx/{signature}",
            "pre_balance": pre_balance,
            "post_balance": post_balance,
            "delta_raw": 0
        }
        
    except Exception as e:
        logger.exception(f"Jupiter swap failed: {e}")
        return {"success": False, "error": f"Swap error: {e}"}

def _get_sol_balance(pubkey: str) -> float:
    """Get SOL balance for wallet"""
    try:
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getBalance',
            'params': [pubkey]
        }
        response = requests.post(RPC_URL, json=payload, timeout=10)
        data = response.json()
        return data['result']['value'] / 1_000_000_000
    except:
        return 0.0

def _get_token_balance(ata_address: str) -> int:
    """Get token balance from ATA"""
    try:
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getTokenAccountBalance',
            'params': [ata_address]
        }
        response = requests.post(RPC_URL, json=payload, timeout=10)
        data = response.json()
        
        if 'result' in data and data['result']['value']:
            return int(data['result']['value']['amount'])
        return 0
    except:
        return 0