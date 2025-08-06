#!/usr/bin/env python3
"""
Stable monitoring service that stays running
"""
import time
import requests
import logging
import sys
from app import app
from models import db, UserSession
from wallet_integration import SolanaWalletIntegrator, generate_swap_link, WSOL_ADDRESS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = '8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824'

def send_notification(chat_id, message):
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        response = requests.post(url, json={'chat_id': chat_id, 'text': message}, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Notification error: {e}")
        return False

def monitor_session():
    integrator = SolanaWalletIntegrator()
    
    with app.app_context():
        session = UserSession.query.filter_by(chat_id='1653046781', state='monitoring').first()
        
        if not session:
            logger.info("No active monitoring session")
            return False
        
        try:
            current_price = integrator.get_token_price_in_sol(session.contract_address)
            if not current_price:
                logger.warning("Could not get price")
                return False
            
            change_percent = ((current_price - session.entry_price) / session.entry_price) * 100
            
            logger.info(f"MORK Monitor - Entry: {session.entry_price:.10f}, Current: {current_price:.10f}, Change: {change_percent:+.2f}%, Threshold: ±{session.take_profit}%")
            
            # Check triggers
            if change_percent <= -session.stop_loss:
                sell_link = generate_swap_link(session.contract_address, WSOL_ADDRESS, None)
                message = f"""🔴 STOP LOSS TRIGGERED!

Entry: {session.entry_price:.10f} SOL
Current: {current_price:.10f} SOL
Change: {change_percent:+.2f}%

{sell_link}"""
                
                logger.info("STOP LOSS TRIGGERED - Sending notification")
                success = send_notification(session.chat_id, message)
                if success:
                    session.state = 'idle'
                    db.session.commit()
                    logger.info("Session reset after successful notification")
                return True
                
            elif change_percent >= session.take_profit:
                sell_link = generate_swap_link(session.contract_address, WSOL_ADDRESS, None)
                message = f"""🟢 TAKE PROFIT TRIGGERED!

Entry: {session.entry_price:.10f} SOL
Current: {current_price:.10f} SOL
Change: {change_percent:+.2f}%

{sell_link}"""
                
                logger.info("TAKE PROFIT TRIGGERED - Sending notification")
                success = send_notification(session.chat_id, message)
                if success:
                    session.state = 'idle'
                    db.session.commit()
                    logger.info("Session reset after successful notification")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            return False

def main():
    logger.info("Starting stable monitoring service...")
    
    while True:
        try:
            monitor_session()
            time.sleep(3)  # Check every 3 seconds
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Monitoring loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()