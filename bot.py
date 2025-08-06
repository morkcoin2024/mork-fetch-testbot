import os
import re
import logging
import requests
from datetime import datetime
from flask import current_app

# Bot configuration
BOT_TOKEN = "8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Command states
STATE_IDLE = "idle"
STATE_WAITING_CONTRACT = "waiting_contract"
STATE_WAITING_STOPLOSS = "waiting_stoploss"
STATE_WAITING_TAKEPROFIT = "waiting_takeprofit"
STATE_WAITING_SELLPERCENT = "waiting_sellpercent"
STATE_READY_TO_CONFIRM = "ready_to_confirm"

def send_message(chat_id, text, reply_markup=None):
    """Send a message to a Telegram chat"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
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
    with current_app.app_context():
        session = UserSession.query.filter_by(chat_id=str(chat_id)).first()
        if not session:
            session = UserSession()
            session.chat_id = str(chat_id)
            db.session.add(session)
            db.session.commit()
        return session

def update_session(chat_id, **kwargs):
    """Update user session data"""
    from models import UserSession, db
    with current_app.app_context():
        session = get_or_create_session(chat_id)
        for key, value in kwargs.items():
            setattr(session, key, value)
        db.session.commit()
        return session

def is_valid_solana_address(address):
    """Validate Solana contract address format"""
    if not address:
        return False
    
    # Trim whitespace
    address = address.strip()
    
    # Solana addresses are typically 32-44 characters, but let's be more flexible
    if len(address) < 32 or len(address) > 50:
        return False
    
    # Base58 character check (Bitcoin alphabet without 0, O, I, l)
    valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    
    # Check if all characters are valid Base58
    if not all(char in valid_chars for char in address):
        return False
    
    # Additional check: Solana addresses shouldn't contain ambiguous characters
    forbidden_chars = "0OIl"
    if any(char in forbidden_chars for char in address):
        return False
    
    return True

def is_valid_percentage(value):
    """Validate percentage input (0-100)"""
    try:
        percentage = float(value)
        return 0 <= percentage <= 100
    except ValueError:
        return False

def handle_start_command(chat_id, user_first_name):
    """Handle /start command"""
    welcome_text = f"""
🤖 <b>Welcome to Mork Sniper Bot, {user_first_name}!</b>

🧪 <b>FREE SIMULATION MODE</b>
Practice crypto sniping without risk! This is a simulation environment where you can learn how token sniping works.

<b>Available Commands:</b>
🎯 /snipe - Start a simulation snipe
📊 /status - Check your current session
❓ /help - Get help and instructions

<b>How it works:</b>
1. Use /snipe to start
2. Enter a token contract address
3. Set your stop-loss percentage
4. Set your take-profit percentage  
5. Set your sell percentage
6. Confirm to run simulation

Ready to practice? Type /snipe to begin!

<i>Note: This is simulation mode only. No real trades are executed.</i>
    """
    
    # Reset user session
    update_session(chat_id, state=STATE_IDLE, contract_address=None, 
                  stop_loss=None, take_profit=None, sell_percent=None)
    
    send_message(chat_id, welcome_text)

def handle_snipe_command(chat_id):
    """Handle /snipe command"""
    session = get_or_create_session(chat_id)
    
    snipe_text = """
🎯 <b>Starting Simulation Snipe</b>

Please enter the <b>Solana token contract address</b> you want to simulate sniping:

<i>Example: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM</i>

Type the contract address or /cancel to abort.
    """
    
    update_session(chat_id, state=STATE_WAITING_CONTRACT)
    send_message(chat_id, snipe_text)

def handle_contract_input(chat_id, contract_address):
    """Handle contract address input"""
    if not is_valid_solana_address(contract_address):
        error_text = """
❌ <b>Invalid Contract Address</b>

Please enter a valid Solana contract address (32-44 characters, Base58 encoded).

<i>Example: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    update_session(chat_id, contract_address=contract_address, state=STATE_WAITING_STOPLOSS)
    
    stoploss_text = f"""
✅ <b>Contract Address Set:</b>
<code>{contract_address}</code>

📉 Now enter your <b>Stop-Loss percentage</b> (0-100):

This is the percentage loss at which the bot will automatically sell to limit losses.

<i>Example: Enter "20" for 20% stop-loss</i>

Type a number between 0-100 or /cancel to abort.
    """
    
    send_message(chat_id, stoploss_text)

def handle_stoploss_input(chat_id, stop_loss):
    """Handle stop-loss percentage input"""
    if not is_valid_percentage(stop_loss):
        error_text = """
❌ <b>Invalid Stop-Loss Percentage</b>

Please enter a valid percentage between 0 and 100.

<i>Example: Enter "20" for 20% stop-loss</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    stop_loss_value = float(stop_loss)
    update_session(chat_id, stop_loss=stop_loss_value, state=STATE_WAITING_TAKEPROFIT)
    
    takeprofit_text = f"""
✅ <b>Stop-Loss Set:</b> {stop_loss_value}%

📈 Now enter your <b>Take-Profit percentage</b> (0-1000):

