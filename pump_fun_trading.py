"""
Pump.fun Trading System - Correct Bonding Curve Implementation
Uses PumpPortal API and proper bonding curve contracts instead of Jupiter
"""
import requests
import json
import logging
from typing import Dict, Optional
import base58
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

# Pump.fun Constants
PUMP_FUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_FUN_ACCOUNT = "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"
PUMPPORTAL_API = "https://pumpportal.fun/api/trade-local"

class PumpFunTrader:
    """Handles Pump.fun trading using bonding curve contracts"""
    
    def __init__(self, rpc_endpoint: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_endpoint = rpc_endpoint
        self.client = Client(rpc_endpoint)
        
    def generate_bonding_curve_address(self, mint_address: str) -> str:
        """Generate the bonding curve address for a pump.fun token"""
        try:
            mint_pubkey = PublicKey(mint_address)
            program_pubkey = PublicKey(PUMP_FUN_PROGRAM_ID)
            
            # Generate bonding curve PDA
            bonding_curve_seeds = [b"bonding-curve", bytes(mint_pubkey)]
            bonding_curve_address, _ = PublicKey.find_program_address(
                bonding_curve_seeds, 
                program_pubkey
            )
            
            logger.info(f"Generated bonding curve: {bonding_curve_address} for mint: {mint_address}")
            return str(bonding_curve_address)
            
        except Exception as e:
            logger.error(f"Failed to generate bonding curve address: {e}")
            return ""
    
    async def buy_pump_token(self, 
                           private_key: str,
                           token_mint: str, 
                           sol_amount: float,
                           slippage_percent: float = 1.0) -> Dict:
        """
        Buy pump.fun token using PumpPortal API (correct method)
        """
        try:
            # Get wallet from private key
            private_key_bytes = base58.b58decode(private_key)
            keypair = Keypair.from_secret_key(private_key_bytes)
            public_key = str(keypair.public_key)
            
            logger.info(f"Buying {sol_amount} SOL worth of {token_mint[:8]}...")
            
            # Use PumpPortal API for proper pump.fun trading
            trade_data = {
                "publicKey": public_key,
                "action": "buy",
                "mint": token_mint,
                "denominatedInSol": "true",  # We're spending SOL amount
                "amount": int(sol_amount * 1_000_000_000),  # Convert to lamports
                "slippage": slippage_percent,
                "priorityFee": 0.0001  # Small priority fee
            }
            
            logger.info(f"Sending buy request: {trade_data}")
            
            # Make the API call
            async with aiohttp.ClientSession() as session:
                async with session.post(PUMPPORTAL_API, 
                                      json=trade_data,
                                      headers={"Content-Type": "application/json"}) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"PumpPortal API error: {error_text}")
                        return {"success": False, "error": f"API error: {error_text}"}
                    
                    response_data = await response.json()
                    logger.info(f"PumpPortal response: {response_data}")
                    
                    # The API returns a serialized transaction
                    if 'transaction' in response_data or isinstance(response_data, str):
                        # Response is the serialized transaction
                        transaction_data = response_data if isinstance(response_data, str) else response_data['transaction']
                        
                        # Deserialize and sign transaction
                        transaction_bytes = base58.b58decode(transaction_data)
                        transaction = VersionedTransaction.deserialize(transaction_bytes)
                        
                        # Sign with our keypair
                        transaction.sign([keypair])
                        
                        # Send transaction
                        signature = self.client.send_transaction(transaction)
                        
                        logger.info(f"Transaction sent: {signature}")
                        
                        # Wait for confirmation
                        await asyncio.sleep(2)
                        confirmation = self.client.confirm_transaction(signature.value)
                        
                        return {
                            "success": True,
                            "transaction_hash": str(signature),
                            "confirmation": confirmation,
                            "sol_spent": sol_amount,
                            "token_mint": token_mint
                        }
                    else:
                        return {"success": False, "error": "Invalid response format"}
                        
        except Exception as e:
            logger.error(f"Pump.fun buy failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def sell_pump_token(self,
                            private_key: str,
                            token_mint: str,
                            percentage: float = 100.0,
                            slippage_percent: float = 1.0) -> Dict:
        """
        Sell pump.fun token using PumpPortal API
        """
        try:
            # Get wallet from private key
            private_key_bytes = base58.b58decode(private_key)
            keypair = Keypair.from_secret_key(private_key_bytes)
            public_key = str(keypair.public_key)
            
            logger.info(f"Selling {percentage}% of {token_mint[:8]}...")
            
            # Get current token balance first
            token_balance = await self.get_token_balance(public_key, token_mint)
            if token_balance == 0:
                return {"success": False, "error": "No tokens to sell"}
            
            # Calculate amount to sell
            sell_amount = int(token_balance * (percentage / 100))
            
            trade_data = {
                "publicKey": public_key,
                "action": "sell",
                "mint": token_mint,
                "denominatedInSol": "false",  # Selling tokens, not SOL
                "amount": sell_amount,
                "slippage": slippage_percent,
                "priorityFee": 0.0001
            }
            
            logger.info(f"Sending sell request: {trade_data}")
            
            # Make the API call
            async with aiohttp.ClientSession() as session:
                async with session.post(PUMPPORTAL_API, 
                                      json=trade_data,
                                      headers={"Content-Type": "application/json"}) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"PumpPortal sell API error: {error_text}")
                        return {"success": False, "error": f"API error: {error_text}"}
                    
                    response_data = await response.json()
                    
                    # Handle transaction signing and sending (same as buy)
                    if 'transaction' in response_data or isinstance(response_data, str):
                        transaction_data = response_data if isinstance(response_data, str) else response_data['transaction']
                        
                        transaction_bytes = base58.b58decode(transaction_data)
                        transaction = VersionedTransaction.deserialize(transaction_bytes)
                        transaction.sign([keypair])
                        
                        signature = self.client.send_transaction(transaction)
                        logger.info(f"Sell transaction sent: {signature}")
                        
                        await asyncio.sleep(2)
                        confirmation = self.client.confirm_transaction(signature.value)
                        
                        return {
                            "success": True,
                            "transaction_hash": str(signature),
                            "confirmation": confirmation,
                            "tokens_sold": sell_amount,
                            "percentage_sold": percentage
                        }
                    else:
                        return {"success": False, "error": "Invalid sell response format"}
                        
        except Exception as e:
            logger.error(f"Pump.fun sell failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_token_balance(self, wallet_address: str, token_mint: str) -> float:
        """Get token balance for pump.fun tokens (6 decimals)"""
        try:
            # Pump.fun tokens use 6 decimals, not 9
            from solana.rpc.types import TokenAccountOpts
            response = self.client.get_token_accounts_by_owner(
                PublicKey.from_string(wallet_address),
                TokenAccountOpts(mint=PublicKey.from_string(token_mint))
            )
            
            if response.value and response.value:
                account_info = response.value[0].account
                token_amount = account_info.data.parsed.info.token_amount
                return float(token_amount.ui_amount or 0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return 0.0
    
    def get_bonding_curve_progress(self, token_mint: str) -> Dict:
        """Get bonding curve progress for pump.fun token"""
        try:
            # This would typically involve querying the bonding curve account
            # For now, return basic info
            bonding_curve_address = self.generate_bonding_curve_address(token_mint)
            
            return {
                "bonding_curve_address": bonding_curve_address,
                "token_mint": token_mint,
                "progress_percent": 0.0,  # Would need to calculate from reserves
                "market_cap": 0.0,
                "note": "Bonding curve progress calculation requires reserve data"
            }
            
        except Exception as e:
            logger.error(f"Failed to get bonding curve progress: {e}")
            return {}

# Convenience functions for integration
async def buy_pump_fun_token(private_key: str, token_mint: str, sol_amount: float) -> Dict:
    """Convenience function to buy pump.fun token"""
    trader = PumpFunTrader()
    return await trader.buy_pump_token(private_key, token_mint, sol_amount)

async def sell_pump_fun_token(private_key: str, token_mint: str, percentage: float = 100.0) -> Dict:
    """Convenience function to sell pump.fun token"""
    trader = PumpFunTrader()
    return await trader.sell_pump_token(private_key, token_mint, percentage)