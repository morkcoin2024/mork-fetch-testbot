#!/usr/bin/env python3
"""
Automated Pump.fun Trading System
Handles fully automated trading with burner wallets, real-time monitoring, and automatic buy/sell execution.
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutomatedPumpTrader:
    """Handles fully automated pump.fun trading with burner wallets"""
    
    def __init__(self):
        self.active_trades = {}  # chat_id -> list of active trades
        self.monitoring_tasks = {}  # chat_id -> asyncio tasks
        
    async def execute_automated_trading(self, chat_id: str, burner_wallet: Dict, trade_amount_sol: float) -> Dict:
        """Execute fully automated pump.fun trading"""
        try:
            logger.info(f"Starting automated trading for user {chat_id} with {trade_amount_sol} SOL")
            
            # Step 1: Identify good tokens
            good_tokens = await self.identify_good_tokens()
            
            if not good_tokens:
                return {
                    'success': False,
                    'error': 'No suitable tokens found for trading',
                    'message': 'Scanner found no tokens meeting safety criteria'
                }
            
            # Step 2: Execute buy transactions
            trades_executed = []
            
            for token in good_tokens[:3]:  # Trade top 3 tokens
                trade_result = await self.execute_buy_transaction(
                    chat_id, burner_wallet, token, trade_amount_sol / 3
                )
                
                if trade_result['success']:
                    trades_executed.append(trade_result)
                    
                    # Step 3: Start real-time monitoring
                    await self.start_trade_monitoring(chat_id, trade_result)
            
            if trades_executed:
                # Store active trades
                self.active_trades[chat_id] = trades_executed
                
                return {
                    'success': True,
                    'trades': trades_executed,
                    'message': f'Successfully executed {len(trades_executed)} automated trades'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to execute any trades',
                    'message': 'All buy transactions failed'
                }
                
        except Exception as e:
            logger.error(f"Automated trading failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Automated trading system error'
            }
    
    async def identify_good_tokens(self) -> List[Dict]:
        """Identify good tokens based on pump.fun logic"""
        try:
            # Import our token scanning modules
            from pump_scanner import PumpFunScanner
            from advanced_pump_rules import AdvancedPumpRules
            
            good_tokens = []
            
            # Scan for fresh tokens
            async with PumpFunScanner() as scanner:
                candidates = await scanner.get_token_candidates(min_safety_score=35)
                
                if candidates:
                    # Apply advanced rules
                    rules_engine = AdvancedPumpRules()
                    
                    for candidate in candidates:
                        # Convert to dict if needed
                        if hasattr(candidate, 'to_dict'):
                            token_data = candidate.to_dict()
                        else:
                            token_data = candidate
                            
                        # Apply trading logic
                        is_good = await self.evaluate_token_for_trading(token_data, rules_engine)
                        
                        if is_good:
                            good_tokens.append(token_data)
                            
                        # Limit to top candidates
                        if len(good_tokens) >= 5:
                            break
            
            logger.info(f"Identified {len(good_tokens)} good tokens for trading")
            return good_tokens
            
        except Exception as e:
            logger.error(f"Token identification failed: {e}")
            return []
    
    async def evaluate_token_for_trading(self, token_data: Dict, rules_engine) -> bool:
        """Evaluate if token is good for automated trading"""
        try:
            # Basic safety checks
            safety_score = token_data.get('safety_score', 0)
            if safety_score < 35:
                return False
            
            # Market cap check
            market_cap = token_data.get('market_cap', 0)
            if market_cap < 1000 or market_cap > 50000:  # Sweet spot: $1K-50K
                return False
            
            # Age check (prefer fresh but not too fresh)
            age_minutes = token_data.get('age_minutes', 0)
            if age_minutes < 5 or age_minutes > 60:  # 5-60 minutes old
                return False
            
            # Volume check
            volume_24h = token_data.get('volume_24h', 0)
            if volume_24h < 500:  # Minimum $500 volume
                return False
            
            # Apply advanced rules
            if hasattr(rules_engine, 'evaluate_token'):
                advanced_score = rules_engine.evaluate_token(token_data)
                if advanced_score < 60:  # Minimum 60/100 score
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Token evaluation failed: {e}")
            return False
    
    async def execute_buy_transaction(self, chat_id: str, burner_wallet: Dict, token: Dict, amount_sol: float) -> Dict:
        """Execute buy transaction using smart platform routing"""
        try:
            token_symbol = token.get('symbol', 'TOKEN')
            logger.info(f"Executing smart trade for {token_symbol} with {amount_sol} SOL")
            
            # Import smart trading router
            from smart_trading_router import smart_trading_router
            
            # Get private key from burner wallet
            private_key = burner_wallet.get('private_key') or burner_wallet.get('private_key_encrypted')
            
            if not private_key:
                return {
                    'success': False,
                    'error': 'Private key not found in burner wallet'
                }
            
            # Execute smart trade (automatically routes to Pump.fun or Jupiter)
            result = await smart_trading_router.execute_smart_trade(
                private_key=private_key,
                token_mint=token.get('mint', ''),
                token_symbol=token_symbol,
                sol_amount=amount_sol,
                trade_type="buy"
            )
            
            if result.get('success'):
                # Store trade information
                trade_info = {
                    'trade_id': f"{chat_id}_{token.get('mint', '')}_{int(time.time())}",
                    'token_mint': token.get('mint', ''),
                    'token_symbol': token.get('symbol', 'TOKEN'),
                    'token_name': token.get('name', 'Unknown'),
                    'buy_price': result.get('price', 0),
                    'amount_sol': amount_sol,
                    'buy_time': datetime.now(),
                    'profit_target': 2.0,  # 2x profit target
                    'stop_loss': 0.6,      # -40% stop loss
                    'status': 'active',
                    'burner_wallet': burner_wallet['public_key']
                }
                
                logger.info(f"Buy transaction successful: {trade_info['trade_id']}")
                return {
                    'success': True,
                    'trade_info': trade_info,
                    'transaction': result
                }
            else:
                logger.error(f"Buy transaction failed: {result.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Buy transaction failed')
                }
                
        except Exception as e:
            logger.error(f"Buy transaction execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def start_trade_monitoring(self, chat_id: str, trade_result: Dict):
        """Start real-time monitoring for a trade"""
        try:
            trade_info = trade_result['trade_info']
            trade_id = trade_info['trade_id']
            
            logger.info(f"Starting monitoring for trade {trade_id}")
            
            # Create monitoring task
            task = asyncio.create_task(
                self.monitor_trade_realtime(chat_id, trade_info)
            )
            
            # Store task
            if chat_id not in self.monitoring_tasks:
                self.monitoring_tasks[chat_id] = []
            self.monitoring_tasks[chat_id].append(task)
            
        except Exception as e:
            logger.error(f"Failed to start trade monitoring: {e}")
    
    async def monitor_trade_realtime(self, chat_id: str, trade_info: Dict):
        """Monitor trade in real-time and execute sell when conditions are met"""
        try:
            trade_id = trade_info['trade_id']
            token_mint = trade_info['token_mint']
            buy_price = trade_info['buy_price']
            profit_target = trade_info['profit_target']
            stop_loss = trade_info['stop_loss']
            
            logger.info(f"Monitoring trade {trade_id} - Target: {profit_target}x, Stop: {stop_loss}x")
            
            start_time = time.time()
            max_monitoring_time = 300  # 5 minutes maximum
            
            while time.time() - start_time < max_monitoring_time:
                try:
                    # Get current price
                    current_price = await self.get_current_token_price(token_mint)
                    
                    if current_price and buy_price:
                        price_ratio = current_price / buy_price
                        
                        # Check profit target
                        if price_ratio >= profit_target:
                            logger.info(f"Profit target hit for {trade_id}: {price_ratio:.2f}x")
                            await self.execute_sell_transaction(chat_id, trade_info, 'profit_target')
                            break
                        
                        # Check stop loss
                        elif price_ratio <= stop_loss:
                            logger.info(f"Stop loss triggered for {trade_id}: {price_ratio:.2f}x")
                            await self.execute_sell_transaction(chat_id, trade_info, 'stop_loss')
                            break
                        
                        # Log current status
                        if int(time.time()) % 30 == 0:  # Every 30 seconds
                            logger.info(f"Trade {trade_id} monitoring: {price_ratio:.2f}x")
                    
                    # Wait before next check
                    await asyncio.sleep(5)  # Check every 5 seconds
                    
                except Exception as e:
                    logger.error(f"Error during trade monitoring: {e}")
                    await asyncio.sleep(10)  # Wait longer on error
            
            # If we reach here, monitoring timed out
            logger.info(f"Monitoring timeout for trade {trade_id}, executing emergency sell")
            await self.execute_sell_transaction(chat_id, trade_info, 'timeout')
            
        except Exception as e:
            logger.error(f"Trade monitoring failed: {e}")
    
    async def get_current_token_price(self, token_mint: str) -> Optional[float]:
        """Get current token price"""
        try:
            # Import price checking modules
            from wallet_integration import SolanaWalletIntegrator
            
            integrator = SolanaWalletIntegrator()
            price = integrator.get_token_price_in_sol(token_mint)
            
            return price if price and price > 0 else None
            
        except Exception as e:
            logger.error(f"Failed to get token price: {e}")
            return None
    
    async def execute_sell_transaction(self, chat_id: str, trade_info: Dict, reason: str):
        """Execute sell transaction"""
        try:
            trade_id = trade_info['trade_id']
            token_mint = trade_info['token_mint']
            
            logger.info(f"Executing sell transaction for {trade_id}, reason: {reason}")
            
            # Import burner wallet system
            from burner_wallet_system import BurnerWalletSystem
            
            wallet_system = BurnerWalletSystem()
            
            # Execute the sell trade
            result = await wallet_system.execute_burner_trade(
                chat_id, 
                token_mint, 
                0,  # Sell all tokens
                'sell'
            )
            
            if result.get('success'):
                # Calculate profit/loss
                buy_price = trade_info.get('buy_price', 0)
                sell_price = result.get('price', 0)
                profit_ratio = sell_price / buy_price if buy_price else 0
                
                # Send notification
                await self.send_trade_notification(chat_id, trade_info, result, reason, profit_ratio)
                
                logger.info(f"Sell transaction successful for {trade_id}: {profit_ratio:.2f}x")
            else:
                logger.error(f"Sell transaction failed for {trade_id}: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Sell transaction execution failed: {e}")
    
    async def send_trade_notification(self, chat_id: str, trade_info: Dict, sell_result: Dict, reason: str, profit_ratio: float):
        """Send trade completion notification to user"""
        try:
            from bot import send_message
            
            token_symbol = trade_info.get('token_symbol', 'TOKEN')
            amount_sol = trade_info.get('amount_sol', 0)
            
            # Determine message based on outcome
            if profit_ratio >= 1.5:
                outcome = "🚀 PROFIT"
                emoji = "💰"
            elif profit_ratio >= 1.0:
                outcome = "✅ PROFIT"
                emoji = "📈"
            else:
                outcome = "📉 LOSS"
                emoji = "🛡️"
            
            message = f"""
{emoji} <b>AUTOMATED TRADE COMPLETE</b>

