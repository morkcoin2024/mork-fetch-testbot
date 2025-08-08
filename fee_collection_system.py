"""
Fee Collection System for Mork F.E.T.C.H Bot
Handles 5% fee collection from profitable trades and routes to marketing wallet
"""

import logging
import requests
from datetime import datetime
from typing import Dict, Optional, Tuple
import requests

# Marketing wallet address for fee collection
MARKETING_WALLET = "G2DQGR6iWRyDMdu5GxmnPvVj1xpMN3ZG8JeZLVzMZ3TS"
FEE_PERCENTAGE = 0.005  # 0.5% fee on profitable trades (corrected from 5% to 0.5%)

class FeeCollectionSystem:
    """Handles fee collection from profitable trades"""
    
    def __init__(self):
        self.marketing_wallet = MARKETING_WALLET
        self.fee_percentage = FEE_PERCENTAGE
        
    def calculate_fee(self, profit_amount_sol: float) -> float:
        """Calculate 5% fee from profit amount in SOL"""
        if profit_amount_sol <= 0:
            return 0.0
        return profit_amount_sol * self.fee_percentage
    
    def calculate_fee_usd(self, profit_amount_usd: float) -> float:
        """Calculate 5% fee from profit amount in USD"""
        if profit_amount_usd <= 0:
            return 0.0
        return profit_amount_usd * self.fee_percentage
    
    def generate_fee_collection_link(self, user_wallet: str, fee_amount_sol: float, trade_id: str = None) -> str:
        """Generate Jupiter DEX link for fee collection transfer"""
        try:
            # Convert SOL to lamports for Jupiter
            fee_lamports = int(fee_amount_sol * 1_000_000_000)
            
            # Create Jupiter transfer link
            # This will create a SOL transfer from user wallet to marketing wallet
            jupiter_link = f"https://jup.ag/send?to={self.marketing_wallet}&amount={fee_lamports}&token=SOL"
            
            logging.info(f"Generated fee collection link for {fee_amount_sol:.6f} SOL to marketing wallet")
            return jupiter_link
            
        except Exception as e:
            logging.error(f"Failed to generate fee collection link: {e}")
            return ""
    
    def create_fee_collection_message(self, 
                                    profit_amount_sol: float, 
                                    fee_amount_sol: float,
                                    token_symbol: str,
                                    user_wallet: str) -> str:
        """Create fee collection message for successful trades"""
        try:
            fee_link = self.generate_fee_collection_link(user_wallet, fee_amount_sol)
            
            fee_message = f"""
🎉 <b>PROFITABLE TRADE COMPLETED!</b>

<b>📊 Trade Summary:</b>
🏷️ <b>Token:</b> ${token_symbol}
💰 <b>Total Profit:</b> {profit_amount_sol:.6f} SOL
🏦 <b>Platform Fee (5%):</b> {fee_amount_sol:.6f} SOL
💎 <b>Your Net Profit:</b> {profit_amount_sol - fee_amount_sol:.6f} SOL

<b>💳 Fee Payment Required:</b>
Please complete the 5% platform fee payment to support Mork F.E.T.C.H Bot development.

<b>🔗 Pay Fee via Jupiter:</b>
<a href="{fee_link}">👆 Pay {fee_amount_sol:.6f} SOL Platform Fee</a>

<i>Fee payments help maintain and improve the bot for all users!</i>
            """
            
            return fee_message
            
        except Exception as e:
            logging.error(f"Failed to create fee collection message: {e}")
            return f"Profit: {profit_amount_sol:.6f} SOL | Fee: {fee_amount_sol:.6f} SOL"
    
    def process_profitable_trade(self, 
                               trade_data: Dict, 
                               user_wallet: str) -> Tuple[str, float]:
        """Process a profitable trade and calculate fees"""
        try:
            # Extract trade information
            profit_sol = trade_data.get('profit_sol', 0.0)
            token_symbol = trade_data.get('token_symbol', 'UNKNOWN')
            entry_price = trade_data.get('entry_price', 0.0)
            exit_price = trade_data.get('exit_price', 0.0)
            
            # Only collect fees on profitable trades
            if profit_sol <= 0:
                return "No fees due - trade was not profitable", 0.0
            
            # Calculate 5% fee
            fee_amount = self.calculate_fee(profit_sol)
            
            # Create fee collection message
            fee_message = self.create_fee_collection_message(
                profit_sol, fee_amount, token_symbol, user_wallet
            )
            
            # Log fee collection
            logging.info(f"Fee collection processed: {fee_amount:.6f} SOL from {profit_sol:.6f} SOL profit")
            
            return fee_message, fee_amount
            
        except Exception as e:
            logging.error(f"Failed to process profitable trade fee: {e}")
            return "Fee calculation error", 0.0
    
    def get_marketing_wallet_balance(self) -> float:
        """Get current balance of marketing wallet"""
        try:
            rpc_url = "https://api.mainnet-beta.solana.com"
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [self.marketing_wallet]
            }
            
            response = requests.post(rpc_url, json=data)
            result = response.json()
            
            if 'result' in result and 'value' in result['result']:
                # Convert lamports to SOL
                lamports = result['result']['value']
                balance_sol = lamports / 1_000_000_000
                return balance_sol
            return 0.0
            
        except Exception as e:
            logging.error(f"Failed to get marketing wallet balance: {e}")
            return 0.0
    
    def validate_fee_payment(self, user_wallet: str, expected_fee: float, recent_hours: int = 1) -> bool:
        """Validate if user has paid the required fee (simplified check)"""
        try:
            # This is a simplified validation - in production you'd check recent transactions
            # For now, we'll assume fees are paid via the Jupiter link
            logging.info(f"Fee validation requested for {expected_fee:.6f} SOL from {user_wallet}")
            return True  # Simplified - Jupiter handles the actual transfer
            
        except Exception as e:
            logging.error(f"Fee validation failed: {e}")
            return False

# Global fee collection instance
fee_collector = FeeCollectionSystem()

def collect_profit_fee(profit_sol: float, token_symbol: str, user_wallet: str) -> Tuple[str, float]:
    """Convenience function to collect fees from profitable trades"""
    trade_data = {
        'profit_sol': profit_sol,
        'token_symbol': token_symbol
    }
    return fee_collector.process_profitable_trade(trade_data, user_wallet)

def get_fee_percentage() -> float:
    """Get current fee percentage"""
    return FEE_PERCENTAGE

def get_marketing_wallet() -> str:
    """Get marketing wallet address"""
    return MARKETING_WALLET