This is the percentage gain at which the bot will automatically sell to secure profits.

<i>Example: Enter "200" for 200% take-profit (3x return)</i>

Type a number between 0-1000 or /cancel to abort.
    """
    
    send_message(chat_id, takeprofit_text)

def handle_takeprofit_input(chat_id, take_profit):
    """Handle take-profit percentage input"""
    try:
        take_profit_value = float(take_profit)
        if take_profit_value < 0 or take_profit_value > 1000:
            raise ValueError()
    except ValueError:
        error_text = """
❌ <b>Invalid Take-Profit Percentage</b>

Please enter a valid percentage between 0 and 1000.

<i>Example: Enter "200" for 200% take-profit</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    update_session(chat_id, take_profit=take_profit_value, state=STATE_WAITING_SELLPERCENT)
    
    sellpercent_text = f"""
✅ <b>Take-Profit Set:</b> {take_profit_value}%

💰 Finally, enter the <b>percentage of tokens to sell</b> when conditions are met (1-100):

This determines how much of your position to sell when stop-loss or take-profit triggers.

<i>Example: Enter "50" to sell 50% of tokens, keeping 50%</i>

Type a number between 1-100 or /cancel to abort.
    """
    
    send_message(chat_id, sellpercent_text)

def handle_sellpercent_input(chat_id, sell_percent):
    """Handle sell percentage input"""
    try:
        sell_percent_value = float(sell_percent)
        if sell_percent_value < 1 or sell_percent_value > 100:
            raise ValueError()
    except ValueError:
        error_text = """
❌ <b>Invalid Sell Percentage</b>

Please enter a valid percentage between 1 and 100.

<i>Example: Enter "50" to sell 50% of tokens</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    session = update_session(chat_id, sell_percent=sell_percent_value, state=STATE_READY_TO_CONFIRM)
    
    confirm_text = f"""
🎯 <b>Simulation Snipe Ready!</b>

<b>📋 Configuration Summary:</b>
🎯 <b>Contract:</b> <code>{session.contract_address}</code>
📉 <b>Stop-Loss:</b> {session.stop_loss}%
📈 <b>Take-Profit:</b> {session.take_profit}%
💰 <b>Sell Amount:</b> {session.sell_percent}%

<b>⚠️ This is SIMULATION MODE</b>
No real trades will be executed. This is for learning purposes only.

Type <b>/confirm</b> to run the simulation or /cancel to abort.
    """
    
    send_message(chat_id, confirm_text)

def handle_confirm_command(chat_id):
    """Handle /confirm command"""
    session = get_or_create_session(chat_id)
    
    if session.state != STATE_READY_TO_CONFIRM:
        error_text = """
❌ <b>Nothing to Confirm</b>

Please start a new snipe with /snipe first.
        """
        send_message(chat_id, error_text)
        return
    
    # Simulate the trade
    simulation_text = f"""
🎮 <b>SIMULATION EXECUTING...</b>

<b>📊 Simulated Trade Details:</b>
🎯 <b>Token:</b> <code>{session.contract_address}</code>
💵 <b>Simulated Investment:</b> 1.0 SOL
📉 <b>Stop-Loss:</b> {session.stop_loss}%
📈 <b>Take-Profit:</b> {session.take_profit}%
💰 <b>Sell Amount:</b> {session.sell_percent}%

⏱️ <b>Simulation Results:</b>
✅ Trade simulation completed successfully!
📈 Simulated entry price: $0.00234 per token
🎯 Tokens acquired: 427,350 tokens
⏰ Execution time: 0.3 seconds

<b>🎯 Monitoring Conditions:</b>
• Stop-loss trigger: Price drops to $0.{int((100-session.stop_loss)*234/100):05d}
• Take-profit trigger: Price rises to $0.{int((100+session.take_profit)*234/100):05d}
• Will sell {session.sell_percent}% when triggered

<b>🧪 This was a SIMULATION!</b>
In live mode, this would execute real trades on Solana DEXs.

Type /snipe to run another simulation or /status to check session.
    """
    
    # Reset session after simulation
    update_session(chat_id, state=STATE_IDLE)
    
    send_message(chat_id, simulation_text)

def handle_status_command(chat_id):
    """Handle /status command"""
    session = get_or_create_session(chat_id)
    
    if session.state == STATE_IDLE:
        status_text = """
📊 <b>Session Status</b>

🟢 <b>Status:</b> Ready
🧪 <b>Mode:</b> Simulation (Free)
⏰ <b>Last Activity:</b> Ready for new snipe

Type /snipe to start a new simulation!
        """
    else:
        state_descriptions = {
            STATE_WAITING_CONTRACT: "Waiting for contract address",
            STATE_WAITING_STOPLOSS: "Waiting for stop-loss percentage", 
            STATE_WAITING_TAKEPROFIT: "Waiting for take-profit percentage",
            STATE_WAITING_SELLPERCENT: "Waiting for sell percentage",
            STATE_READY_TO_CONFIRM: "Ready to confirm simulation"
        }
        
        status_text = f"""
