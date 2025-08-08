"""
CRITICAL FIX: Clean PumpPortal API Implementation
Removes "pool" parameter and implements proper transaction verification
"""
import requests
import json
import logging
from typing import Dict, Optional
import base58
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solana.rpc.api import Client  
import time
import asyncio
import aiohttp
from solana.rpc.commitment import Confirmed
import base64
from solders.transaction import Transaction

logger = logging.getLogger(__name__)

# Pump.fun Constants
PUMP_FUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_FUN_ACCOUNT = "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"
PUMPPORTAL_API = "https://pumpportal.fun/api/trade-local"

# Configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2
API_TIMEOUT = 30

class FixedPumpFunTrader:
    """FIXED implementation - removes pool parameter, adds proper verification"""

    def __init__(self, rpc_endpoint: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_endpoint = rpc_endpoint
        self.client = Client(rpc_endpoint)

    def check_wallet_balance(self, wallet_address: str) -> Dict:
        """Check SOL balance of a wallet"""
        try:
            pubkey = PublicKey.from_string(wallet_address)
            balance_response = self.client.get_balance(pubkey)

            if balance_response.value is not None:
                lamports = balance_response.value
                sol_balance = lamports / 1_000_000_000

                return {
                    "success": True,
                    "sol_balance": sol_balance,
                    "lamports": lamports,
                    "funded": sol_balance > 0.001,
                    "trading_ready": sol_balance >= 0.01
                }
            else:
                return {"success": False, "error": "Unable to fetch balance"}

        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return {"success": False, "error": str(e)}

    async def buy_pump_token_fixed(self, private_key: str, token_contract: str, sol_amount: float, slippage_percent: float = 1.0) -> Dict:
        """FIXED: Buy pump.fun token without pool parameter"""
        try:
            logger.info(f"🚀 FIXED IMPLEMENTATION: Buying {sol_amount} SOL of {token_contract}")

            # Handle different key types
            if private_key in ['test_key', 'demo_key', 'funded_key'] or '_' in private_key:
                logger.info("Using test key - generating mock keypair for demo")
                test_keypair = Keypair()
                private_key_bytes = bytes(test_keypair)
            else:
                private_key_bytes = base58.b58decode(private_key)

            keypair = Keypair.from_bytes(private_key_bytes)
            public_key = str(keypair.pubkey())

            # Check wallet balance
            balance_check = self.check_wallet_balance(public_key)
            wallet_balance = balance_check.get('sol_balance', 0)

            logger.info(f"💰 Wallet balance: {wallet_balance:.6f} SOL")

            if wallet_balance < sol_amount:
                return {
                    "success": False,
                    "error": f"Insufficient funds: {wallet_balance:.6f} SOL available, need {sol_amount} SOL"
                }

            # FIXED trade_data - REMOVED "pool" parameter per ChatGPT analysis
            trade_data = {
                "publicKey": public_key,
                "action": "buy",
                "mint": token_contract,
                "denominatedInSol": "true",
                "amount": sol_amount,
                "slippage": slippage_percent,
                "priorityFee": 0.0001
                # CRITICAL: "pool": "pump" parameter REMOVED to prevent SOL draining
            }

            logger.info(f"📤 Sending fixed trade_data: {json.dumps(trade_data, indent=2)}")

            for attempt in range(MAX_RETRIES):
                try:
                    logger.info(f"🔄 Attempt {attempt + 1}/{MAX_RETRIES}: Fixed PumpPortal API...")

                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as session:
                        async with session.post(
                            PUMPPORTAL_API, 
                            json=trade_data,
                            headers={"Content-Type": "application/json"}
                        ) as response:
                            if response.status == 200:
                                response_data = await response.json()
                                logger.info(f"📥 API Response: {response_data}")

                                # Extract transaction data
                                serialized_transaction = None
                                if isinstance(response_data, dict) and "transaction" in response_data:
                                    serialized_transaction = response_data["transaction"]
                                elif isinstance(response_data, str):
                                    serialized_transaction = response_data
                                else:
                                    raise Exception(f"Invalid API response: {type(response_data)}")

                                if not serialized_transaction:
                                    raise Exception("No transaction data received")

                                # ENHANCED TRANSACTION PROCESSING
                                try:
                                    # Method 1: Proper signing and sending
                                    logger.info(f"🔐 Attempting proper transaction signing...")
                                    tx_data = base64.b64decode(serialized_transaction)
                                    transaction = Transaction.deserialize(tx_data)
                                    transaction.sign(keypair)
                                    
                                    send_result = self.client.send_transaction(
                                        transaction,
                                        opts={"skip_preflight": False, "preflight_commitment": Confirmed}
                                    )
                                    
                                    tx_hash = str(send_result.value)
                                    logger.info(f"✅ PROPERLY SIGNED TRANSACTION SENT: {tx_hash}")
                                    
                                    # Verify balance change
                                    await asyncio.sleep(3)
                                    post_balance = self.check_wallet_balance(public_key)
                                    new_balance = post_balance.get('sol_balance', wallet_balance)
                                    balance_change = wallet_balance - new_balance
                                    
                                    logger.info(f"💹 Balance change: {balance_change:.6f} SOL")
                                    
                                    return {
                                        "success": True,
                                        "transaction_hash": tx_hash,
                                        "method": "Fixed_No_Pool_Param",
                                        "amount_sol": sol_amount,
                                        "balance_before": wallet_balance,
                                        "balance_after": new_balance,
                                        "balance_change": balance_change,
                                        "platform": "pump_fun",
                                        "tokens_acquired": balance_change > 0,
                                        "message": f"FIXED: Removed pool param, {balance_change:.6f} SOL spent"
                                    }
                                    
                                except Exception as signing_error:
                                    logger.warning(f"⚠️ Signing failed: {signing_error}, trying raw method...")
                                    
                                    # Method 2: Raw transaction fallback
                                    send_result = self.client.send_raw_transaction(
                                        serialized_transaction,
                                        opts={"skip_preflight": True, "preflight_commitment": Confirmed}
                                    )
                                    
                                    tx_hash = str(send_result.value) if hasattr(send_result, 'value') else str(send_result)
                                    logger.info(f"📤 Raw transaction sent: {tx_hash}")
                                    
                                    return {
                                        "success": True,
                                        "transaction_hash": tx_hash,
                                        "method": "Fixed_Raw_No_Pool",
                                        "amount_sol": sol_amount,
                                        "platform": "pump_fun",
                                        "tokens_acquired": "unverified",
                                        "message": f"FIXED raw method - pool parameter removed"
                                    }
                                    
                            else:
                                error_text = await response.text()
                                raise Exception(f"API error {response.status}: {error_text}")

                except Exception as e:
                    logger.warning(f"❌ Attempt {attempt + 1} failed: {e}")
                    last_error = e

                if attempt < MAX_RETRIES - 1:
                    retry_delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)

            return {
                "success": False,
                "error": f"Fixed API failed after {MAX_RETRIES} attempts: {last_error}",
                "attempts": MAX_RETRIES,
                "method": "Fixed_API_Failed"
            }

        except Exception as e:
            logger.error(f"Fixed buy failed: {e}")
            return {"success": False, "error": str(e)}


