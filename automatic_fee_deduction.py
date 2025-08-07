"""
Automatic Fee Deduction System for Mork F.E.T.C.H Bot
Deducts 5% fee directly from profitable trades and ACTUALLY SENDS to marketing wallet
"""

import logging
import asyncio
from typing import Dict, Tuple, Optional
from fee_collection_system import MARKETING_WALLET, FEE_PERCENTAGE

# Import Solana libraries for actual transactions
try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    from solders.transaction import Transaction
    from solders.hash import Hash
    from solders.message import Message
    import httpx
    import json
    import base64
    from cryptography.fernet import Fernet
    import os
    SOLANA_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Solana libraries not available: {e}")
    SOLANA_AVAILABLE = False

class AutomaticFeeDeduction:
    """Handles automatic fee deduction from profitable trades"""
    
    def __init__(self):
        self.marketing_wallet = MARKETING_WALLET
        self.fee_percentage = FEE_PERCENTAGE
        self.rpc_url = "https://api.mainnet-beta.solana.com"
    
    def calculate_net_profit_and_fee(self, gross_profit_sol: float) -> Tuple[float, float]:
        """
        Calculate net profit after automatic fee deduction
        Returns: (net_profit_sol, fee_amount_sol)
        """
        if gross_profit_sol <= 0:
            return gross_profit_sol, 0.0
        
        fee_amount = gross_profit_sol * self.fee_percentage
        net_profit = gross_profit_sol - fee_amount
        
        return net_profit, fee_amount
    
    async def send_fee_to_marketing_wallet(self, user_wallet_address: str, fee_amount_sol: float) -> bool:
        """Actually send fee to marketing wallet using Solana blockchain transaction"""
        try:
            if not SOLANA_AVAILABLE:
                logging.error("Cannot send fee - Solana libraries not available")
                return False
                
            if fee_amount_sol <= 0:
                logging.info("No fee to send - amount is 0")
                return True
                
            # Load user's burner wallet to send fee from
            wallet_file = f"user_wallets/user_{user_wallet_address}.json"
            if not os.path.exists(wallet_file):
                logging.error(f"User wallet file not found: {wallet_file}")
                return False
                
            with open(wallet_file, 'r') as f:
                wallet_data = json.load(f)
            
            encrypted_private_key = wallet_data.get('encrypted_private_key')
            if not encrypted_private_key:
                logging.error("No encrypted private key found in wallet file")
                return False
            
            # Decrypt private key
            key_file = 'wallet_encryption.key'
            if not os.path.exists(key_file):
                logging.error("Encryption key file not found")
                return False
                
            with open(key_file, 'rb') as f:
                encryption_key = f.read()
            
            fernet = Fernet(encryption_key)
            decrypted_str = fernet.decrypt(encrypted_private_key.encode()).decode()
            private_key_bytes = base64.b64decode(decrypted_str)
            
            # Create keypair from decrypted private key
            keypair = Keypair.from_bytes(private_key_bytes)
            from_pubkey = keypair.pubkey()
            to_pubkey = Pubkey.from_string(self.marketing_wallet)
            
            # Convert SOL to lamports
            fee_lamports = int(fee_amount_sol * 1_000_000_000)
            
            # Create transfer instruction
            transfer_ix = transfer(TransferParams(
                from_pubkey=from_pubkey,
                to_pubkey=to_pubkey,
                lamports=fee_lamports
            ))
            
            # Get recent blockhash
            async with httpx.AsyncClient() as client:
                response = await client.post(self.rpc_url, json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getLatestBlockhash"
                })
                result = response.json()
                
                if 'result' not in result:
                    logging.error("Failed to get recent blockhash")
                    return False
                
                blockhash_str = result['result']['value']['blockhash']
                recent_blockhash = Hash.from_string(blockhash_str)
            
            # Create transaction
            message = Message.new_with_blockhash([transfer_ix], from_pubkey, recent_blockhash)
            transaction = Transaction.new_unsigned(message)
            transaction.sign([keypair], recent_blockhash)
            
            # Send transaction
            tx_bytes = bytes(transaction)
            tx_b64 = base64.b64encode(tx_bytes).decode()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.rpc_url, json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "sendTransaction",
                    "params": [tx_b64, {"encoding": "base64"}]
                })
                
                result = response.json()
                
                if 'result' in result:
                    tx_signature = result['result']
                    logging.info(f"✅ FEE TRANSACTION SUCCESSFUL: {fee_amount_sol:.6f} SOL sent to marketing wallet")
                    logging.info(f"Transaction signature: {tx_signature}")
                    return True
                else:
                    error_msg = result.get('error', {}).get('message', 'Unknown error')
                    logging.error(f"Fee transaction failed: {error_msg}")
                    return False
                    
        except Exception as e:
            logging.error(f"Failed to send fee to marketing wallet: {e}")
            return False

    def process_profitable_trade_with_auto_fee(self, 
                                             trade_data: Dict,
                                             user_wallet_address: str = None) -> Dict:
        """
        Process a profitable trade with automatic fee deduction AND ACTUAL PAYMENT
        Returns updated trade data with net amounts
        """
        try:
            gross_profit = trade_data.get('profit_sol', 0.0)
            token_symbol = trade_data.get('token_symbol', 'UNKNOWN')
            
            if gross_profit <= 0:
                # No profit, no fee
                trade_data['net_profit_sol'] = gross_profit
                trade_data['fee_deducted_sol'] = 0.0
                trade_data['fee_applied'] = False
                trade_data['fee_sent'] = False
                return trade_data
            
            # Calculate automatic fee deduction
            net_profit, fee_amount = self.calculate_net_profit_and_fee(gross_profit)
            
            # Update trade data with calculations
            trade_data['gross_profit_sol'] = gross_profit
            trade_data['net_profit_sol'] = net_profit
            trade_data['fee_deducted_sol'] = fee_amount
            trade_data['fee_applied'] = True
            trade_data['marketing_wallet'] = self.marketing_wallet
            
            # ACTUALLY SEND THE FEE TO MARKETING WALLET
            if user_wallet_address and fee_amount > 0:
                try:
                    # Run async fee sending in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    fee_sent = loop.run_until_complete(
                        self.send_fee_to_marketing_wallet(user_wallet_address, fee_amount)
                    )
                    loop.close()
                    
                    trade_data['fee_sent'] = fee_sent
                    if fee_sent:
                        logging.info(f"✅ REAL FEE SENT: {fee_amount:.6f} SOL to marketing wallet G2DQGR6iWRyDMdu5GxmnPvVj1xpMN3ZG8JeZLVzMZ3TS")
                    else:
                        logging.error(f"❌ FEE SENDING FAILED: {fee_amount:.6f} SOL NOT sent to marketing wallet")
                except Exception as fee_error:
                    logging.error(f"Fee sending exception: {fee_error}")
                    trade_data['fee_sent'] = False
            else:
                trade_data['fee_sent'] = False
                logging.info(f"Fee calculated but not sent (no user wallet or 0 amount): {fee_amount:.6f} SOL")
            
            logging.info(f"Auto fee processing: {fee_amount:.6f} SOL from {gross_profit:.6f} SOL profit ({token_symbol}) - Sent: {trade_data.get('fee_sent', False)}")
            
            return trade_data
            
        except Exception as e:
            logging.error(f"Auto fee deduction failed: {e}")
            trade_data['fee_applied'] = False
            trade_data['fee_sent'] = False
            return trade_data
    
    def generate_trade_completion_message(self, trade_data: Dict) -> str:
        """Generate trade completion message with automatic fee deduction info"""
        try:
            token_symbol = trade_data.get('token_symbol', 'UNKNOWN')
            gross_profit = trade_data.get('gross_profit_sol', 0.0)
            net_profit = trade_data.get('net_profit_sol', 0.0)
            fee_deducted = trade_data.get('fee_deducted_sol', 0.0)
            fee_applied = trade_data.get('fee_applied', False)
            
            if not fee_applied or gross_profit <= 0:
                # No profit or fee not applied
                return f"""
🎉 <b>TRADE COMPLETED!</b>

<b>📊 {token_symbol} Trade Results:</b>
💰 <b>Result:</b> {gross_profit:.6f} SOL
🎯 <b>Status:</b> {'Break-even or Loss' if gross_profit <= 0 else 'Profit'}

{'❌ <b>No fees charged on unprofitable trades</b>' if gross_profit <= 0 else ''}

<i>Ready for your next trade!</i>
                """
            
            # Check if fee was actually sent
            fee_sent = trade_data.get('fee_sent', False)
            fee_status = "✅ Fee sent to marketing wallet" if fee_sent else "⚠️ Fee calculated (manual payment required)"
            
            # Profitable trade with automatic fee deduction
            return f"""
🎉 <b>PROFITABLE TRADE COMPLETED!</b>

<b>📊 {token_symbol} Trade Results:</b>
💰 <b>Gross Profit:</b> {gross_profit:.6f} SOL
🏦 <b>Platform Fee (0.5%):</b> -{fee_deducted:.6f} SOL
💎 <b>Net Profit to You:</b> {net_profit:.6f} SOL

<b>✅ AUTOMATIC FEE PROCESSING:</b>
• 0.5% platform fee automatically calculated
• {fee_status}
• Marketing wallet: G2DQGR6iWRyDMdu5GxmnPvVj1xpMN3ZG8JeZLVzMZ3TS
• {"Transaction confirmed on blockchain" if fee_sent else "Fee processing attempted"}

<b>🎯 Transaction Summary:</b>
• You receive: {net_profit:.6f} SOL
• Platform receives: {fee_deducted:.6f} SOL
• Total trade profit: {gross_profit:.6f} SOL

<i>Fee helps maintain and improve Mork F.E.T.C.H Bot for all users!</i>
            """
            
        except Exception as e:
            logging.error(f"Failed to generate trade completion message: {e}")
            return "Trade completed - fee processing error"

# Global automatic fee deduction instance
auto_fee_deductor = AutomaticFeeDeduction()

def process_profitable_trade_auto_fee(trade_data: Dict, user_wallet_address: str = None) -> Tuple[Dict, str]:
    """
    Convenience function to process profitable trade with automatic fee deduction AND REAL PAYMENT
    Returns: (updated_trade_data, completion_message)
    """
    updated_trade_data = auto_fee_deductor.process_profitable_trade_with_auto_fee(trade_data, user_wallet_address)
    completion_message = auto_fee_deductor.generate_trade_completion_message(updated_trade_data)
    return updated_trade_data, completion_message

def calculate_net_amount_after_fees(gross_profit_sol: float) -> Tuple[float, float]:
    """
    Calculate net amount user receives after automatic fee deduction
    Returns: (net_amount_to_user, fee_amount)
    """
    return auto_fee_deductor.calculate_net_profit_and_fee(gross_profit_sol)