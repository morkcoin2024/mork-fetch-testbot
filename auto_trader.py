"""
Advanced Automated Trading System for Mork F.E.T.C.H Bot
Provides multiple automated trading strategies with Jupiter DEX integration
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from wallet_integration import generate_swap_link, WSOL_ADDRESS

logger = logging.getLogger(__name__)

@dataclass
class AutoTrade:
    """Represents an automated trade setup"""
    trade_id: str
    chat_id: str
    token_mint: str
    token_name: str
    token_symbol: str
    strategy: str  # 'auto_buy', 'auto_sell', 'full_auto'
    trigger_price: float
    amount_sol: float
    stop_loss_percent: float
    take_profit_percent: float
    status: str = 'pending'
    created_time: datetime = None
    executed_time: datetime = None

class AutoTradingEngine:
    """Advanced automated trading engine"""
    
    def __init__(self):
        self.pending_trades: Dict[str, List[AutoTrade]] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.active = True
    
    def add_auto_buy_order(self, chat_id: str, token_mint: str, token_name: str, 
                          trigger_price: float, amount_sol: float, 
                          stop_loss: float, take_profit: float) -> str:
        """Add an automated buy order"""
        trade_id = f"auto_buy_{int(time.time())}"
        
        auto_trade = AutoTrade(
            trade_id=trade_id,
            chat_id=chat_id,
            token_mint=token_mint,
            token_name=token_name,
            token_symbol="TOKEN",
            strategy='auto_buy',
            trigger_price=trigger_price,
            amount_sol=amount_sol,
            stop_loss_percent=stop_loss,
            take_profit_percent=take_profit,
            status='waiting_for_trigger',
            created_time=datetime.now()
        )
        
        if chat_id not in self.pending_trades:
            self.pending_trades[chat_id] = []
        self.pending_trades[chat_id].append(auto_trade)
        
        # Start monitoring task
        task = asyncio.create_task(self._monitor_auto_trade(auto_trade))
        self.monitoring_tasks[f"{chat_id}_{trade_id}"] = task
        
        logger.info(f"Added auto-buy order: {trade_id} for {token_name}")
        return trade_id
    
    def add_auto_sell_order(self, chat_id: str, token_mint: str, token_name: str, 
                           trigger_price: float, amount_sol: float) -> str:
        """Add an automated sell order"""
        trade_id = f"auto_sell_{int(time.time())}"
        
        auto_trade = AutoTrade(
            trade_id=trade_id,
            chat_id=chat_id,
            token_mint=token_mint,
            token_name=token_name,
            token_symbol="TOKEN",
            strategy='auto_sell',
            trigger_price=trigger_price,
            amount_sol=amount_sol,
            stop_loss_percent=0,
            take_profit_percent=0,
            status='waiting_for_trigger',
            created_time=datetime.now()
        )
        
        if chat_id not in self.pending_trades:
            self.pending_trades[chat_id] = []
        self.pending_trades[chat_id].append(auto_trade)
        
        # Start monitoring task
        task = asyncio.create_task(self._monitor_auto_trade(auto_trade))
        self.monitoring_tasks[f"{chat_id}_{trade_id}"] = task
        
        logger.info(f"Added auto-sell order: {trade_id} for {token_name}")
        return trade_id
    
    async def _monitor_auto_trade(self, auto_trade: AutoTrade):
        """Monitor automated trade for trigger conditions"""
        from trade_executor import TradeExecutor
        
        executor = TradeExecutor()
        check_interval = 5  # Check every 5 seconds
        max_duration = 1800  # 30 minutes max monitoring
        start_time = time.time()
        
        try:
            while (time.time() - start_time) < max_duration and self.active:
                current_price = await executor._get_token_price(auto_trade.token_mint)
                
                if not current_price:
                    await asyncio.sleep(check_interval)
                    continue
                
                # Check trigger conditions
                triggered = False
                
                if auto_trade.strategy == 'auto_buy':
                    # Buy when price drops to or below trigger price
                    if current_price <= auto_trade.trigger_price:
                        triggered = True
                        await self._execute_auto_buy(auto_trade, current_price)
                
                elif auto_trade.strategy == 'auto_sell':
                    # Sell when price rises to or above trigger price
                    if current_price >= auto_trade.trigger_price:
                        triggered = True
                        await self._execute_auto_sell(auto_trade, current_price)
                
                if triggered:
                    auto_trade.status = 'triggered'
                    auto_trade.executed_time = datetime.now()
                    break
                
                await asyncio.sleep(check_interval)
            
            # Timeout or stopped
            if auto_trade.status == 'waiting_for_trigger':
                auto_trade.status = 'expired'
                await self._send_expiry_notification(auto_trade)
        
        except Exception as e:
            logger.error(f"Auto-trade monitoring failed: {e}")
            auto_trade.status = 'failed'
        
        finally:
            # Clean up
            trade_key = f"{auto_trade.chat_id}_{auto_trade.trade_id}"
            if trade_key in self.monitoring_tasks:
                del self.monitoring_tasks[trade_key]
    
    async def _execute_auto_buy(self, auto_trade: AutoTrade, current_price: float):
        """Execute automatic buy order"""
        # Generate Jupiter buy link
        buy_link = generate_swap_link(
            input_mint=WSOL_ADDRESS,
            output_mint=auto_trade.token_mint,
            amount_sol=auto_trade.amount_sol
        )
        
        notification = f"""