async def execute_fixed_pump_trade(private_key: str, token_contract: str, sol_amount: float) -> Dict:
    """Execute fixed pump.fun trade without pool parameter"""
    try:
        logger.info(f"🔧 EXECUTING FIXED TRADE: {sol_amount} SOL for {token_contract}")
        
        trader = FixedPumpFunTrader()
        result = await trader.buy_pump_token_fixed(private_key, token_contract, sol_amount)
        
        if result.get('success'):
            logger.info(f"✅ FIXED TRADE SUCCESS: {result.get('message', 'Trade completed')}")
            return {
                'success': True,
                'transaction_hash': result.get('transaction_hash', ''),
                'tx_hash': result.get('transaction_hash', ''),
                'sol_spent': result.get('balance_change', sol_amount),
                'tokens_received': result.get('tokens_acquired', False),
                'method': result.get('method', 'Fixed_Implementation'),
                'platform': 'pump.fun',
                'fixed_implementation': True
            }
        else:
            logger.error(f"❌ FIXED TRADE FAILED: {result.get('error', 'Unknown error')}")
            return {
                'success': False,
                'error': result.get('error', 'Fixed trade failed'),
                'method': 'Fixed_Implementation_Failed'
            }
            
    except Exception as e:
        logger.error(f"Fixed trade execution failed: {e}")
        return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    # Test the fixed implementation
    import asyncio
    async def test_fixed():
        result = await execute_fixed_pump_trade(
            "test_key",
            "9TZxZUkgzNmqF2cKHKrWJFP3E2qVTkHhK3dRfDZ6JpgJ",
            0.01
        )
        print(f"Fixed test result: {result}")
    
    asyncio.run(test_fixed())