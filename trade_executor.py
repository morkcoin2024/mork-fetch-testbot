"""
Trade Execution Engine for VIP FETCH Auto-Trading
Handles buy/sell operations and trade monitoring
"""
import asyncio
import logging
import time
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import requests
from models import db, UserSession

logger = logging.getLogger(__name__)

@dataclass
class ActiveTrade:
    """Data class for active trades"""
    trade_id: str
    chat_id: str
    token_mint: str
    token_name: str
    token_symbol: str
    entry_price: float
    trade_amount: float
    stop_loss_percent: float
    take_profit_percent: float
    entry_time: datetime
    status: str  # 'monitoring', 'completed', 'failed'
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None

class TradeExecutor:
    """Executes and monitors cryptocurrency trades"""
    
    def __init__(self):
        self.active_trades: Dict[str, List[ActiveTrade]] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        
    async def execute_buy_order(self, chat_id: str, wallet_address: str, 
                              token_mint: str, amount_sol: float) -> Dict:
        """Execute a buy order for a token"""
        try:
            # In production, this would integrate with Solana DEX APIs
            # For now, we simulate the buy execution
            
            # Get current token price
            current_price = await self._get_token_price(token_mint)
            if not current_price:
                return {
                    'success': False,
                    'error': 'Unable to fetch token price'
                }
            
            # Simulate buy transaction
            transaction_id = f"buy_{int(time.time())}_{token_mint[:8]}"
            
            # Calculate tokens received (minus slippage)
            slippage = 0.02  # 2% slippage simulation
            tokens_received = (amount_sol / current_price) * (1 - slippage)
            
            logger.info(f"Simulated buy: {amount_sol} SOL -> {tokens_received:.2f} tokens at {current_price}")
            
            return {
                'success': True,
                'transaction_id': transaction_id,
                'tokens_received': tokens_received,
                'entry_price': current_price,
                'amount_sol': amount_sol,
                'slippage': slippage
            }
            
        except Exception as e:
            logger.error(f"Buy order failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def execute_sell_order(self, trade: ActiveTrade, sell_percentage: float = 100.0) -> Dict:
        """Execute a sell order for a trade"""
        try:
            # Get current token price
            current_price = await self._get_token_price(trade.token_mint)
            if not current_price:
                return {
                    'success': False,
                    'error': 'Unable to fetch current token price'
                }
            
            # Calculate sell amount
            tokens_to_sell = (trade.trade_amount / trade.entry_price) * (sell_percentage / 100)
            sol_received = tokens_to_sell * current_price * 0.98  # 2% slippage
            
            # Calculate P&L
            pnl = sol_received - (trade.trade_amount * sell_percentage / 100)
            
            # Simulate transaction
            transaction_id = f"sell_{int(time.time())}_{trade.token_mint[:8]}"
            
            logger.info(f"Simulated sell: {tokens_to_sell:.2f} tokens -> {sol_received:.3f} SOL (P&L: {pnl:+.3f})")
            
            return {
                'success': True,
                'transaction_id': transaction_id,
                'sol_received': sol_received,
                'exit_price': current_price,
                'pnl': pnl,
                'tokens_sold': tokens_to_sell
            }
            
        except Exception as e:
            logger.error(f"Sell order failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_token_price(self, token_mint: str) -> Optional[float]:
        """Get current token price from various sources"""
        try:
            # Try DexScreener first
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                if pairs:
                    # Find SOL pair with highest liquidity
                    sol_pairs = [p for p in pairs if p.get('quoteToken', {}).get('symbol') == 'SOL']
                    if sol_pairs:
                        best_pair = max(sol_pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0)))
                        return float(best_pair.get('priceNative', 0))
            
            # Fallback to Jupiter API
            jupiter_url = f"https://price.jup.ag/v4/price?ids={token_mint}"
            response = requests.get(jupiter_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                token_data = data.get('data', {}).get(token_mint)
                if token_data:
                    return float(token_data.get('price', 0))
            
            # If all fails, return None
            return None
            
        except Exception as e:
            logger.error(f"Failed to get token price: {e}")
            return None
    
    async def start_trade_monitoring(self, trade: ActiveTrade):
        """Start monitoring a trade for exit conditions"""
        trade_key = f"{trade.chat_id}_{trade.trade_id}"
        
        # Add to active trades
        if trade.chat_id not in self.active_trades:
            self.active_trades[trade.chat_id] = []
        self.active_trades[trade.chat_id].append(trade)
        
        # Start monitoring task
        task = asyncio.create_task(self._monitor_trade_loop(trade))
        self.monitoring_tasks[trade_key] = task
        
        logger.info(f"Started monitoring trade {trade.trade_id}")
    
    async def _monitor_trade_loop(self, trade: ActiveTrade):
        """Main monitoring loop for a trade"""
        logger.info(f"Monitoring trade {trade.trade_id} for {trade.token_name}")
        
        monitoring_duration = 300  # 5 minutes max monitoring
        check_interval = 10  # Check every 10 seconds
        start_time = time.time()
        
        try:
            while (time.time() - start_time) < monitoring_duration:
                current_price = await self._get_token_price(trade.token_mint)
                
                if not current_price:
                    await asyncio.sleep(check_interval)
                    continue
                
                # Calculate current P&L percentage
                price_change_percent = ((current_price - trade.entry_price) / trade.entry_price) * 100
                
                exit_reason = None
                
                # Check take profit
                if price_change_percent >= trade.take_profit_percent:
                    exit_reason = "Take Profit Hit"
                # Check stop loss
                elif price_change_percent <= -trade.stop_loss_percent:
                    exit_reason = "Stop Loss Hit"
                
                if exit_reason:
                    # Generate automatic sell order for user
                    from wallet_integration import generate_swap_link, WSOL_ADDRESS
                    
                    # Create sell transaction link
                    sell_link = generate_swap_link(
                        input_mint=trade.token_mint,
                        output_mint=WSOL_ADDRESS,
                        amount_sol=None  # User can adjust amount
                    )
                    
                    trade.status = 'exit_triggered'
                    trade.exit_price = current_price
                    trade.exit_time = datetime.now()
                    trade.exit_reason = exit_reason
                    
                    # Calculate potential P&L
                    price_change = ((current_price - trade.entry_price) / trade.entry_price) * 100
                    potential_pnl = trade.trade_amount * (price_change / 100)
                    
                    # Send automated sell notification with transaction link
                    await self._send_exit_notification(
                        trade.chat_id,
                        f"""
🚨 <b>{exit_reason}!</b>

<b>📊 Trade Alert:</b>
🏷️ <b>Token:</b> {trade.token_name} ({trade.token_symbol})
💲 <b>Entry:</b> ${trade.entry_price:.8f}
💲 <b>Current:</b> ${current_price:.8f}
📈 <b>Change:</b> {price_change:+.2f}%
💰 <b>Est. P&L:</b> {potential_pnl:+.4f} SOL

<b>🔗 EXECUTE SELL ORDER:</b>
<a href="{sell_link}">👆 CLICK TO SELL ON JUPITER</a>

<b>⚡ Quick Action Required:</b>
Your {trade.token_name} position has hit your {exit_reason.lower()} target. Click the link above to execute the sell order through Jupiter DEX with Phantom wallet.

<b>🔄 This link will:</b>
• Open Jupiter DEX pre-configured for your token
• Connect to your Phantom wallet  
• Execute the sell transaction
• Convert your tokens back to SOL
                        """
                    )
                    return
                
                await asyncio.sleep(check_interval)
            
            # Timeout reached - exit with current price
            sell_result = await self.execute_sell_order(trade, 100.0)
            
            if sell_result['success']:
                trade.status = 'completed'
                trade.exit_price = sell_result['exit_price']
                trade.exit_time = datetime.now()
                trade.pnl = sell_result['pnl']
                trade.exit_reason = "Timeout (5 min)"
                
                await self._send_trade_notification(trade)
            
        except Exception as e:
            logger.error(f"Trade monitoring failed: {e}")
            trade.status = 'failed'
        
        finally:
            # Clean up
            trade_key = f"{trade.chat_id}_{trade.trade_id}"
            if trade_key in self.monitoring_tasks:
                del self.monitoring_tasks[trade_key]
    
    async def _send_exit_notification(self, chat_id: str, message: str):
        """Send exit signal notification with Jupiter link"""
        from bot import send_message
        send_message(chat_id, message)
    
    async def _send_trade_notification(self, trade: ActiveTrade):
        """Send trade completion notification"""
        from bot import send_message
        
        pnl_percent = (trade.pnl / trade.trade_amount) * 100 if trade.pnl and trade.trade_amount else 0
        emoji = "🎉" if trade.pnl and trade.pnl > 0 else "📉" if trade.pnl and trade.pnl < 0 else "⚪"
        
        notification = f"""
{emoji} <b>VIP AUTO-TRADE COMPLETED</b>

<b>🎯 Trade Summary:</b>
🏷️ <b>Token:</b> {trade.token_name} (${trade.token_symbol})
💰 <b>Entry:</b> ${trade.entry_price:.8f}
💰 <b>Exit:</b> ${trade.exit_price:.8f}
💵 <b>Amount:</b> {trade.trade_amount:.3f} SOL
📊 <b>P&L:</b> {trade.pnl:+.3f} SOL ({pnl_percent:+.1f}%)
🎯 <b>Exit:</b> {trade.exit_reason}
⏱️ <b>Duration:</b> {(trade.exit_time - trade.entry_time).total_seconds():.0f if trade.exit_time and trade.entry_time else 0}s

<b>🐕 VIP FETCH Results:</b>
{"🚀 Successful snipe! Great timing!" if trade.pnl and trade.pnl > 0 else "📉 This one didn't work out, but that's trading!" if trade.pnl and trade.pnl < 0 else "⚪ Neutral result - better safe than sorry!"}

Keep FETCHing those opportunities! 🐕‍🦺
        """
        
        send_message(chat_id, notification)
    
    def get_active_trades(self, chat_id: str) -> List[ActiveTrade]:
        """Get active trades for a user"""
        return self.active_trades.get(chat_id, [])
    
    async def stop_all_trades(self, chat_id: str):
        """Stop all active trades for a user"""
        if chat_id in self.active_trades:
            for trade in self.active_trades[chat_id]:
                trade_key = f"{chat_id}_{trade.trade_id}"
                if trade_key in self.monitoring_tasks:
                    self.monitoring_tasks[trade_key].cancel()
                    del self.monitoring_tasks[trade_key]
            
            del self.active_trades[chat_id]
        
        logger.info(f"Stopped all trades for chat {chat_id}")

# Global trade executor instance
trade_executor = TradeExecutor()