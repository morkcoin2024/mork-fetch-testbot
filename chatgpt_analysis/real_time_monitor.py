#!/usr/bin/env python3
"""
Real-time monitoring service that runs continuously
"""
import asyncio
import logging
import time
import requests
import os
from app import app
from models import db, UserSession
from wallet_integration import SolanaWalletIntegrator, generate_swap_link, WSOL_ADDRESS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = '8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824'

async def send_notification(chat_id, message):
    """Send Telegram notification"""
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ Notification sent to {chat_id}")
            return True
        else:
            logger.error(f"❌ Failed to send: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Notification error: {e}")
        return False

async def monitor_loop():
    """Main monitoring loop"""
    logger.info("🚀 Starting real-time monitoring service...")
    integrator = SolanaWalletIntegrator()
    
    while True:
        try:
            with app.app_context():
                sessions = UserSession.query.filter_by(state='monitoring').all()
                
                if not sessions:
                    logger.info("⏳ No active sessions, checking again in 10 seconds...")
                    await asyncio.sleep(10)
                    continue
                
                for session in sessions:
                    if not session.contract_address or not session.entry_price:
                        continue
                    
                    # Get current price
                    current_price = integrator.get_token_price_in_sol(session.contract_address)
                    
                    if not current_price or current_price <= 0:
                        logger.warning(f"⚠️ Could not get price for {session.contract_address}")
                        continue
                    
                    # Calculate change
                    change_percent = ((current_price - session.entry_price) / session.entry_price) * 100
                    
                    logger.info(f"📊 {session.contract_address[:8]}... | "
                              f"Entry: {session.entry_price:.10f} | "
                              f"Current: {current_price:.10f} | "
                              f"Change: {change_percent:+.2f}%")
                    
                    # Check triggers
                    triggered = False
                    message = ""
                    
                    if change_percent <= -session.stop_loss:
                        # Stop loss triggered
                        sell_link = generate_swap_link(session.contract_address, WSOL_ADDRESS, None)
                        message = f"""🔴 STOP LOSS TRIGGERED!

📊 MORK Alert:
💲 Entry: {session.entry_price:.10f} SOL
💲 Current: {current_price:.10f} SOL
📉 Change: {change_percent:+.2f}%
🔴 Threshold: -{session.stop_loss}%

⚡ INSTANT SELL:
{sell_link}"""
                        triggered = True
                        
                    elif change_percent >= session.take_profit:
                        # Take profit triggered
                        sell_link = generate_swap_link(session.contract_address, WSOL_ADDRESS, None)
                        message = f"""🟢 TAKE PROFIT TRIGGERED!

📊 MORK Alert:
💲 Entry: {session.entry_price:.10f} SOL
💲 Current: {current_price:.10f} SOL
📈 Change: {change_percent:+.2f}%
🟢 Threshold: +{session.take_profit}%

⚡ INSTANT SELL:
{sell_link}"""
                        triggered = True
                    
                    if triggered:
                        logger.info(f"🚨 TRIGGER DETECTED! Sending notification...")
                        success = await send_notification(session.chat_id, message)
                        
                        if success:
                            # Reset session to idle after notification
                            session.state = 'idle'
                            db.session.commit()
                            logger.info(f"✅ Session reset to idle after successful notification")
                        
                        break  # Exit session loop after first trigger
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except Exception as e:
            logger.error(f"❌ Monitor loop error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(monitor_loop())