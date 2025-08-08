import os
import re
import logging
import requests
import json
import random
from datetime import datetime
from flask import current_app
from sqlalchemy import func

# Bot configuration - USES ENVIRONMENT VARIABLE FOR TEST BOT
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
BOT_USERNAME = "@MorkSniperTestBot"  # Test bot username

# Command states - Simulation mode
STATE_IDLE = "idle"
STATE_WAITING_CONTRACT = "waiting_contract"
STATE_WAITING_AMOUNT = "waiting_amount"
STATE_WAITING_STOPLOSS = "waiting_stoploss"
STATE_WAITING_TAKEPROFIT = "waiting_takeprofit"
STATE_WAITING_SELLPERCENT = "waiting_sellpercent"
STATE_READY_TO_CONFIRM = "ready_to_confirm"

# Live trading states
STATE_WAITING_WALLET = "waiting_wallet"
STATE_LIVE_WAITING_CONTRACT = "live_waiting_contract"
STATE_LIVE_WAITING_AMOUNT = "live_waiting_amount"
STATE_LIVE_WAITING_TOKEN_COUNT = "live_waiting_token_count"
STATE_LIVE_WAITING_STOPLOSS = "live_waiting_stoploss"
STATE_LIVE_WAITING_TAKEPROFIT = "live_waiting_takeprofit"
STATE_LIVE_WAITING_SELLPERCENT = "live_waiting_sellpercent"
STATE_LIVE_READY_TO_CONFIRM = "live_ready_to_confirm"

# Auto-trading selection states
STATE_TRADING_MODE_SELECTION = "trading_mode_selection"

# Mork token contract address
MORK_TOKEN_CONTRACT = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"

# Risk disclaimer for TEST environment
TRADING_DISCLAIMER = "\n\n<i>🧪 TEST ENVIRONMENT: This is the test bot. No real trades will be executed. Use for testing only.</i>"

def send_message(chat_id, text, reply_markup=None):
    """Send a message to a Telegram chat"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        if isinstance(reply_markup, dict):
            data['reply_markup'] = json.dumps(reply_markup)
        else:
            data['reply_markup'] = reply_markup
    
    try:
        response = requests.post(url, json=data)
        return response.json()
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return None

def get_or_create_session(chat_id):
    """Get or create a user session"""
    from models import UserSession, db
    session = UserSession.query.filter_by(chat_id=str(chat_id)).first()
    if not session:
        session = UserSession()
        session.chat_id = str(chat_id)
        session.state = STATE_IDLE
        db.session.add(session)
        db.session.commit()
        logging.info(f"Chat {chat_id}: Created new session")
    return session

def update_session(chat_id, **kwargs):
    """Update user session data"""
    from models import UserSession, db
    session = get_or_create_session(chat_id)
    for key, value in kwargs.items():
        try:
            setattr(session, key, value)
        except Exception as e:
            if 'token_count' in str(e):
                logging.warning(f"token_count column not available: {e}")
                continue
            else:
                raise e
    db.session.commit()
    logging.info(f"Chat {chat_id}: Updated session - State: {session.state}")
    return session

def handle_start_command(chat_id):
    """Handle /start command"""
    welcome_text = """🐕 <b>Welcome to Mork F.E.T.C.H Test Bot!</b>

🧪 <i>This is the TEST ENVIRONMENT</i>

<b>F.E.T.C.H</b> = <i>Fast Execution, Trade Control Handler</i>

🎯 <b>Available Commands:</b>
/help - Show all commands
/simulate - Practice trading (simulation mode)
/status - Check your session status

<b>🧪 TEST MODE FEATURES:</b>
• Safe environment for testing
• No real money at risk
• Full bot functionality testing
• Isolated from production users

<i>Ready to test your trading strategies?</i>"""

    send_message(chat_id, welcome_text)
    update_session(chat_id, state=STATE_IDLE)

def handle_help_command(chat_id):
    """Handle /help command"""
    help_text = """🤖 <b>Mork F.E.T.C.H Test Bot Commands</b>

🧪 <b>TEST ENVIRONMENT</b>

<b>📊 Basic Commands:</b>
/start - Welcome message
/help - This help menu
/status - Your current session

<b>🎮 Simulation Mode:</b>
/simulate - Practice trading with fake money

<b>ℹ️ Test Bot Info:</b>
• Safe testing environment
• No real transactions
• Same functionality as production
• Perfect for learning and testing

