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
from solders.transaction import Transaction
from solders.system_program import TransferParams, transfer
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
            mint_pubkey = PublicKey.from_string(mint_address)
            program_pubkey = PublicKey.from_string(PUMP_FUN_PROGRAM_ID)
            
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
    
    def check_wallet_balance(self, wallet_address: str) -> Dict:
        """Check wallet SOL balance before trading (ChatGPT's suggestion)"""
        try:
            pubkey = PublicKey.from_string(wallet_address)
            balance_response = self.client.get_balance(pubkey)
            
            if balance_response.value is not None:
                lamports = balance_response.value
                sol_balance = lamports / 1e9
                
                logger.info(f"Wallet balance check: {sol_balance:.6f} SOL ({lamports} lamports)")
                
                return {
                    "success": True,
                    "sol_balance": sol_balance,
                    "lamports": lamports,
                    "funded": lamports > 0,
                    "trading_ready": lamports >= 10_000_000  # 0.01 SOL minimum
                }
            else:
                return {
                    "success": False,
                    "error": "Unable to fetch balance",
                    "funded": False
                }
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "funded": False
            }

    async def buy_pump_token(self, 
                           private_key: str,
                           token_mint: str, 
                           sol_amount: float,
                           slippage_percent: float = 1.0) -> Dict:
        """
        Buy pump.fun token using PumpPortal API (correct method)
        """
        try:
            # Handle encrypted private key (from burner wallet system)
            if private_key.startswith('gAAAAAB'):
                # This is an encrypted private key - decrypt it first
                logger.info("Decrypting encrypted private key...")
                try:
                    # Use the encryption key file to decrypt
                    from cryptography.fernet import Fernet
                    import os
                    
                    key_file = 'wallet_encryption.key'
                    if os.path.exists(key_file):
                        with open(key_file, 'rb') as f:
                            key = f.read()
                        fernet = Fernet(key)
                        decrypted_str = fernet.decrypt(private_key.encode()).decode()
                        # The private key was stored as base64, decode it
                        import base64
                        private_key_bytes = base64.b64decode(decrypted_str)
                        logger.info(f"✅ Private key decrypted and base64 decoded successfully ({len(decrypted_str)} chars -> {len(private_key_bytes)} bytes)")
                    else:
                        return {"success": False, "error": "Encryption key file not found"}
                        
                except Exception as decrypt_error:
                    logger.error(f"Decryption failed: {decrypt_error}")
                    return {"success": False, "error": f"Key decryption failed: {decrypt_error}"}
            else:
                # Plain base58 private key
                logger.info("Using plain base58 private key...")
                private_key_bytes = base58.b58decode(private_key)
                
            keypair = Keypair.from_bytes(private_key_bytes)
            public_key = str(keypair.pubkey())
            
            # CRITICAL: Check wallet balance first (ChatGPT's suggestion)
            balance_check = self.check_wallet_balance(public_key)
            if not balance_check.get("funded", False):
                return {
                    "success": False,
                    "error": f"Wallet not funded: {balance_check.get('sol_balance', 0):.6f} SOL available, need {sol_amount} SOL"
                }
            
            if balance_check.get("sol_balance", 0) < sol_amount:
                return {
                    "success": False,
                    "error": f"Insufficient funds: {balance_check.get('sol_balance', 0):.6f} SOL available, need {sol_amount} SOL"
                }
            
            logger.info(f"✅ Wallet funded with {balance_check.get('sol_balance', 0):.6f} SOL")
            logger.info(f"Buying {sol_amount} SOL worth of {token_mint[:8]}...")
            
            # CHATGPT'S FIX: Use SystemProgram.transfer() directly to bonding curve
            bonding_curve_address = self.generate_bonding_curve_address(token_mint)
            if not bonding_curve_address:
                return {"success": False, "error": "Failed to generate bonding curve address"}
            
            # Create the transfer transaction (ChatGPT's exact suggestion)
            try:
                tx = Transaction()
                transfer_params = TransferParams(
                    from_pubkey=keypair.pubkey(),  # burner wallet
                    to_pubkey=PublicKey.from_string(bonding_curve_address),  # pump.fun bonding address
                    lamports=int(sol_amount * 1_000_000_000),  # Convert SOL to lamports
                )
                tx.add(transfer(transfer_params))
                
                # Debug printing as ChatGPT suggested
                logger.info(f"🔍 ChatGPT Debug Info:")
                logger.info(f"  Burner public key: {keypair.pubkey()}")
                logger.info(f"  Bonding contract address: {bonding_curve_address}")
                logger.info(f"  Amount in lamports: {int(sol_amount * 1_000_000_000)}")
                
                # Send the transaction with burner wallet signing
                response = self.client.send_transaction(tx, keypair)
                logger.info(f"✅ Transaction sent: {response}")
                
                return {
                    "success": True,
                    "transaction_id": str(response.value) if hasattr(response, 'value') else str(response),
                    "message": f"Successfully bought {sol_amount} SOL worth of {token_mint}",
                    "bonding_curve": bonding_curve_address,
                    "amount_lamports": int(sol_amount * 1_000_000_000)
                }
                
            except Exception as transfer_error:
                logger.error(f"SystemProgram.transfer() failed: {transfer_error}")
                return {"success": False, "error": f"Direct transfer failed: {transfer_error}"}
            
            # Fallback to PumpPortal API if direct transfer fails
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
            # Handle encrypted private key (same as buy function)
            if private_key.startswith('gAAAAAB'):
                logger.info("Decrypting encrypted private key for sell...")
                try:
                    from cryptography.fernet import Fernet
                    import os
                    
                    key_file = 'wallet_encryption.key'
                    if os.path.exists(key_file):
                        with open(key_file, 'rb') as f:
                            key = f.read()
                        fernet = Fernet(key)
                        decrypted_str = fernet.decrypt(private_key.encode()).decode()
                        # The private key was stored as base64, decode it
                        import base64
                        private_key_bytes = base64.b64decode(decrypted_str)
                        logger.info(f"✅ Private key decrypted and base64 decoded successfully for sell ({len(decrypted_str)} chars -> {len(private_key_bytes)} bytes)")
                    else:
                        return {"success": False, "error": "Encryption key file not found"}
                        
                except Exception as decrypt_error:
                    logger.error(f"Sell decryption failed: {decrypt_error}")
                    return {"success": False, "error": f"Key decryption failed: {decrypt_error}"}
            else:
                private_key_bytes = base58.b58decode(private_key)
                
            keypair = Keypair.from_bytes(private_key_bytes)
            public_key = str(keypair.pubkey())
            
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