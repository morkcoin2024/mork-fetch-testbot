#!/usr/bin/env python3
"""
Continuous Background Monitoring Service for MORK F.E.T.C.H Bot
Runs persistently to monitor price changes and send real-time notifications
"""

import asyncio
import logging
import time
from datetime import datetime
import requests
import os
from app import app
from models import db, UserSession
from trade_executor import trade_executor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def send_telegram_notification(chat_id: str, message: str):
    """Send Telegram notification"""
    try:
        data = {
            'chat_id': chat_id,
            'text': message.strip(),
            'parse_mode': 'HTML'
        }
        
        response = requests.post(f'{TELEGRAM_API_URL}/sendMessage', json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"Notification sent successfully to {chat_id}")
            return True
        else:
            logger.error(f"Failed to send notification: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {e}")
        return False

async def monitor_active_sessions():
    """Main monitoring loop for all active sessions"""
    logger.info("Starting continuous monitoring service...")
    
    while True:
        try:
            with app.app_context():
                # Get all monitoring sessions
                sessions = UserSession.query.filter_by(state='monitoring').all()
                
                if not sessions:
                    logger.info("No active monitoring sessions")
                    await asyncio.sleep(30)  # Check every 30 seconds when no active sessions
                    continue
                
                for session in sessions:
                    if not session.contract_address or not session.entry_price:
                        continue
                    
                    try:
                        # Get current price
                        current_price = await trade_executor._get_token_price(session.contract_address)
                        
                        if not current_price or current_price <= 0:
                            logger.warning(f"Could not get price for {session.token_symbol}")
                            continue
                        
                        # Calculate change percentage
                        change_percent = ((current_price - session.entry_price) / session.entry_price) * 100
                        
                        logger.info(f"Monitoring {session.token_symbol} (Chat {session.chat_id}): "
                                  f"Entry={session.entry_price:.10f}, Current={current_price:.10f}, "
                                  f"Change={change_percent:+.2f}%")
                        
                        # Check stop loss trigger (-3%)
                        if change_percent <= -session.stop_loss:
                            logger.info(f"🔴 STOP LOSS TRIGGERED for {session.token_symbol}! "
                                      f"Price down {abs(change_percent):.2f}%")
                            
                            # Generate sell link
                            from wallet_integration import generate_swap_link, WSOL_ADDRESS
                            sell_link = generate_swap_link(
                                input_mint=session.contract_address,
                                output_mint=WSOL_ADDRESS,
                                amount_sol=None
                            )
                            
                            message = f"""
🚨 <b>STOP LOSS TRIGGERED!</b>

<b>📊 {session.token_name} Alert:</b>
💲 <b>Entry Price:</b> {session.entry_price:.10f} SOL
💲 <b>Current Price:</b> {current_price:.10f} SOL
📉 <b>Change:</b> {change_percent:.2f}%
🔴 <b>Threshold:</b> -{session.stop_loss}%

<b>⚡ INSTANT SELL:</b>
<a href="{sell_link}">🔗 Execute Sell Order via Jupiter</a>

Your sensitive monitoring detected the price drop!
                            """
                            
                            # Send notification
                            success = await send_telegram_notification(session.chat_id, message)
                            if success:
                                # Stop monitoring after trigger
                                session.state = 'idle'
                                db.session.commit()
                                logger.info(f"Session {session.chat_id} monitoring stopped after stop-loss trigger")
                        
                        # Check take profit trigger (+3%)
                        elif change_percent >= session.take_profit:
                            logger.info(f"🟢 TAKE PROFIT TRIGGERED for {session.token_symbol}! "
                                      f"Price up {change_percent:.2f}%")
                            
                            # Generate sell link  
                            from wallet_integration import generate_swap_link, WSOL_ADDRESS
                            sell_link = generate_swap_link(
                                input_mint=session.contract_address,
                                output_mint=WSOL_ADDRESS,
                                amount_sol=None
                            )
                            
                            message = f"""
🎉 <b>TAKE PROFIT TRIGGERED!</b>

<b>📊 {session.token_name} Alert:</b>
💲 <b>Entry Price:</b> {session.entry_price:.10f} SOL
💲 <b>Current Price:</b> {current_price:.10f} SOL
📈 <b>Change:</b> {change_percent:.2f}%
🟢 <b>Threshold:</b> +{session.take_profit}%

<b>⚡ INSTANT SELL:</b>
<a href="{sell_link}">🔗 Execute Sell Order via Jupiter</a>

Time to secure those profits!
                            """
                            
                            # Send notification
                            success = await send_telegram_notification(session.chat_id, message)
                            if success:
                                # Stop monitoring after trigger
                                session.state = 'idle'
                                db.session.commit()
                                logger.info(f"Session {session.chat_id} monitoring stopped after take-profit trigger")
                        
                        # Log significant movements that haven't triggered yet
                        elif abs(change_percent) >= 1.0:
                            logger.info(f"📊 Significant movement for {session.token_symbol}: "
                                      f"{change_percent:+.2f}% (watching for ±{session.stop_loss}%)")
                    
                    except Exception as e:
                        logger.error(f"Error monitoring session {session.chat_id}: {e}")
            
            # Wait 10 seconds before next check
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.error(f"Critical monitoring error: {e}")
            await asyncio.sleep(30)  # Wait longer on critical errors

async def main():
    """Main entry point"""
    logger.info("MORK F.E.T.C.H Bot Monitoring Service Starting...")
    logger.info("Sensitive thresholds: ±3% for stop-loss/take-profit")
    
    # Test notification system
    with app.app_context():
        test_session = UserSession.query.filter_by(chat_id='1653046781').first()
        if test_session:
            test_message = """
🤖 <b>MONITORING SERVICE ACTIVATED</b>

Sensitive monitoring is now running with ±3% thresholds:

📊 <b>Your MORK Position:</b>
💲 Entry: {:.10f} SOL
🔴 Stop Loss: -{:.1f}% (at {:.10f} SOL)  
🟢 Take Profit: +{:.1f}% (at {:.10f} SOL)

⚡ <b>Ready to detect your trades!</b>
Try another $100+ sell/buy to test the system.
            """.format(
                test_session.entry_price,
                test_session.stop_loss,
                test_session.entry_price * (1 - test_session.stop_loss/100),
                test_session.take_profit,
                test_session.entry_price * (1 + test_session.take_profit/100)
            )
            
            await send_telegram_notification(test_session.chat_id, test_message)
    
    # Start continuous monitoring
    await monitor_active_sessions()

if __name__ == "__main__":
    asyncio.run(main())