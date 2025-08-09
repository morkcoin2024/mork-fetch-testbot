"""
Jupiter Engine - Secure Solana/Jupiter DEX Integration
Core trading engine for Mork F.E.T.C.H Bot with preflight checks and verification
"""

import requests
import json
import base64
import base58
from typing import Dict, Tuple, Optional
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address
import logging
from config import JUPITER_API_BASE, SOLANA_RPC_URL

logger = logging.getLogger(__name__)

class JupiterEngine:
    """Secure Jupiter DEX integration with preflight checks and verification"""
    
    def __init__(self):
        self.quote_api = JUPITER_API_BASE
        self.rpc_url = SOLANA_RPC_URL
        
    def get_sol_balance(self, wallet_address: str) -> float:
        """Get SOL balance for wallet address"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [wallet_address]
            }
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                lamports = result.get("result", {}).get("value", 0)
                return lamports / 1_000_000_000
            return 0.0
        except Exception as e:
            logger.error(f"Error getting SOL balance: {e}")
            return 0.0
    
    def get_token_balance(self, ata_address: str) -> int:
        """Get token balance for Associated Token Account"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountBalance",
                "params": [ata_address]
            }
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "result" in result and result["result"]["value"]:
                    return int(result["result"]["value"]["amount"])
            return 0
        except Exception as e:
            logger.debug(f"Token balance check (expected for new tokens): {e}")
            return 0
    
    def check_token_routable(self, token_mint: str, amount_sol: float) -> Tuple[bool, str]:
        """Check if token is routable via Jupiter with proper liquidity"""
        try:
            quote_params = {
                "inputMint": "So11111111111111111111111111111111111111112",  # SOL
                "outputMint": token_mint,
                "amount": str(int(amount_sol * 1_000_000_000)),
                "slippageBps": "300"
            }
            
            response = requests.get(f"{self.quote_api}/quote", params=quote_params, timeout=10)
            if response.status_code == 200:
                quote = response.json()
                if quote.get("outAmount"):
                    expected_tokens = int(quote["outAmount"])
                    return True, f"Routable - {expected_tokens:,} tokens expected"
                else:
                    return False, "No liquidity available"
            else:
                return False, f"Quote API error: {response.status_code}"
                
        except Exception as e:
            return False, f"Routing check failed: {e}"
    
    def preflight_checks(self, wallet_address: str, token_mint: str, amount_sol: float) -> Tuple[bool, str]:
        """Comprehensive preflight checks before trade execution"""
        
        # Check SOL balance
        sol_balance = self.get_sol_balance(wallet_address)
        required_sol = amount_sol + 0.01  # Trade amount + rent/fees headroom
        
        if sol_balance < required_sol:
            return False, f"Insufficient SOL: have {sol_balance:.6f}, need {required_sol:.6f}"
        
        # Check token routability
        is_routable, route_msg = self.check_token_routable(token_mint, amount_sol)
        if not is_routable:
            return False, f"Token not routable: {route_msg}"
        
        # Verify ATA requirements
        try:
            wallet_pubkey = Pubkey.from_string(wallet_address)
            token_pubkey = Pubkey.from_string(token_mint)
            ata_address = get_associated_token_address(wallet_pubkey, token_pubkey)
            logger.info(f"ATA calculated: {ata_address}")
        except Exception as e:
            return False, f"ATA calculation failed: {e}"
        
        return True, f"All checks passed - {route_msg}"
    
    def safe_swap(self, private_key_b58: str, token_mint: str, amount_sol: float, 
                  slippage_bps: int = 300) -> Dict:
        """Execute safe swap with full verification"""
        
        try:
            # Decode private key and get wallet address
            private_key_bytes = base58.b58decode(private_key_b58)
            keypair = Keypair.from_bytes(private_key_bytes)
            wallet_address = str(keypair.pubkey())
            
            logger.info(f"Starting safe swap: {amount_sol} SOL → {token_mint[:8]}...")
            
            # Preflight checks
            checks_ok, checks_msg = self.preflight_checks(wallet_address, token_mint, amount_sol)
            if not checks_ok:
                return {"success": False, "error": f"Preflight failed: {checks_msg}"}
            
            # Get pre-trade token balance
            wallet_pubkey = Pubkey.from_string(wallet_address)
            token_pubkey = Pubkey.from_string(token_mint)
            ata_address = get_associated_token_address(wallet_pubkey, token_pubkey)
            pre_balance = self.get_token_balance(str(ata_address))
            
            # Get Jupiter quote
            quote_params = {
                "inputMint": "So11111111111111111111111111111111111111112",
                "outputMint": token_mint,
                "amount": str(int(amount_sol * 1_000_000_000)),
                "slippageBps": str(slippage_bps)
            }
            
            quote_response = requests.get(f"{self.quote_api}/quote", params=quote_params, timeout=15)
            if quote_response.status_code != 200:
                return {"success": False, "error": f"Quote failed: {quote_response.status_code}"}
            
            quote_data = quote_response.json()
            expected_tokens = int(quote_data.get("outAmount", 0))
            
            # Build swap transaction
            swap_payload = {
                "quoteResponse": quote_data,
                "userPublicKey": wallet_address,
                "wrapAndUnwrapSol": True,
                "computeUnitPriceMicroLamports": 2000000,
                "dynamicComputeUnitLimit": True
            }
            
            swap_response = requests.post(
                f"{self.quote_api}/swap",
                json=swap_payload,
                headers={"Content-Type": "application/json"},
                timeout=20
            )
            
            if swap_response.status_code != 200:
                return {"success": False, "error": f"Swap build failed: {swap_response.status_code}"}
            
            swap_data = swap_response.json()
            transaction = swap_data.get("swapTransaction")
            
            # Send transaction
            rpc_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [
                    transaction,
                    {
                        "skipPreflight": False,
                        "preflightCommitment": "confirmed",
                        "encoding": "base64",
                        "maxRetries": 3
                    }
                ]
            }
            
            response = requests.post(self.rpc_url, json=rpc_payload, timeout=30)
            result = response.json()
            
            if "result" in result:
                signature = result["result"]
                
                # Wait briefly for settlement
                import time
                time.sleep(5)
                
                # Verify token delivery
                post_balance = self.get_token_balance(str(ata_address))
                delta = post_balance - pre_balance
                
                if delta > 0:
                    return {
                        "success": True,
                        "signature": signature,
                        "pre_balance": pre_balance,
                        "post_balance": post_balance,
                        "delta_raw": delta,
                        "expected_tokens": expected_tokens
                    }
                else:
                    return {
                        "success": False,
                        "error": "Trade completed but no tokens received",
                        "signature": signature,
                        "pre_balance": pre_balance,
                        "post_balance": post_balance
                    }
            else:
                error = result.get("error", "Unknown error")
                return {"success": False, "error": f"Transaction failed: {error}"}
                
        except Exception as e:
            logger.error(f"Safe swap error: {e}")
            return {"success": False, "error": f"Swap execution failed: {e}"}

# Global instance
jupiter_engine = JupiterEngine()