🚀 <b>AUTO-BUY TRIGGERED!</b>

<b>📊 Buy Signal:</b>
🏷️ <b>Token:</b> {auto_trade.token_name}
💲 <b>Target Price:</b> ${auto_trade.trigger_price:.8f}
💲 <b>Current Price:</b> ${current_price:.8f}
💰 <b>Amount:</b> {auto_trade.amount_sol} SOL

<b>🔗 EXECUTE BUY ORDER:</b>
<a href="{buy_link}">👆 CLICK TO BUY ON JUPITER</a>

<b>⚡ Your auto-buy order is ready!</b>
The price dropped to your target. Click the link above to execute the buy through Jupiter DEX with Phantom wallet.

<b>🔄 After buying:</b>
• Use /executed to set up monitoring
• Set stop-loss: {auto_trade.stop_loss_percent}%
• Set take-profit: {auto_trade.take_profit_percent}%
        """
        
        await self._send_notification(auto_trade.chat_id, notification)
    
    async def _execute_auto_sell(self, auto_trade: AutoTrade, current_price: float):
        """Execute automatic sell order"""
        # Generate Jupiter sell link
        sell_link = generate_swap_link(
            input_mint=auto_trade.token_mint,
            output_mint=WSOL_ADDRESS,
            amount_sol=None
        )
        
        notification = f"""
📈 <b>AUTO-SELL TRIGGERED!</b>

<b>📊 Sell Signal:</b>
🏷️ <b>Token:</b> {auto_trade.token_name}
💲 <b>Target Price:</b> ${auto_trade.trigger_price:.8f}
💲 <b>Current Price:</b> ${current_price:.8f}

<b>🔗 EXECUTE SELL ORDER:</b>
<a href="{sell_link}">👆 CLICK TO SELL ON JUPITER</a>

<b>⚡ Your auto-sell order is ready!</b>
The price rose to your target. Click the link above to execute the sell through Jupiter DEX with Phantom wallet.
        """
        
        await self._send_notification(auto_trade.chat_id, notification)
    
    async def _send_expiry_notification(self, auto_trade: AutoTrade):
        """Send notification when auto-trade expires"""
        notification = f"""
⏰ <b>AUTO-TRADE EXPIRED</b>

<b>📊 Order Details:</b>
🏷️ <b>Token:</b> {auto_trade.token_name}
📈 <b>Strategy:</b> {auto_trade.strategy.replace('_', '-').title()}
💲 <b>Target Price:</b> ${auto_trade.trigger_price:.8f}
⏱️ <b>Duration:</b> 30 minutes

The price never reached your target level. You can create a new auto-trade order anytime.
        """
        
        await self._send_notification(auto_trade.chat_id, notification)
    
    async def _send_notification(self, chat_id: str, message: str):
        """Send notification to user"""
        from bot import send_message
        send_message(chat_id, message)
    
    def get_pending_trades(self, chat_id: str) -> List[AutoTrade]:
        """Get pending auto-trades for a user"""
        return self.pending_trades.get(chat_id, [])
    
    def cancel_auto_trade(self, chat_id: str, trade_id: str) -> bool:
        """Cancel a pending auto-trade"""
        if chat_id in self.pending_trades:
            for trade in self.pending_trades[chat_id]:
                if trade.trade_id == trade_id:
                    trade.status = 'cancelled'
                    
                    # Cancel monitoring task
                    task_key = f"{chat_id}_{trade_id}"
                    if task_key in self.monitoring_tasks:
                        self.monitoring_tasks[task_key].cancel()
                        del self.monitoring_tasks[task_key]
                    
                    # Remove from pending
                    self.pending_trades[chat_id].remove(trade)
                    return True
        return False

# Global auto-trading engine instance
auto_trading_engine = AutoTradingEngine()