<i>Happy testing! 🐕</i>"""

    send_message(chat_id, help_text)

def handle_simulate_command(chat_id):
    """Handle /simulate command"""
    session = get_or_create_session(chat_id)
    
    simulate_text = """🎮 <b>Simulation Mode - TEST ENVIRONMENT</b>

Practice trading with virtual money! Perfect for learning without risk.

📝 <b>What you'll need:</b>
• Token contract address (Solana/Pump.fun)
• Trade amount (in SOL)
• Stop-loss percentage (e.g., 20)
• Take-profit percentage (e.g., 50)
• Sell percentage (e.g., 100)

<b>🔗 Please enter the token contract address to simulate:</b>

<i>Example: 4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R</i>"""

    send_message(chat_id, simulate_text)
    update_session(chat_id, state=STATE_WAITING_CONTRACT)

def handle_status_command(chat_id):
    """Handle /status command"""
    session = get_or_create_session(chat_id)
    
    status_text = f"""📊 <b>Your Test Session Status</b>

<b>🆔 Chat ID:</b> {chat_id}
<b>🔄 Current State:</b> {session.state}
<b>🕐 Session Created:</b> {session.created_at.strftime('%Y-%m-%d %H:%M UTC')}

<b>🧪 Environment:</b> TEST MODE
<b>🤖 Bot:</b> @MorkSniperTestBot

<i>All activities are simulated - no real trading occurs.</i>"""

    send_message(chat_id, status_text)

def handle_update(update):
    """Main handler for Telegram updates"""
    try:
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            
            if 'text' in message:
                text = message['text'].strip()
                
                # Handle commands
                if text.startswith('/'):
                    command = text.split()[0].lower()
                    if command == '/start':
                        handle_start_command(chat_id)
                    elif command == '/help':
                        handle_help_command(chat_id)
                    elif command == '/simulate':
                        handle_simulate_command(chat_id)
                    elif command == '/status':
                        handle_status_command(chat_id)
                    else:
                        send_message(chat_id, "Unknown command. Type /help for available commands.")
                else:
                    # Handle regular text based on current state
                    session = get_or_create_session(chat_id)
                    handle_text_input(chat_id, text, session.state)
        
        return {'status': 'ok'}
    except Exception as e:
        logging.error(f"Error handling update: {e}")
        return {'status': 'error', 'message': str(e)}

def handle_text_input(chat_id, text, state):
    """Handle text input based on current state"""
    if state == STATE_WAITING_CONTRACT:
        # Validate contract address format
        if len(text) >= 32 and re.match(r'^[A-Za-z0-9]+$', text):
            update_session(chat_id, contract_address=text, state=STATE_WAITING_AMOUNT)
            send_message(chat_id, f"✅ Contract set: <code>{text}</code>\n\n💰 How much SOL do you want to simulate trading?\n\n<i>Example: 0.1</i>")
        else:
            send_message(chat_id, "❌ Invalid contract address format. Please enter a valid Solana address.")
    
    elif state == STATE_WAITING_AMOUNT:
        try:
            amount = float(text)
            if 0 < amount <= 100:  # Reasonable limits for simulation
                update_session(chat_id, trade_amount=amount, state=STATE_WAITING_STOPLOSS)
                send_message(chat_id, f"💰 Trade amount: {amount} SOL\n\n📉 Enter stop-loss percentage:\n\n<i>Example: 20 (for -20%)</i>")
            else:
                send_message(chat_id, "❌ Please enter an amount between 0.001 and 100 SOL.")
        except ValueError:
            send_message(chat_id, "❌ Please enter a valid number for the trade amount.")
    
    elif state == STATE_WAITING_STOPLOSS:
        try:
            stop_loss = float(text)
            if 0 < stop_loss <= 100:
                update_session(chat_id, stop_loss=stop_loss, state=STATE_WAITING_TAKEPROFIT)
                send_message(chat_id, f"📉 Stop-loss: -{stop_loss}%\n\n📈 Enter take-profit percentage:\n\n<i>Example: 50 (for +50%)</i>")
            else:
                send_message(chat_id, "❌ Please enter a percentage between 1 and 100.")
        except ValueError:
            send_message(chat_id, "❌ Please enter a valid number for stop-loss percentage.")
    
    elif state == STATE_WAITING_TAKEPROFIT:
        try:
            take_profit = float(text)
            if 0 < take_profit <= 1000:
                update_session(chat_id, take_profit=take_profit, state=STATE_WAITING_SELLPERCENT)
                send_message(chat_id, f"📈 Take-profit: +{take_profit}%\n\n💼 What percentage to sell at take-profit?\n\n<i>Example: 100 (sell all)</i>")
            else:
                send_message(chat_id, "❌ Please enter a percentage between 1 and 1000.")
        except ValueError:
            send_message(chat_id, "❌ Please enter a valid number for take-profit percentage.")
    
    elif state == STATE_WAITING_SELLPERCENT:
        try:
            sell_percent = float(text)
            if 0 < sell_percent <= 100:
                session = update_session(chat_id, sell_percent=sell_percent, state=STATE_READY_TO_CONFIRM)
                
                # Show confirmation
                confirmation_text = f"""🎮 <b>Simulation Trade Confirmation</b>

