#!/usr/bin/env python3
"""
Simple, direct monitoring script
"""
import time
import requests
from app import app
from models import db, UserSession
from wallet_integration import SolanaWalletIntegrator, generate_swap_link, WSOL_ADDRESS

BOT_TOKEN = '8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824'

def send_notification(chat_id, message):
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        response = requests.post(url, json={'chat_id': chat_id, 'text': message}, timeout=10)
        return response.status_code == 200
    except:
        return False

def monitor_once():
    integrator = SolanaWalletIntegrator()
    
    with app.app_context():
        session = UserSession.query.filter_by(chat_id='1653046781', state='monitoring').first()
        
        if not session:
            print("No monitoring session found")
            return False
        
        current_price = integrator.get_token_price_in_sol(session.contract_address)
        if not current_price:
            print("Could not get price")
            return False
        
        change_percent = ((current_price - session.entry_price) / session.entry_price) * 100
        
        print(f"Entry: {session.entry_price:.10f}, Current: {current_price:.10f}, Change: {change_percent:+.2f}%")
        
        triggered = False
        if change_percent <= -0.5:
            sell_link = generate_swap_link(session.contract_address, WSOL_ADDRESS, None)
            message = f"""🔴 STOP LOSS TRIGGERED!

Entry: {session.entry_price:.10f} SOL
Current: {current_price:.10f} SOL
Change: {change_percent:+.2f}%

{sell_link}"""
            triggered = True
            
        elif change_percent >= 0.5:
            sell_link = generate_swap_link(session.contract_address, WSOL_ADDRESS, None)
            message = f"""🟢 TAKE PROFIT TRIGGERED!

Entry: {session.entry_price:.10f} SOL
Current: {current_price:.10f} SOL
Change: {change_percent:+.2f}%

{sell_link}"""
            triggered = True
        
        if triggered:
            success = send_notification(session.chat_id, message)
            print(f"TRIGGERED! Notification sent: {success}")
            if success:
                session.state = 'idle'
                db.session.commit()
            return True
        
        return False

if __name__ == "__main__":
    print("Starting simple monitor...")
    while True:
        try:
            monitor_once()
            time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)