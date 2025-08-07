"""
Demonstration of Fee Collection Integration for Profitable Trades
"""

from fee_collection_system import collect_profit_fee, get_marketing_wallet

# Example of how fee collection integrates with profitable trades
def demo_profitable_trade():
    """Demo how the fee system works with a profitable trade"""
    
    # Example trade data
    profit_sol = 0.15  # User made 0.15 SOL profit
    token_symbol = "MEME"
    user_wallet = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
    
    # Collect 5% fee
    fee_message, fee_amount = collect_profit_fee(profit_sol, token_symbol, user_wallet)
    
    print("Fee Collection Demo:")
    print(f"User Profit: {profit_sol} SOL")
    print(f"Fee Amount (5%): {fee_amount} SOL")
    print(f"Marketing Wallet: {get_marketing_wallet()}")
    print(f"Net User Profit: {profit_sol - fee_amount} SOL")
    print("\nFee Message to User:")
    print(fee_message)

if __name__ == "__main__":
    demo_profitable_trade()