#!/usr/bin/env python3
"""
Jupiter Trade Engine - Professional Trading Implementation
Based on ChatGPT analysis and recommendations
Replaces unreliable PumpPortal with native Solana + Jupiter hybrid
"""
import requests
import json
import base64
import base58
import time
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address

class JupiterTradeEngine:
    """Professional-grade trading engine using Jupiter aggregator"""
    
    def __init__(self, rpc_url="https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url
        self.jupiter_quote_url = "https://quote-api.jup.ag/v6/quote"
        self.jupiter_swap_url = "https://quote-api.jup.ag/v6/swap"
        self.sol_mint = "So11111111111111111111111111111111111111112"
        
    def validate_token_bonded(self, token_mint):
        """Validate that token is bonded and has liquidity"""
        try:
            # Check if token has Jupiter route (indicates bonding)
            quote_params = {
                "inputMint": self.sol_mint,
                "outputMint": token_mint,
                "amount": 1000000,  # 0.001 SOL test
                "slippageBps": 1000
            }
            
            response = requests.get(self.jupiter_quote_url, params=quote_params, timeout=10)
            
            if response.status_code == 200:
                quote_data = response.json()
                if quote_data.get('routePlan') and len(quote_data['routePlan']) > 0:
                    return True, "Token has active trading route"
                else:
                    return False, "No trading route available"
            else:
                return False, f"Quote failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def check_ata_exists(self, wallet_pubkey, token_mint):
        """Check if Associated Token Account exists"""
        try:
            wallet_key = Pubkey.from_string(wallet_pubkey)
            token_key = Pubkey.from_string(token_mint)
            ata_address = get_associated_token_address(wallet_key, token_key)
            
            # Check if ATA exists on-chain
            payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'getAccountInfo',
                'params': [str(ata_address), {'encoding': 'base64'}]
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            data = response.json()
            
            if 'result' in data and data['result']['value'] is not None:
                return True, str(ata_address)
            else:
                return False, str(ata_address)
                
        except Exception as e:
            return False, f"ATA check error: {e}"
    
    def check_sol_balance(self, wallet_pubkey):
        """Check wallet SOL balance for rent and fees"""
        try:
            payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'getBalance',
                'params': [wallet_pubkey]
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            data = response.json()
            
            if 'result' in data:
                balance_lamports = data['result']['value']
                balance_sol = balance_lamports / 1_000_000_000
                
                # Need at least 0.005 SOL for rent + fees + trade
                min_required = 0.005
                sufficient = balance_sol >= min_required
                
                return sufficient, balance_sol, min_required
            else:
                return False, 0, 0.005
                
        except Exception as e:
            return False, 0, 0.005
    
    def execute_jupiter_trade(self, wallet_pubkey, private_key, token_mint, sol_amount, slippage_bps=1000):
        """Execute trade using Jupiter aggregator with full validation"""
        
        print(f"🪐 JUPITER TRADE EXECUTION")
        print(f"Token: {token_mint[:8]}...{token_mint[-8:]}")
        print(f"Amount: {sol_amount} SOL")
        print()
        
        try:
            # Step 1: Validate token is bonded
            print("1. Validating token bonding status...")
            bonded, bond_msg = self.validate_token_bonded(token_mint)
            if not bonded:
                return {"success": False, "error": f"Token not bonded: {bond_msg}"}
            print(f"✅ {bond_msg}")
            
            # Step 2: Check SOL balance
            print("2. Checking wallet balance...")
            sufficient, balance, required = self.check_sol_balance(wallet_pubkey)
            if not sufficient:
                return {"success": False, "error": f"Insufficient SOL: {balance:.4f} < {required:.4f}"}
            print(f"✅ Balance: {balance:.4f} SOL (sufficient)")
            
            # Step 3: Check/Create ATA
            print("3. Validating Associated Token Account...")
            ata_exists, ata_address = self.check_ata_exists(wallet_pubkey, token_mint)
            if not ata_exists:
                print(f"⚠️  ATA will be created: {ata_address}")
            else:
                print(f"✅ ATA exists: {ata_address}")
            
            # Step 4: Get Jupiter quote
            print("4. Getting Jupiter quote...")
            amount_lamports = int(sol_amount * 1_000_000_000)
            
            quote_params = {
                "inputMint": self.sol_mint,
                "outputMint": token_mint,
                "amount": amount_lamports,
                "slippageBps": slippage_bps
            }
            
            quote_response = requests.get(self.jupiter_quote_url, params=quote_params, timeout=30)
            if quote_response.status_code != 200:
                return {"success": False, "error": f"Quote failed: {quote_response.text}"}
            
            quote_data = quote_response.json()
            expected_tokens = int(quote_data.get('outAmount', 0))
            price_impact = quote_data.get('priceImpactPct', 0)
            
            print(f"✅ Expected tokens: {expected_tokens:,}")
            print(f"✅ Price impact: {price_impact}%")
            
            # Step 5: Get swap transaction
            print("5. Building swap transaction...")
            swap_payload = {
                "quoteResponse": quote_data,
                "userPublicKey": wallet_pubkey,
                "wrapAndUnwrapSol": True,
                "computeUnitPriceMicroLamports": 2000000  # Priority fee
            }
            
            swap_response = requests.post(
                self.jupiter_swap_url,
                json=swap_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if swap_response.status_code != 200:
                return {"success": False, "error": f"Swap failed: {swap_response.text}"}
            
            swap_data = swap_response.json()
            swap_transaction = swap_data["swapTransaction"]
            print("✅ Swap transaction built")
            
            # Step 6: Sign transaction
            print("6. Signing transaction...")
            transaction_bytes = base64.b64decode(swap_transaction)
            transaction = VersionedTransaction.from_bytes(transaction_bytes)
            
            try:
                keypair = Keypair.from_base58_string(private_key)
            except:
                decoded_key = base58.b58decode(private_key)
                keypair = Keypair.from_seed(decoded_key)
            
            signed_tx = VersionedTransaction(transaction.message, [keypair])
            print("✅ Transaction signed")
            
            # Step 7: Broadcast transaction
            print("7. Broadcasting transaction...")
            commitment = CommitmentLevel.Confirmed
            config = RpcSendTransactionConfig(preflight_commitment=commitment)
            
            send_response = requests.post(
                url=self.rpc_url,
                headers={"Content-Type": "application/json"},
                data=SendVersionedTransaction(signed_tx, config).to_json(),
                timeout=30
            )
            
            if send_response.status_code != 200:
                return {"success": False, "error": f"Broadcast failed: {send_response.text}"}
            
            response_json = send_response.json()
            
            if 'result' in response_json:
                tx_hash = response_json['result']
                print(f"✅ Transaction broadcast: {tx_hash}")
                
                # Step 8: Verify token delivery
                print("8. Verifying token delivery...")
                time.sleep(15)  # Wait for confirmation
                
                tokens_received = self.verify_token_delivery(wallet_pubkey, token_mint, expected_tokens)
                
                return {
                    "success": tokens_received > 0,
                    "transaction_hash": tx_hash,
                    "expected_tokens": expected_tokens,
                    "actual_tokens": tokens_received,
                    "explorer_url": f"https://solscan.io/tx/{tx_hash}"
                }
            else:
                error = response_json.get('error', 'Unknown error')
                return {"success": False, "error": f"Transaction failed: {error}"}
                
        except Exception as e:
            return {"success": False, "error": f"Trade execution failed: {e}"}
    
    def verify_token_delivery(self, wallet_pubkey, token_mint, expected_amount):
        """Verify tokens were actually delivered"""
        try:
            payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'getTokenAccountsByOwner',
                'params': [
                    wallet_pubkey,
                    {'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},
                    {'encoding': 'jsonParsed'}
                ]
            }

            response = requests.post(self.rpc_url, json=payload, timeout=10)
            data = response.json()

            if 'result' in data and data['result']['value']:
                accounts = data['result']['value']
                
                for account in accounts:
                    parsed = account['account']['data']['parsed']
                    if parsed and 'info' in parsed:
                        mint = parsed['info']['mint']
                        balance = float(parsed['info']['tokenAmount']['uiAmount'])
                        
                        if mint == token_mint:
                            print(f"🎯 Tokens found: {balance:,.0f}")
                            return balance
            
            print("❌ No tokens found")
            return 0
            
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return 0

def test_jupiter_engine():
    """Test the Jupiter trade engine"""
    engine = JupiterTradeEngine()
    
    # Load test wallet
    with open('test_wallet_info.txt', 'r') as f:
        lines = f.read().strip().split('\n')
        public_key = lines[0].split(': ')[1].strip()
        private_key = lines[1].split(': ')[1].strip()
    
    # Test with CLIPPY
    clippy_mint = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"
    
    result = engine.execute_jupiter_trade(
        wallet_pubkey=public_key,
        private_key=private_key,
        token_mint=clippy_mint,
        sol_amount=0.003,  # 0.003 SOL
        slippage_bps=1000
    )
    
    print("\n" + "="*50)
    print("JUPITER ENGINE TEST RESULT")
    print("="*50)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_jupiter_engine()