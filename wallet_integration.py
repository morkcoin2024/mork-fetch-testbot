"""
Real Solana Wallet Integration for Mork F.E.T.C.H Bot
Handles actual wallet transactions, balance checking, and trade execution
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional, Tuple
import base64

# Solana RPC endpoints
SOLANA_RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-api.projectserum.com",
    "https://rpc.ankr.com/solana"
]

# Known token addresses
WSOL_ADDRESS = "So11111111111111111111111111111111111111112"
USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

class SolanaWalletIntegrator:
    def __init__(self):
        self.rpc_endpoint = SOLANA_RPC_ENDPOINTS[0]
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
        })
        
    def _make_rpc_call(self, method: str, params: list) -> Dict[str, Any]:
        """Make RPC call to Solana blockchain"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        for endpoint in SOLANA_RPC_ENDPOINTS:
            try:
                response = self.session.post(endpoint, json=payload, timeout=10)
                response.raise_for_status()
                result = response.json()
                
                if 'error' in result:
                    logging.error(f"Solana RPC error: {result['error']}")
                    continue
                    
                return result.get('result', {})
                
            except Exception as e:
                logging.warning(f"RPC endpoint {endpoint} failed: {str(e)}")
                continue
                
        raise Exception("All Solana RPC endpoints failed")
    
    def get_sol_balance(self, wallet_address: str) -> float:
        """Get SOL balance for a wallet address"""
        try:
            result = self._make_rpc_call("getBalance", [wallet_address])
            lamports = result.get('value', 0)
            return lamports / 1_000_000_000  # Convert lamports to SOL
        except Exception as e:
            logging.error(f"Error getting SOL balance: {str(e)}")
            return 0.0
    
    def get_token_balance(self, wallet_address: str, token_mint: str) -> float:
        """Get SPL token balance for a wallet address"""
        try:
            # Get token accounts by owner
            result = self._make_rpc_call("getTokenAccountsByOwner", [
                wallet_address,
                {"mint": token_mint},
                {"encoding": "jsonParsed"}
            ])
            
            accounts = result.get('value', [])
            if not accounts:
                return 0.0
            
            # Sum up all token account balances
            total_balance = 0.0
            for account in accounts:
                token_amount = account['account']['data']['parsed']['info']['tokenAmount']
                decimals = int(token_amount['decimals'])
                amount = int(token_amount['amount'])
                total_balance += amount / (10 ** decimals)
            
            return total_balance
        except Exception as e:
            logging.error(f"Error getting token balance: {str(e)}")
            return 0.0
    
    def get_token_price_in_sol(self, token_mint: str) -> float:
        """Get token price in SOL using Jupiter Price API"""
        try:
            # Use Jupiter Price API
            url = f"https://price.jup.ag/v4/price"
            params = {
                'ids': token_mint,
                'vsToken': WSOL_ADDRESS
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if token_mint in data['data']:
                return float(data['data'][token_mint]['price'])
            
            return 0.0
        except Exception as e:
            logging.error(f"Error getting token price: {str(e)}")
            return 0.0
    
    def validate_wallet_address(self, address: str) -> bool:
        """Validate if a string is a valid Solana wallet address"""
        try:
            if len(address) < 32 or len(address) > 44:
                return False
            
            # Try to decode base58
            import base58
            decoded = base58.b58decode(address)
            if len(decoded) != 32:
                return False
            
            return True
        except:
            return False
    
    def get_recent_transactions(self, wallet_address: str, limit: int = 10) -> list:
        """Get recent transactions for a wallet"""
        try:
            result = self._make_rpc_call("getSignaturesForAddress", [
                wallet_address,
                {"limit": limit}
            ])
            
            signatures = result if isinstance(result, list) else []
            transactions = []
            
            for sig_info in signatures[:5]:  # Limit to 5 to avoid rate limits
                try:
                    tx_result = self._make_rpc_call("getTransaction", [
                        sig_info['signature'],
                        {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
                    ])
                    
                    if tx_result:
                        transactions.append({
                            'signature': sig_info['signature'],
                            'slot': tx_result.get('slot', 0),
                            'blockTime': tx_result.get('blockTime', 0),
                            'success': not bool(tx_result.get('meta', {}).get('err'))
                        })
                except Exception as e:
                    logging.warning(f"Error getting transaction details: {str(e)}")
                    continue
            
            return transactions
        except Exception as e:
            logging.error(f"Error getting recent transactions: {str(e)}")
            return []
    
    def create_swap_transaction_data(self, 
                                   wallet_address: str,
                                   input_mint: str, 
                                   output_mint: str, 
                                   amount: int,
                                   slippage_bps: int = 50) -> Optional[Dict]:
        """Create swap transaction data using Jupiter API"""
        try:
            # Get quote from Jupiter
            quote_url = "https://quote-api.jup.ag/v6/quote"
            quote_params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps
            }
            
            quote_response = self.session.get(quote_url, params=quote_params, timeout=10)
            quote_response.raise_for_status()
            quote_data = quote_response.json()
            
            if 'error' in quote_data:
                logging.error(f"Jupiter quote error: {quote_data['error']}")
                return None
            
            # Get swap transaction
            swap_url = "https://quote-api.jup.ag/v6/swap"
            swap_data = {
                'quoteResponse': quote_data,
                'userPublicKey': wallet_address,
                'wrapAndUnwrapSol': True,
                'dynamicComputeUnitLimit': True,
                'prioritizationFeeLamports': 'auto'
            }
            
            swap_response = self.session.post(swap_url, json=swap_data, timeout=10)
            swap_response.raise_for_status()
            swap_result = swap_response.json()
            
            if 'error' in swap_result:
                logging.error(f"Jupiter swap error: {swap_result['error']}")
                return None
            
            return {
                'quote': quote_data,
                'transaction': swap_result.get('swapTransaction'),
                'input_amount': amount,
                'expected_output': quote_data.get('outAmount', 0),
                'price_impact': quote_data.get('priceImpactPct', 0)
            }
            
        except Exception as e:
            logging.error(f"Error creating swap transaction: {str(e)}")
            return None

# Real wallet integration functions
def get_real_sol_balance(wallet_address: str) -> float:
    """Get actual SOL balance from blockchain"""
    integrator = SolanaWalletIntegrator()
    return integrator.get_sol_balance(wallet_address)

def get_real_token_balance(wallet_address: str, token_mint: str) -> float:
    """Get actual SPL token balance from blockchain"""
    integrator = SolanaWalletIntegrator()
    return integrator.get_token_balance(wallet_address, token_mint)

def get_real_token_price_sol(token_mint: str) -> float:
    """Get actual token price in SOL"""
    integrator = SolanaWalletIntegrator()
    return integrator.get_token_price_in_sol(token_mint)

def validate_solana_address(address: str) -> bool:
    """Validate Solana wallet address"""
    integrator = SolanaWalletIntegrator()
    return integrator.validate_wallet_address(address)

def create_buy_transaction(wallet_address: str, token_address: str, sol_amount: float, 
                          stop_loss_percent: float = None, take_profit_percent: float = None, 
                          sell_percent: float = None, slippage: float = 0.5) -> Optional[Dict]:
    """Create a buy transaction for a token"""
    integrator = SolanaWalletIntegrator()
    
    # Convert SOL to lamports
    lamports = int(sol_amount * 1_000_000_000)
    
    return integrator.create_swap_transaction_data(
        wallet_address=wallet_address,
        input_mint=WSOL_ADDRESS,
        output_mint=token_address,
        amount=lamports,
        slippage_bps=int(slippage * 100)
    )

def create_sell_transaction(wallet_address: str, token_mint: str, token_amount: float, slippage: float = 0.5) -> Optional[Dict]:
    """Create a sell transaction for a token"""
    integrator = SolanaWalletIntegrator()
    
    # Get token decimals (assume 9 decimals for now, should get from mint info)
    token_amount_raw = int(token_amount * 1_000_000_000)
    
    return integrator.create_swap_transaction_data(
        wallet_address=wallet_address,
        input_mint=token_mint,
        output_mint=WSOL_ADDRESS,
        amount=token_amount_raw,
        slippage_bps=int(slippage * 100)
    )

def get_wallet_transaction_history(wallet_address: str) -> list:
    """Get recent transaction history for wallet"""
    integrator = SolanaWalletIntegrator()
    return integrator.get_recent_transactions(wallet_address)