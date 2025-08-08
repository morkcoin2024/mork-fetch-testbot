"""
Automatic Fee Deduction System for Mork F.E.T.C.H Bot
Deducts 5% fee directly from profitable trades before sending to user
"""

import logging
from typing import Dict, Tuple, Optional
from fee_collection_system import MARKETING_WALLET, FEE_PERCENTAGE

class AutomaticFeeDeduction:
    """Handles automatic fee deduction from profitable trades"""
    
    def __init__(self):
        self.marketing_wallet = MARKETING_WALLET
        self.fee_percentage = FEE_PERCENTAGE
    
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
    
    def process_profitable_trade_with_auto_fee(self, 
                                             trade_data: Dict) -> Dict:
        """
        Process a profitable trade with automatic fee deduction
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
                return trade_data
            
            # Calculate automatic fee deduction
            net_profit, fee_amount = self.calculate_net_profit_and_fee(gross_profit)
            
            # Update trade data
            trade_data['gross_profit_sol'] = gross_profit
            trade_data['net_profit_sol'] = net_profit
            trade_data['fee_deducted_sol'] = fee_amount
            trade_data['fee_applied'] = True
            trade_data['marketing_wallet'] = self.marketing_wallet
            
            logging.info(f"Auto fee deduction: {fee_amount:.6f} SOL from {gross_profit:.6f} SOL profit ({token_symbol})")
            
            return trade_data
            
        except Exception as e:
            logging.error(f"Auto fee deduction failed: {e}")
            trade_data['fee_applied'] = False
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
            
            # Profitable trade with automatic fee deduction
            return f"""
🎉 <b>PROFITABLE TRADE COMPLETED!</b>

<b>📊 {token_symbol} Trade Results:</b>
💰 <b>Gross Profit:</b> {gross_profit:.6f} SOL
🏦 <b>Platform Fee (5%):</b> -{fee_deducted:.6f} SOL
💎 <b>Net Profit to You:</b> {net_profit:.6f} SOL

<b>✅ AUTOMATIC FEE PROCESSING:</b>
• 5% platform fee automatically deducted
• Fee sent to marketing wallet
• No additional payment required
• Net profit transferred to your wallet

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

def process_profitable_trade_auto_fee(trade_data: Dict) -> Tuple[Dict, str]:
    """
    Convenience function to process profitable trade with automatic fee deduction
    Returns: (updated_trade_data, completion_message)
    """
    updated_trade_data = auto_fee_deductor.process_profitable_trade_with_auto_fee(trade_data)
    completion_message = auto_fee_deductor.generate_trade_completion_message(updated_trade_data)
    return updated_trade_data, completion_message

def calculate_net_amount_after_fees(gross_profit_sol: float) -> Tuple[float, float]:
    """
    Calculate net amount user receives after automatic fee deduction
    Returns: (net_amount_to_user, fee_amount)
    """
    return auto_fee_deductor.calculate_net_profit_and_fee(gross_profit_sol)