<b>🎯 Trade Summary:</b>
🏷️ <b>Token:</b> {token_symbol}
💵 <b>Investment:</b> {amount_sol:.3f} SOL
📊 <b>Result:</b> {profit_ratio:.2f}x ({outcome})
🔄 <b>Trigger:</b> {reason.replace('_', ' ').title()}

<b>⚡ Fully automated execution!</b>
Bot handled everything from buy to sell automatically.

<b>💼 Burner Wallet:</b> {trade_info.get('burner_wallet', '')[:8]}...

{f'<b>🎉 Profit secured!</b>' if profit_ratio > 1.0 else '<b>🛡️ Loss minimized by stop-loss</b>'}
            """
            
            send_message(chat_id, message)
            
        except Exception as e:
            logger.error(f"Failed to send trade notification: {e}")
    
    def stop_monitoring(self, chat_id: str):
        """Stop all monitoring tasks for a user"""
        try:
            if chat_id in self.monitoring_tasks:
                for task in self.monitoring_tasks[chat_id]:
                    if not task.done():
                        task.cancel()
                del self.monitoring_tasks[chat_id]
                
            if chat_id in self.active_trades:
                del self.active_trades[chat_id]
                
            logger.info(f"Stopped monitoring for user {chat_id}")
            
        except Exception as e:
            logger.error(f"Failed to stop monitoring: {e}")

# Global instance
automated_trader = AutomatedPumpTrader()

# Export functions for use in bot
async def start_automated_trading(chat_id: str, burner_wallet: Dict, trade_amount_sol: float) -> Dict:
    """Start automated trading for a user"""
    return await automated_trader.execute_automated_trading(chat_id, burner_wallet, trade_amount_sol)

def stop_automated_trading(chat_id: str):
    """Stop automated trading for a user"""
    automated_trader.stop_monitoring(chat_id)

def get_active_trades(chat_id: str) -> List[Dict]:
    """Get active trades for a user"""
    return automated_trader.active_trades.get(chat_id, [])