<b>📝 Trade Details:</b>
• Contract: <code>{session.contract_address}</code>
• Amount: {session.trade_amount} SOL
• Stop-loss: -{session.stop_loss}%
• Take-profit: +{session.take_profit}%
• Sell amount: {session.sell_percent}%

<b>🧪 This is a SIMULATION - no real trades!</b>

Type 'confirm' to run simulation or 'cancel' to abort."""

                send_message(chat_id, confirmation_text)
            else:
                send_message(chat_id, "❌ Please enter a percentage between 1 and 100.")
        except ValueError:
            send_message(chat_id, "❌ Please enter a valid number for sell percentage.")
    
    elif state == STATE_READY_TO_CONFIRM:
        if text.lower() == 'confirm':
            execute_simulation(chat_id)
        elif text.lower() == 'cancel':
            update_session(chat_id, state=STATE_IDLE)
            send_message(chat_id, "❌ Simulation cancelled. Type /simulate to start again.")
        else:
            send_message(chat_id, "Please type 'confirm' to run simulation or 'cancel' to abort.")
    
    else:
        send_message(chat_id, "Type /help to see available commands.")

def execute_simulation(chat_id):
    """Execute a trading simulation"""
    from models import TradeSimulation, db
    
    session = get_or_create_session(chat_id)
    
    # Create simulation record
    simulation = TradeSimulation()
    simulation.chat_id = str(chat_id)
    simulation.contract_address = session.contract_address
    simulation.trade_amount = session.trade_amount
    simulation.stop_loss = session.stop_loss
    simulation.take_profit = session.take_profit
    simulation.sell_percent = session.sell_percent
    
    # Simulate random outcome
    outcome = random.choice(['profit', 'loss', 'partial_profit'])
    
    if outcome == 'profit':
        profit_percent = random.uniform(session.take_profit * 0.8, session.take_profit * 1.2)
        profit_sol = session.trade_amount * (profit_percent / 100)
        simulation.result_type = 'profit'
        simulation.profit_loss = profit_sol
        
        result_text = f"""✅ <b>Simulation Complete - PROFIT!</b>

📈 <b>Results:</b>
• Profit: +{profit_percent:.1f}% ({profit_sol:.4f} SOL)
• Exit: Take-profit target hit
• Duration: {random.randint(5, 45)} minutes

🎉 <b>Great simulation trade!</b>"""
        
    elif outcome == 'loss':
        loss_percent = random.uniform(session.stop_loss * 0.8, session.stop_loss)
        loss_sol = session.trade_amount * (loss_percent / 100)
        simulation.result_type = 'loss'
        simulation.profit_loss = -loss_sol
        
        result_text = f"""❌ <b>Simulation Complete - LOSS</b>

📉 <b>Results:</b>
• Loss: -{loss_percent:.1f}% (-{loss_sol:.4f} SOL)
• Exit: Stop-loss triggered
• Duration: {random.randint(2, 30)} minutes

📚 <b>Learning opportunity!</b>"""
    
    else:  # partial_profit
        partial_percent = random.uniform(5, session.take_profit * 0.6)
        partial_sol = session.trade_amount * (partial_percent / 100)
        simulation.result_type = 'partial_profit'
        simulation.profit_loss = partial_sol
        
        result_text = f"""🔄 <b>Simulation Complete - PARTIAL PROFIT</b>

📊 <b>Results:</b>
• Profit: +{partial_percent:.1f}% ({partial_sol:.4f} SOL)
• Exit: Manual exit simulation
• Duration: {random.randint(10, 60)} minutes

💡 <b>Decent simulation trade!</b>"""
    
    db.session.add(simulation)
    db.session.commit()
    
    # Reset session
    update_session(chat_id, state=STATE_IDLE)
    
    result_text += f"\n\n🎮 <b>Ready for another simulation?</b>\nType /simulate to try again!"
    
    send_message(chat_id, result_text)