📊 <b>Session Status</b>

🟡 <b>Status:</b> In Progress
🧪 <b>Mode:</b> Simulation (Free)
📝 <b>Current Step:</b> {state_descriptions.get(session.state, "Unknown")}

<b>Configuration:</b>
🎯 <b>Contract:</b> {session.contract_address or "Not set"}
📉 <b>Stop-Loss:</b> {f"{session.stop_loss}%" if session.stop_loss else "Not set"}
📈 <b>Take-Profit:</b> {f"{session.take_profit}%" if session.take_profit else "Not set"}
💰 <b>Sell Amount:</b> {f"{session.sell_percent}%" if session.sell_percent else "Not set"}

Type /cancel to abort current operation.
        """
    
    send_message(chat_id, status_text)

def handle_help_command(chat_id):
    """Handle /help command"""
    help_text = """
❓ <b>Mork Sniper Bot Help</b>

<b>🧪 FREE SIMULATION MODE</b>
Practice crypto sniping safely without real money.

<b>📋 Available Commands:</b>
• <b>/start</b> - Welcome message and reset session
• <b>/snipe</b> - Start a new simulation snipe
• <b>/confirm</b> - Execute the simulation
• <b>/status</b> - Check current session status
• <b>/cancel</b> - Cancel current operation
• <b>/help</b> - Show this help message

<b>📖 How to Use:</b>
1. Type /snipe to begin
2. Enter a Solana token contract address
3. Set your stop-loss percentage (0-100%)
4. Set your take-profit percentage (0-1000%)
5. Set what percentage to sell (1-100%)
6. Type /confirm to run simulation

<b>🎯 What is Sniping?</b>
Token sniping means buying tokens quickly when they launch or hit certain price points, then selling based on predefined profit/loss targets.

<b>⚠️ Important Notes:</b>
• This is simulation mode - no real trades
• Real mode requires 100,000 $MORK tokens
• Always DYOR (Do Your Own Research)

<b>🔗 Future Features (Live Mode):</b>
• Real Solana/Pump.fun integration
• Phantom wallet linking
• Auto-scanning new launches
• Copy trading features

Need help? Contact support in our Telegram group!
    """
    
    send_message(chat_id, help_text)

def handle_cancel_command(chat_id):
    """Handle /cancel command"""
    session = get_or_create_session(chat_id)
    
    if session.state == STATE_IDLE:
        cancel_text = """
ℹ️ <b>Nothing to Cancel</b>

You don't have any active operations running.

Type /snipe to start a new simulation!
        """
    else:
        cancel_text = """
❌ <b>Operation Cancelled</b>

Your current snipe setup has been cancelled and reset.

Type /snipe to start a new simulation!
        """
        update_session(chat_id, state=STATE_IDLE, contract_address=None,
                      stop_loss=None, take_profit=None, sell_percent=None)
    
    send_message(chat_id, cancel_text)

def handle_update(update):
    """Main update handler for Telegram webhook"""
    try:
        if 'message' not in update:
            return
        
        message = update['message']
        chat_id = message['chat']['id']
        
        if 'text' not in message:
            send_message(chat_id, "Please send text messages only.")
            return
        
        text = message['text'].strip()
        user_first_name = message['from'].get('first_name', 'User')
        
        # Handle commands
        if text.startswith('/'):
            command = text.lower().split()[0]
            
            if command == '/start':
                handle_start_command(chat_id, user_first_name)
            elif command == '/snipe':
                handle_snipe_command(chat_id)
            elif command == '/confirm':
                handle_confirm_command(chat_id)
            elif command == '/status':
                handle_status_command(chat_id)
            elif command == '/help':
                handle_help_command(chat_id)
            elif command == '/cancel':
                handle_cancel_command(chat_id)
            else:
                send_message(chat_id, "Unknown command. Type /help for available commands.")
        else:
            # Handle text input based on current state
            session = get_or_create_session(chat_id)
            
            if session.state == STATE_WAITING_CONTRACT:
                handle_contract_input(chat_id, text)
            elif session.state == STATE_WAITING_STOPLOSS:
                handle_stoploss_input(chat_id, text)
            elif session.state == STATE_WAITING_TAKEPROFIT:
                handle_takeprofit_input(chat_id, text)
            elif session.state == STATE_WAITING_SELLPERCENT:
                handle_sellpercent_input(chat_id, text)
            else:
                send_message(chat_id, "I'm not sure what you mean. Type /help for available commands or /snipe to start a simulation.")
    
    except Exception as e:
        logging.error(f"Error handling update: {e}")
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            send_message(chat_id, "Sorry, an error occurred. Please try again or type /start to reset.")

def set_webhook(webhook_url):
    """Set the webhook URL for the bot"""
    url = f"{TELEGRAM_API_URL}/setWebhook"
    data = {'url': webhook_url}
    
    try:
        response = requests.post(url, json=data)
        result = response.json()
        logging.info(f"Webhook set result: {result}")
        return result.get('ok', False)
    except Exception as e:
        logging.error(f"Error setting webhook: {e}")
        return False
