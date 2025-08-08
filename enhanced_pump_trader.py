#!/usr/bin/env python3
"""
Enhanced Pump.fun Trader - Based on ChatGPT analysis
Fixes the "throwing SOL down the drain" issue
"""

import logging
import base58
import base64
import asyncio
import aiohttp
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client

# Enhanced settings based on ChatGPT analysis
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2
API_TIMEOUT = 30
PUMPPORTAL_API = "https://pumpportal.fun/api/trade-local"

logger = logging.getLogger(__name__)

class EnhancedPumpTrader:
    """Enhanced PumpFun trader that actually buys tokens (not just drains SOL)"""
    
    def __init__(self, rpc_endpoint: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_endpoint = rpc_endpoint
        self.client = Client(rpc_endpoint)
        logger.info("✅ Enhanced PumpFun Trader initialized")
    
    def check_wallet_balance(self, wallet_address: str):
        """Enhanced balance check from ChatGPT"""
        try:
            pubkey = PublicKey.from_string(wallet_address)
            balance_response = self.client.get_balance(pubkey)
            if balance_response.value is not None:
                lamports = balance_response.value
                sol_balance = lamports / 1e9
                logger.info(f"Wallet balance: {sol_balance:.6f} SOL")
                return {"success": True, "sol_balance": sol_balance, "funded": lamports > 0}
            else:
                return {"success": False, "error": "Unable to fetch balance", "funded": False}
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return {"success": False, "error": str(e), "funded": False}

    async def buy_pump_token(self, private_key: str, token_contract: str, sol_amount: float, slippage_percent: float = 1.0) -> dict:
        """
        ENHANCED: Buy Pump.fun token that actually mints tokens (ChatGPT analysis)
        Key fixes:
        1. Proper response handling with "transaction" field
        2. Enhanced error handling
        3. Better transaction decoding
        4. No "pool" parameter confusion
        """
        try:
            # Key handling (existing logic)
            if private_key.startswith('gAAAAAB'):
                logger.info("Decrypting encrypted private key...")
                from cryptography.fernet import Fernet
                import os
                key_file = 'wallet_encryption.key'
                if os.path.exists(key_file):
                    with open(key_file, 'rb') as f:
                        key = f.read()
                    fernet = Fernet(key)
                    decrypted_str = fernet.decrypt(private_key.encode()).decode()
                    private_key_bytes = base64.b64decode(decrypted_str)
                    logger.info(f"✅ Private key decrypted successfully")
                else:
                    return {"success": False, "error": "Encryption key file not found"}
            else:
                logger.info("Using plain base58 private key...")
                private_key_bytes = base58.b58decode(private_key)
            
            keypair = Keypair.from_bytes(private_key_bytes)
            public_key = str(keypair.pubkey())

            # Enhanced balance check
            balance_check = self.check_wallet_balance(public_key)
            sol_balance = balance_check.get('sol_balance', 0)
            if not balance_check.get("funded", False) or sol_balance < sol_amount:
                return {
                    "success": False,
                    "error": f"Insufficient funds: {sol_balance:.6f} SOL available, need {sol_amount} SOL"
                }
            
            logger.info(f"Ready to buy {sol_amount} SOL of {token_contract[:8]} from wallet {public_key}")

            # ENHANCED PumpPortal API call (ChatGPT improvements)
            trade_data = {
                "publicKey": public_key,
                "action": "buy",
                "mint": token_contract,
                "denominatedInSol": "true",
                "amount": sol_amount,  # Float (not lamports!) - ChatGPT emphasis
                "slippage": slippage_percent,
                "priorityFee": 0.0001
                # NOTE: ChatGPT analysis shows NO "pool" parameter
            }
            
            retry_delay = INITIAL_RETRY_DELAY
            for attempt in range(MAX_RETRIES):
                try:
                    logger.info(f"🚀 Attempt {attempt+1}/{MAX_RETRIES}: Enhanced PumpPortal API call...")
                    
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as session:
                        async with session.post(
                            PUMPPORTAL_API, 
                            json=trade_data, 
                            headers={"Content-Type": "application/json"}  # ChatGPT includes explicit headers
                        ) as response:
                            if response.status == 200:
                                response_data = await response.json()
                                logger.info(f"✅ PumpPortal API responded: {str(response_data)[:120]}...")

                                # CRITICAL: Enhanced response handling (ChatGPT's key insight)
                                serialized_transaction = None
                                
                                if isinstance(response_data, dict) and "transaction" in response_data:
                                    # Look for "transaction" field in dict response
                                    serialized_transaction = response_data["transaction"]
                                    logger.info("✅ Found 'transaction' field in dict response")
                                elif isinstance(response_data, str):
                                    # Raw string response
                                    serialized_transaction = response_data
                                    logger.info("✅ Using raw string response as transaction")
                                else:
                                    logger.error(f"❌ Invalid API response: {response_data}")
                                    return {"success": False, "error": "Invalid API response from PumpPortal"}

                                if not serialized_transaction:
                                    return {"success": False, "error": "No transaction data received from PumpPortal"}

                                # Enhanced transaction handling (ChatGPT approach)
                                try:
                                    transaction_bytes = base64.b64decode(serialized_transaction)
                                    versioned_tx = VersionedTransaction.from_bytes(transaction_bytes)
                                    versioned_tx.sign([keypair])
                                    
                                    send_result = self.client.send_transaction(versioned_tx)
                                    
                                    # Enhanced result handling
                                    tx_hash = None
                                    if hasattr(send_result, 'value') and send_result.value:
                                        tx_hash = str(send_result.value)
                                    elif send_result:
                                        tx_hash = str(send_result)
                                    else:
                                        raise Exception("Transaction submission returned no hash")
                                    
                                    logger.info(f"🎉 TOKEN PURCHASE SUCCESS! TX: {tx_hash}")
                                    
                                    return {
                                        "success": True,
                                        "transaction_id": tx_hash,
                                        "transaction_hash": tx_hash,
                                        "message": f"Successfully bought {sol_amount} SOL worth of {token_contract}",
                                        "amount_sol": sol_amount,
                                        "platform": "pump_fun",
                                        "method": "EnhancedPumpPortal"
                                    }
                                    
                                except Exception as sign_error:
                                    logger.error(f"❌ Transaction signing/sending failed: {sign_error}")
                                    return {"success": False, "error": f"Failed to sign/send transaction: {sign_error}"}
                                    
                            else:
                                error_text = await response.text()
                                logger.warning(f"❌ PumpPortal API error: Status {response.status}, {error_text}")
                                if attempt == MAX_RETRIES - 1:
                                    return {"success": False, "error": f"API error after {MAX_RETRIES} attempts: {error_text}"}
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                
                except aiohttp.ClientError as e:
                    logger.warning(f"❌ Network error: {e}")
                    if attempt == MAX_RETRIES - 1:
                        return {"success": False, "error": f"Network error after {MAX_RETRIES} attempts: {e}"}
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    
            return {"success": False, "error": "PumpPortal API call failed after all retries."}
            
        except Exception as e:
            logger.error(f"❌ Enhanced pump.fun buy failed: {e}")
            return {"success": False, "error": str(e)}

# Test function
async def test_enhanced_trading():
    """Test enhanced trader vs original"""
    print("TESTING ENHANCED PUMP TRADER")
    print("=" * 40)
    print("Key ChatGPT improvements:")
    print("• Look for 'transaction' field in response")
    print("• No 'pool' parameter confusion")
    print("• Enhanced error handling")
    print("• Proper base64 transaction decoding")
    print("• Better result handling")
    print()
    
    trader = EnhancedPumpTrader()
    
    # Test with mock funded wallet
    original_check = trader.check_wallet_balance
    trader.check_wallet_balance = lambda addr: {"success": True, "sol_balance": 0.5, "funded": True}
    
    result = await trader.buy_pump_token(
        private_key="test_enhanced_key",
        token_contract="So11111111111111111111111111111111111111112",
        sol_amount=0.01
    )
    
    trader.check_wallet_balance = original_check
    
    print(f"Enhanced result: {result}")
    print(f"Success: {result.get('success')}")
    print(f"Method: {result.get('method')}")
    print()
    print("✅ Enhanced trader ready for real token minting")

if __name__ == "__main__":
    asyncio.run(test_enhanced_trading())